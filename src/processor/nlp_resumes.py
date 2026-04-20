import os
import json
import re
import asyncio
from pydantic import ValidationError
from groq import AsyncGroq
from dotenv import load_dotenv

from src.db.database import AsyncDatabasePool
from src.processor.schemas import ResumeSchema

load_dotenv()
client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))

SYSTEM_INSTRUCTION = """
Ти професійний HR-аналітик. Твоє завдання: проаналізувати текст резюме.
Поверни ВИКЛЮЧНО валідний JSON. ЗАБОРОНЕНО писати будь-який інший текст.

СХЕМА JSON (суворо дотримуйся цих типів даних, якщо даних немає - пиши null):
{
    "title": "Python Developer", 
    "location_name": "Львів", 
    "region": "Львівська область", 
    "expected_salary": 2500, 
    "currency": "USD", 
    "experience_years": 3, 
    "english_level": "Upper-Intermediate", 
    "skills": [ {"name": "Python", "category": "Hard", "years_of_experience": 2} ]
    # Якщо досвід для конкретної навички не вказано, пиши years_of_experience: null.
}
УВАГА: skills - це ЗАВЖДИ масив об'єктів (або порожній масив []), expected_salary та experience_years - це ЗАВЖДИ цілі числа.
"""


def prepare_text_for_llm(raw_text: str | None) -> str:
    if not raw_text:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw_text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:1500]


async def get_or_create_location(conn, city_name, region, cache):
    if not city_name:
        return None
    city_name = city_name[:99]
    if city_name in cache["locations"]:
        return cache["locations"][city_name]
    loc_id = await conn.fetchval(
        "SELECT id FROM dictionaries.locations WHERE city_name = $1 LIMIT 1;", city_name
    )
    if not loc_id:
        loc_id = await conn.fetchval(
            "INSERT INTO dictionaries.locations (city_name, region) VALUES ($1, $2) RETURNING id;",
            city_name,
            region,
        )
    cache["locations"][city_name] = loc_id
    return loc_id


async def get_or_create_skill(conn, name, category, cache):
    if not name:
        return None
    name = name[:99]
    if name in cache["skills"]:
        return cache["skills"][name]
    skill_id = await conn.fetchval(
        "INSERT INTO dictionaries.skills (name, category) VALUES ($1, $2) ON CONFLICT (name) DO NOTHING RETURNING id;",
        name,
        category,
    )
    if not skill_id:
        skill_id = await conn.fetchval(
            "SELECT id FROM dictionaries.skills WHERE name = $1;", name
        )
    cache["skills"][name] = skill_id
    return skill_id


async def process_single_resume(record, cache, semaphore):
    staging_id = record["id"]
    raw_text = record["raw_text"]
    raw_json = record["raw_json"]

    if isinstance(raw_json, str):
        raw_json = json.loads(raw_json)
    if not raw_json:
        raw_json = {}

    safe_text = prepare_text_for_llm(raw_text)
    prompt = f"Текст резюме:\n{safe_text}"

    async with semaphore:
        for attempt in range(3):
            try:
                chat_completion = await client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": SYSTEM_INSTRUCTION},
                        {"role": "user", "content": prompt},
                    ],
                    model="llama-3.1-8b-instant",
                    temperature=0,  # Детермінованість
                    response_format={"type": "json_object"},
                )

                response_text = chat_completion.choices[0].message.content
                if not response_text:
                    raise ValueError("Отримано порожню відповідь від LLM")

                md_ticks = "`" * 3
                response_text = (
                    response_text.strip()
                    .removeprefix(md_ticks + "json")
                    .removeprefix(md_ticks)
                    .removesuffix(md_ticks)
                    .strip()
                )

                ai_data = ResumeSchema.model_validate_json(response_text)

                async with AsyncDatabasePool.get_connection() as conn:
                    async with conn.transaction():
                        loc_id = await get_or_create_location(
                            conn, ai_data.location_name, ai_data.region, cache
                        )

                        new_resume_id = await conn.fetchval(
                            "INSERT INTO core.resumes (staging_id, title, location_id, min_salary, max_salary, currency, experience_years, english_level) VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING id;",
                            staging_id,
                            ai_data.title[:200],
                            loc_id,
                            ai_data.expected_salary,
                            ai_data.expected_salary,
                            ai_data.currency,
                            ai_data.experience_years,
                            ai_data.english_level,
                        )

                        for skill in ai_data.skills:
                            skill_id = await get_or_create_skill(conn, skill.name, skill.category, cache)
                            if skill_id: 
                                # Змінили запит: додали years_of_experience
                                await conn.execute(
                                    """INSERT INTO core.resume_skills (resume_id, skill_id, years_of_experience) 
                                       VALUES ($1, $2, $3) ON CONFLICT DO NOTHING;""", 
                                    new_resume_id, skill_id, skill.years_of_experience
                                )

                print(f"   💾 Успішно: [ID {staging_id}] {ai_data.title[:30]}...")
                await asyncio.sleep(1)
                return True

            except ValidationError as ve:
                failed_fields = [str(err.get("loc", [""])[0]) for err in ve.errors()]
                print(
                    f"   ⚠️ Галюцинація LLM (спроба {attempt + 1}). Зламались поля: {failed_fields}"
                )
                await asyncio.sleep(2)
            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg or "rate" in error_msg.lower():
                    await asyncio.sleep(10 * (attempt + 1))
                else:
                    print(f"   ❌ Помилка: {error_msg}")
                    break
        return False


async def main():
    await AsyncDatabasePool.initialize()
    cache = {"locations": {}, "skills": {}}
    semaphore = asyncio.Semaphore(10)

    async with AsyncDatabasePool.get_connection() as conn:
        records = await conn.fetch(
            "SELECT s.id, s.external_id, s.raw_text, s.raw_json FROM staging.raw_resumes s LEFT JOIN core.resumes c ON s.id = c.staging_id WHERE s.raw_text IS NOT NULL AND s.raw_text != '' AND c.id IS NULL LIMIT 100;"
        )

    if not records:
        print("⚠️ Немає нових резюме для обробки.")
        #await AsyncDatabasePool.close_all()
        return

    print(f"🚀 Старт ASYNC обробки {len(records)} резюме (Groq + Pydantic)...")
    tasks = [process_single_resume(record, cache, semaphore) for record in records]
    await asyncio.gather(*tasks)
    #await AsyncDatabasePool.close_all()


if __name__ == "__main__":
    asyncio.run(main())
