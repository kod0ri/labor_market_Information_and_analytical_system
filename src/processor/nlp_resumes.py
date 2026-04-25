import os
import re
import asyncio
from bs4 import BeautifulSoup
from pydantic import ValidationError
from groq import AsyncGroq
from dotenv import load_dotenv

from src.db.database import AsyncDatabasePool
from src.processor.schemas import ResumeSchema
from src.processor.skill_normalizer import resolve_skill_id
from src.processor.failure_tracker import record_failure, mark_resolved
from src.processor.rate_limiter import TokenBucketRateLimiter

load_dotenv()
client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))

# Той самий глобальний rate limiter що і у вакансіях
# Якщо запускаються паралельно — вони ділять один ліміт
GROQ_RATE_LIMITER = TokenBucketRateLimiter(rate_per_second=0.25, burst=1)

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
    "skills": [ {"name": "Python", "category": "Hard"} ]
}
УВАГА: skills - це ЗАВЖДИ масив об'єктів (без вказання досвіду для кожної навички), expected_salary та experience_years - це ЗАВЖДИ цілі числа.
"""


def _parse_retry_after(error: Exception) -> float:
    """Витягує точний retry-after з повідомлення Groq."""
    msg = str(error)
    match = re.search(r"try again in ([0-9.]+)(s|ms)", msg)
    if match:
        value, unit = float(match.group(1)), match.group(2)
        return (value if unit == "s" else value / 1000) + 0.5
    return 10.0


def prepare_text_for_llm(raw_text: str | None) -> str:
    if not raw_text:
        return ""
    text = BeautifulSoup(raw_text, "html.parser").get_text(separator=" ", strip=True)
    return text[:1500]


async def get_or_create_location(conn, city_name, region, cache, cache_lock):
    if not city_name:
        return None
    city_name = city_name[:99]
    async with cache_lock:
        if city_name in cache["locations"]:
            return cache["locations"][city_name]
        loc_id = await conn.fetchval(
            "SELECT id FROM dictionaries.locations WHERE city_name = $1 LIMIT 1;",
            city_name,
        )
        if not loc_id:
            loc_id = await conn.fetchval(
                "INSERT INTO dictionaries.locations (city_name, region) VALUES ($1, $2) RETURNING id;",
                city_name, region,
            )
        cache["locations"][city_name] = loc_id
        return loc_id


async def process_single_resume(record, cache, cache_lock, rate_limiter):
    staging_id = record["id"]
    raw_text   = record["raw_text"]

    safe_text = prepare_text_for_llm(raw_text)
    prompt    = f"Текст резюме:\n{safe_text}"

    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            # ✅ Token Bucket: рівномірний потік запитів
            await rate_limiter.acquire()

            chat_completion = await client.chat.completions.create(
                messages=[
                    {"role": "system", "content": SYSTEM_INSTRUCTION},
                    {"role": "user",   "content": prompt},
                ],
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                temperature=0,
                response_format={"type": "json_object"},
            )

            response_text = chat_completion.choices[0].message.content
            if not response_text:
                raise ValueError("Отримано порожню відповідь від LLM")

            match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if not match:
                raise ValueError("LLM не повернула валідний JSON об'єкт")

            ai_data = ResumeSchema.model_validate_json(match.group(0))

            async with AsyncDatabasePool.get_connection() as conn:
                async with conn.transaction():
                    loc_id = await get_or_create_location(
                        conn, ai_data.location_name, ai_data.region, cache, cache_lock,
                    )

                    new_resume_id = await conn.fetchval(
                        """
                        INSERT INTO core.resumes
                            (staging_id, title, location_id,
                             min_salary, max_salary, currency,
                             experience_years, english_level)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        RETURNING id;
                        """,
                        staging_id, ai_data.title[:200], loc_id,
                        ai_data.expected_salary, ai_data.expected_salary,
                        ai_data.currency, ai_data.experience_years,
                        ai_data.english_level,
                    )

                    for skill in ai_data.skills:
                        skill_id = await resolve_skill_id(
                            conn, skill.name, skill.category, cache, cache_lock,
                        )
                        if skill_id:
                            await conn.execute(
                                "INSERT INTO core.resume_skills (resume_id, skill_id) "
                                "VALUES ($1, $2) ON CONFLICT DO NOTHING;",
                                new_resume_id, skill_id,
                            )

                    await conn.execute(
                        "UPDATE staging.raw_resumes SET raw_text = NULL WHERE id = $1;",
                        staging_id,
                    )
                    await mark_resolved(conn, "resume", staging_id)

            print(f"   💾 Успішно: [ID {staging_id}] {ai_data.title[:35]}...")
            return True

        except ValidationError as ve:
            failed_fields = [str(err.get("loc", [""])[0]) for err in ve.errors()]
            detail = f"fields={failed_fields}"
            print(f"   ⚠️ [ID {staging_id}] Галюцинація LLM (спроба {attempt + 1}/{max_attempts}). {detail}")
            if attempt == max_attempts - 1:
                async with AsyncDatabasePool.get_connection() as conn:
                    await record_failure(conn, "resume", staging_id, "validation", detail, attempt + 1)
            await asyncio.sleep(1)

        except Exception as e:
            is_rate_limit = "429" in str(e) or "rate_limit" in str(e).lower()

            if is_rate_limit:
                wait = _parse_retry_after(e)
                print(f"   ⏳ [ID {staging_id}] Rate limit (спроба {attempt + 1}/{max_attempts}). Чекаємо {wait:.1f}s...")
                await asyncio.sleep(wait)
            else:
                print(f"   ❌ [ID {staging_id}] Невідновлювана помилка: {e}")
                async with AsyncDatabasePool.get_connection() as conn:
                    await record_failure(conn, "resume", staging_id, "unknown", str(e), attempt + 1)
                return False

    print(f"   💀 [ID {staging_id}] Вичерпано всі {max_attempts} спроби. Пропускаємо.")
    async with AsyncDatabasePool.get_connection() as conn:
        await record_failure(
            conn, "resume", staging_id,
            "validation", f"Exhausted {max_attempts} attempts", max_attempts,
        )
    return False


async def main():
    await AsyncDatabasePool.initialize()
    cache = {"locations": {}, "skills": {}}
    cache_lock   = asyncio.Lock()
    rate_limiter = GROQ_RATE_LIMITER

    async with AsyncDatabasePool.get_connection() as conn:
        records = await conn.fetch(
            """
            SELECT s.id, s.external_id, s.raw_text, s.raw_json
            FROM staging.raw_resumes s
            LEFT JOIN core.resumes c ON s.id = c.staging_id
            LEFT JOIN staging.failed_records f
                   ON f.staging_id  = s.id
                  AND f.record_type = 'resume'
                  AND f.is_resolved = FALSE
            WHERE s.raw_text IS NOT NULL
              AND s.raw_text != ''
              AND c.id IS NULL
              AND f.id IS NULL
            LIMIT 100;
            """
        )

    if not records:
        print("⚠️ Немає нових резюме для обробки.")
        return

    print(
        f"🚀 Старт обробки {len(records)} резюме "
        f"(llama-4-scout, ~20 запитів/хв, орієнтовно {len(records)//20 + 1} хв)..."
    )

    tasks = [
        process_single_resume(record, cache, cache_lock, rate_limiter)
        for record in records
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    success = sum(1 for r in results if r is True)
    failed  = len(results) - success
    print(f"\n📊 Результат: ✅ {success} успішно, ❌ {failed} помилок.")


if __name__ == "__main__":
    asyncio.run(main())