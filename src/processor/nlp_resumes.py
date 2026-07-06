import os
import json
import asyncio
from dotenv import load_dotenv

from src.processor.schemas import ResumeSchema
from src.processor.skill_normalizer import resolve_skill_id
from src.processor.failure_tracker import mark_resolved
from src.processor.nlp_pipeline import run_llm_record
from src.processor.llm_cascade import (
    any_available,
    budget_summary,
    cascade_summary,
)
from src.processor.llm_utils import prepare_text_for_llm, get_or_create_location, get_or_create_source
from src.db.database import AsyncDatabasePool

load_dotenv()

# Скільки записів за один прогін (спільне з вакансіями, кожен бере по стільки).
BATCH_LIMIT = int(os.getenv("NLP_BATCH_LIMIT", "200"))

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
    db_semaphore: asyncio.Semaphore,
) -> bool:
    staging_id = record["id"]
    source_name = record["source_name"]

    raw_text = record["raw_text"]
    raw_json = (
        record["raw_json"]
        if isinstance(record["raw_json"], dict)
        else json.loads(record["raw_json"] or "{}")
    )
    base_title = raw_json.get("title", "Невідоме резюме")

    safe_text = await prepare_text_for_llm(raw_text)
    prompt = f"Текст резюме:\n{safe_text}\n\nБазова посада: {base_title}"
    messages = [
        {"role": "system", "content": SYSTEM_INSTRUCTION},
        {"role": "user", "content": prompt},
    ]

    async def _persist(conn, ai_data: ResumeSchema) -> str:
        final_title = ai_data.title or base_title

        loc_id = await get_or_create_location(
            conn, ai_data.location_name, ai_data.region, cache, cache_lock,
        )
        src_id = await get_or_create_source(conn, source_name, cache, cache_lock)
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
        return str(final_title)[:35]

    return await run_llm_record(
        staging_id=staging_id,
        record_type="resume",
        messages=messages,
        schema_cls=ResumeSchema,
        db_semaphore=db_semaphore,
        persist=_persist,
    )


async def run_processor() -> None:
    cache = {"locations": {}, "skills": {}, "sources": {}}
    cache_lock = asyncio.Lock()
    db_semaphore = asyncio.Semaphore(15)

    print(f"🚀 Обробка резюме (LLM-каскад: {cascade_summary()})...")
    total_success = total_fail = 0
    batch_no = 0
    no_progress = 0

    # Drain-режим: батчі по BATCH_LIMIT, поки черга не спорожніє або денний
    # бюджет усіх провайдерів не вичерпається.
    while True:
        if not any_available():
            print(f"   ⏹️ Денний бюджет провайдерів вичерпано ({budget_summary()}).")
            break

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
                LIMIT $1;
                """,
                BATCH_LIMIT,
            )

        if not records:
            print("   ✅ Черга резюме порожня." if batch_no else "⚠️ Немає нових резюме для обробки.")
            break

        batch_no += 1
        print(f"   📦 Батч {batch_no}: {len(records)} резюме...")
        results = await asyncio.gather(
            *[process_single_resume(r, cache, cache_lock, db_semaphore) for r in records],
            return_exceptions=True,
        )
        success = sum(1 for r in results if r is True)
        total_success += success
        total_fail += len(results) - success

        if success == 0:
            no_progress += 1
            if no_progress >= 2:
                print("   ⏹️ Два батчі без прогресу — зупиняємось до наступного прогону.")
                break
        else:
            no_progress = 0

    print(f"\n📊 Резюме: ✅ {total_success} успішно, ❌ {total_fail} помилок ({batch_no} батч(ів)).")
    print(f"📈 LLM budget: {budget_summary()}")


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
