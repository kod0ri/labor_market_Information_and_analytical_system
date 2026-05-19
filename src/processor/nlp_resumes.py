import os
import json
import re
import asyncio
from pydantic import ValidationError
from groq import AsyncGroq
from dotenv import load_dotenv

from src.db.database import AsyncDatabasePool
from src.processor.schemas import ResumeSchema
from src.processor.skill_normalizer import resolve_skill_id
from src.processor.failure_tracker import record_failure, mark_resolved
from src.processor.rate_limiter import TokenBucketRateLimiter, GROQ_BUDGET
from src.processor.llm_utils import _parse_retry_after, prepare_text_for_llm, get_or_create_location, get_or_create_source

load_dotenv()
client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))

# Prefect запускає nlp_vacancies і nlp_resumes паралельно.
# Кожен модуль має власний limiter → combined rate = 2 × N.
# Groq llama-4-scout-17b: 30 RPM. Безпечний combined: 20 RPM → 10 RPM кожен → 0.16 req/s.
GROQ_RATE_LIMITER = TokenBucketRateLimiter(rate_per_second=0.16, burst=1)

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
ПРАВИЛА:
- skills — ЗАВЖДИ масив об'єктів {name, category}. expected_salary та experience_years — ЗАВЖДИ цілі числа.
- currency — ТІЛЬКИ код ISO 4217: UAH, USD, EUR. Якщо написано "грн" або "гривня" — пиши UAH.
- english_level — ТІЛЬКИ одне зі значень: Beginner, Elementary, Pre-Intermediate, Intermediate, Upper-Intermediate, Advanced, Fluent, Native. Шукай у: сертифікатах (IELTS 6.0-6.5→Upper-Intermediate, 7.0+→Advanced; TOEFL 72-94→Upper-Intermediate, 95+→Advanced), описах мов ("вільна англійська"→Advanced, "середня"→Intermediate, "базова"→Elementary, "B2"→Upper-Intermediate тощо). Якщо не знайдено — пиши null.
"""


async def process_single_resume(
    record, cache: dict, cache_lock: asyncio.Lock,
    rate_limiter: TokenBucketRateLimiter, db_semaphore: asyncio.Semaphore,
) -> bool:
    staging_id = record["id"]
    source_name = record["source_name"]

    if GROQ_BUDGET.is_exhausted():
        print(f"   ⏸️ [ID {staging_id}] Groq TPD/RPD budget вичерпано ({GROQ_BUDGET.summary}), пропускаємо.")
        return False

    raw_text = record["raw_text"]
    raw_json = (
        record["raw_json"]
        if isinstance(record["raw_json"], dict)
        else json.loads(record["raw_json"] or "{}")
    )
    base_title = raw_json.get("title", "Невідоме резюме")

    safe_text = await prepare_text_for_llm(raw_text)
    prompt = f"Текст резюме:\n{safe_text}\n\nБазова посада: {base_title}"

    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            await rate_limiter.acquire()

            if GROQ_BUDGET.is_exhausted():
                print(f"   ⏸️ [ID {staging_id}] Budget вичерпано після очікування, пропускаємо.")
                return False

            chat_completion = await client.chat.completions.create(
                messages=[
                    {"role": "system", "content": SYSTEM_INSTRUCTION},
                    {"role": "user", "content": prompt},
                ],
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                temperature=0,
                response_format={"type": "json_object"},
            )

            if chat_completion.usage:
                await GROQ_BUDGET.record(chat_completion.usage.total_tokens)

            response_text = chat_completion.choices[0].message.content
            if not response_text:
                raise ValueError("Порожня відповідь від LLM")

            match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if not match:
                raise ValueError("LLM не повернула валідний JSON")

            ai_data = ResumeSchema.model_validate_json(match.group(0))
            final_title = ai_data.title or base_title

            async with db_semaphore:
                async with AsyncDatabasePool.get_connection() as conn:
                    async with conn.transaction():
                        loc_id = await get_or_create_location(
                            conn, ai_data.location_name, ai_data.region,
                            cache, cache_lock,
                        )
                        src_id = await get_or_create_source(
                            conn, source_name, cache, cache_lock,
                        )
                        new_resume_id = await conn.fetchval(
                            """
                            INSERT INTO core.resumes
                                (staging_id, title, location_id, source_id,
                                 min_salary, max_salary, currency,
                                 experience_years, english_level)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                            RETURNING id;
                            """,
                            staging_id, str(final_title)[:200], loc_id, src_id,
                            ai_data.min_salary, ai_data.max_salary, ai_data.currency,
                            ai_data.experience_years, ai_data.english_level,
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

            print(f"   💾 Успішно: [ID {staging_id}] {str(final_title)[:35]}...")
            return True

        except ValidationError as ve:
            failed_fields = [str(e.get("loc", [""])[0]) for e in ve.errors()]
            detail = f"fields={failed_fields}"
            print(f"   ⚠️ [ID {staging_id}] Галюцинація LLM (спроба {attempt + 1}/{max_attempts}). {detail}")
            if attempt == max_attempts - 1:
                async with db_semaphore:
                    async with AsyncDatabasePool.get_connection() as conn:
                        await record_failure(conn, "resume", staging_id, "validation", detail, attempt + 1)
            await asyncio.sleep(1)

        except Exception as e:
            if "429" in str(e) or "rate_limit" in str(e).lower():
                wait = _parse_retry_after(e)
                print(f"   ⏳ [ID {staging_id}] Rate limit (спроба {attempt + 1}/{max_attempts}). Чекаємо {wait:.1f}s...")
                await asyncio.sleep(wait)
            else:
                print(f"   ❌ [ID {staging_id}] Помилка: {e}")
                async with db_semaphore:
                    async with AsyncDatabasePool.get_connection() as conn:
                        await record_failure(conn, "resume", staging_id, "unknown", str(e), attempt + 1)
                return False

    print(f"   💀 [ID {staging_id}] Вичерпано {max_attempts} спроби.")
    async with db_semaphore:
        async with AsyncDatabasePool.get_connection() as conn:
            await record_failure(
                conn, "resume", staging_id,
                "validation", f"Exhausted {max_attempts} attempts", max_attempts,
            )
    return False


async def run_processor() -> None:
    cache = {"locations": {}, "skills": {}, "sources": {}}
    cache_lock = asyncio.Lock()
    rate_limiter = GROQ_RATE_LIMITER
    db_semaphore = asyncio.Semaphore(15)

    async with AsyncDatabasePool.get_connection() as conn:
        records = await conn.fetch(
            """
            SELECT s.id, s.source_name, s.external_id, s.raw_text, s.raw_json
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
        f"(llama-4-scout, ~10 запитів/хв, орієнтовно {len(records) // 10 + 1} хв)..."
    )
    results = await asyncio.gather(
        *[process_single_resume(r, cache, cache_lock, rate_limiter, db_semaphore) for r in records],
        return_exceptions=True,
    )
    success = sum(1 for r in results if r is True)
    print(f"\n📊 Результат: ✅ {success} успішно, ❌ {len(results) - success} помилок.")
    print(f"📈 Groq budget: {GROQ_BUDGET.summary}")


async def main() -> None:
    await run_processor()


if __name__ == "__main__":
    async def _main():
        await AsyncDatabasePool.initialize()
        try:
            await run_processor()
        finally:
            await AsyncDatabasePool.close_all()

    asyncio.run(_main())
