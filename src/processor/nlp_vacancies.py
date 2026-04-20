import os
import json
import re
import asyncio
from pydantic import ValidationError
from groq import AsyncGroq
from dotenv import load_dotenv

from src.db.database import AsyncDatabasePool
from src.processor.schemas import VacancySchema

load_dotenv()
client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))

SYSTEM_INSTRUCTION = """
Ти професійний IT-аналітик та Data Engineer. Твоє завдання: проаналізувати текст вакансії.
Поверни ВИКЛЮЧНО валідний JSON. ЗАБОРОНЕНО писати будь-який інший текст.

СХЕМА JSON (суворо дотримуйся цих типів даних, якщо даних немає - пиши null):
{
    "skills": [ {"name": "назва", "category": "Hard або Soft"} ],
    "experience_years": 2, 
    "english_level": "Intermediate", 
    "min_salary": 20000, 
    "max_salary": 40000, 
    "currency": "UAH", 
    "company_industry": "IT", 
    "website_url": "https://example.com", 
    "region": "Київська область" 
}
УВАГА: skills - це ЗАВЖДИ масив об'єктів (або порожній масив []), min_salary та max_salary - це ЗАВЖДИ цілі числа (не рядки).
"""


def prepare_text_for_llm(raw_text: str | None) -> str:
    if not raw_text:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw_text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:1500]


async def get_or_create_company(conn, name, industry, website, cache):
    if not name:
        return None
    name = name[:200]
    if name in cache["companies"]:
        return cache["companies"][name]
    query = """
        INSERT INTO dictionaries.companies (name, industry, website_url) VALUES ($1, $2, $3) 
        ON CONFLICT (name) DO UPDATE SET industry = COALESCE(dictionaries.companies.industry, EXCLUDED.industry), website_url = COALESCE(dictionaries.companies.website_url, EXCLUDED.website_url) RETURNING id;
    """
    comp_id = await conn.fetchval(query, name, industry, website)
    if not comp_id:
        comp_id = await conn.fetchval(
            "SELECT id FROM dictionaries.companies WHERE name = $1;", name
        )
    cache["companies"][name] = comp_id
    return comp_id


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


async def process_single_vacancy(record, cache, semaphore):
    staging_id = record["id"]
    raw_html = record["raw_html"]
    raw_json = record["raw_json"]

    if isinstance(raw_json, str):
        raw_json = json.loads(raw_json)
    if not raw_json:
        raw_json = {}

    title = raw_json.get("title", "Невідома посада")
    company_name = raw_json.get("company", "")
    location_name = raw_json.get("location", "")
    raw_salary = raw_json.get("salary", "")

    safe_text = prepare_text_for_llm(raw_html)
    prompt = f"Текст вакансії:\n{safe_text}\n\nВказана зарплата: {raw_salary}"

    async with semaphore:
        for attempt in range(3):
            try:
                chat_completion = await client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": SYSTEM_INSTRUCTION},
                        {"role": "user", "content": prompt},
                    ],
                    model="llama-3.1-8b-instant",
                    temperature=0,  # Повний нуль для мінімізації галюцинацій
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

                ai_data = VacancySchema.model_validate_json(response_text)

                async with AsyncDatabasePool.get_connection() as conn:
                    async with conn.transaction():
                        comp_id = await get_or_create_company(
                            conn,
                            company_name,
                            ai_data.company_industry,
                            ai_data.website_url,
                            cache,
                        )
                        loc_id = await get_or_create_location(
                            conn, location_name, ai_data.region, cache
                        )

                        new_vacancy_id = await conn.fetchval(
                            "INSERT INTO core.vacancies (staging_id, title, company_id, location_id, min_salary, max_salary, currency, experience_years, english_level) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) RETURNING id;",
                            staging_id,
                            str(title)[:200],
                            comp_id,
                            loc_id,
                            ai_data.min_salary,
                            ai_data.max_salary,
                            ai_data.currency,
                            ai_data.experience_years,
                            ai_data.english_level,
                        )

                        for skill in ai_data.skills:
                            skill_id = await get_or_create_skill(
                                conn, skill.name, skill.category, cache
                            )
                            if skill_id:
                                await conn.execute(
                                    "INSERT INTO core.vacancy_skills (vacancy_id, skill_id) VALUES ($1, $2) ON CONFLICT DO NOTHING;",
                                    new_vacancy_id,
                                    skill_id,
                                )

                print(f"   💾 Успішно: [ID {staging_id}] {title[:30]}...")
                await asyncio.sleep(1)
                return True

            except ValidationError as ve:
                # ВИТЯГУЄМО ТОЧНУ ПРИЧИНУ ПОМИЛКИ
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
    cache = {"companies": {}, "locations": {}, "skills": {}}
    semaphore = asyncio.Semaphore(10)

    async with AsyncDatabasePool.get_connection() as conn:
        records = await conn.fetch(
            "SELECT s.id, s.external_id, s.raw_html, s.raw_json FROM staging.raw_vacancies s LEFT JOIN core.vacancies c ON s.id = c.staging_id WHERE s.raw_html IS NOT NULL AND s.raw_html != '' AND c.id IS NULL LIMIT 100;"
        )

    if not records:
        print("⚠️ Немає нових вакансій для обробки.")
        #await AsyncDatabasePool.close_all()
        return

    print(f"🚀 Старт ASYNC обробки {len(records)} вакансій (Groq + Pydantic)...")
    tasks = [process_single_vacancy(record, cache, semaphore) for record in records]
    await asyncio.gather(*tasks)
    #await AsyncDatabasePool.close_all()


if __name__ == "__main__":
    asyncio.run(main())
