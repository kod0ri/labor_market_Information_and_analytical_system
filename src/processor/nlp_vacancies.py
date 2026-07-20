"""
Друга стадія ETL: NLP-збагачення сирих вакансій зі staging.raw_vacancies.

Бере необроблені записи (raw_html IS NOT NULL), проганяє текст через LLM-каскад
(llm_cascade.complete, з fallback між провайдерами), валідує вивід схемою
VacancySchema і пише результат у core.vacancies + core.vacancy_skills.
Оркестрація одного запису (retry/помилки/каскад) винесена в nlp_pipeline.run_llm_record -
тут лишається лише специфіка вакансій: сам промпт і крок persist у БД.
"""

import os
import json
import asyncio
from dotenv import load_dotenv

from src.db.database import AsyncDatabasePool
from src.processor.schemas import VacancySchema
from src.processor.skill_normalizer import resolve_skill_id
from src.processor.failure_tracker import mark_resolved
from src.processor.nlp_pipeline import run_llm_record
from src.processor.llm_cascade import (
    any_available,
    budget_summary,
    cascade_summary,
)
from src.processor.llm_utils import (
    prepare_text_for_llm,
    get_or_create_company,
    get_or_create_location,
    get_or_create_source,
)

load_dotenv()

# Скільки записів за один прогін (vacancies + resumes беруть по стільки кожен).
# Підвищуй під частоту cron, щоб вибирати денну стелю провайдерів.
BATCH_LIMIT = int(os.getenv("NLP_BATCH_LIMIT", "200"))

# Скільки записів обробляються ОДНОЧАСНО. Каскад тримає лише ~24 запити/хв
# сумарно на всіх провайдерів (Cerebras 5RPM + Groq 7RPM + Gemini 12RPM);
# запуск усіх 200 задач разом (стара поведінка) означав, що сотні задач
# одночасно тарабанили у той самий TokenBucketRateLimiter і, щойно один
# провайдер ловив 429, одразу «прокидались» юрбою й повторно зносили
# кулдаун — звідси затяжні паузи «Усі провайдери зайняті». Малий семафор
# лишає каскад так само насиченим, але без ефекту юрби.
LLM_CONCURRENCY = int(os.getenv("NLP_LLM_CONCURRENCY", "6"))

SYSTEM_INSTRUCTION = """
Ти професійний IT-аналітик та Data Engineer. Твоє завдання: проаналізувати текст вакансії.
Поверни ВИКЛЮЧНО валідний JSON. ЗАБОРОНЕНО писати будь-який інший текст.

СХЕМА JSON (суворо дотримуйся цих типів даних, якщо даних немає - пиши null):
{
    "company_name": "Назва компанії",
    "location_name": "Київ",
    "skills": [ {"name": "Python", "category": "Hard"} ],
    "experience_years": 2,
    "english_level": "Intermediate",
    "min_salary": 20000,
    "max_salary": 40000,
    "currency": "UAH",
    "company_industry": "IT",
    "website_url": "https://example.com",
    "region": "Київська область",
    "it_related": true
}
ПРАВИЛА:
- skills — ЗАВЖДИ масив об'єктів {name, category}. min_salary та max_salary — ЗАВЖДИ цілі числа.
- category навички: "Hard" — технічні (мови, інструменти, технології), "Soft" — особистісні (комунікація, лідерство, ініціативність, відповідальність тощо).
- it_related — true лише якщо посада реально стосується IT/tech: розробка, QA, DevOps, data, безпека, підтримка інфраструктури, IT-менеджмент, дизайн цифрових продуктів. Маркетинг/SMM/таргет, продажі, контент і копірайтинг, ведення соцмереж, механічне/будівельне конструювання (AutoCAD, SolidWorks) — false.
- currency — ТІЛЬКИ код ISO 4217: UAH, USD, EUR. Якщо написано "грн" або "гривня" — пиши UAH.
- english_level — ТІЛЬКИ одне зі значень: Beginner, Elementary, Pre-Intermediate, Intermediate, Upper-Intermediate, Advanced, Fluent, Native. CEFR коди конвертуй: A1→Beginner, A2→Elementary, B1→Pre-Intermediate, B2→Upper-Intermediate, C1→Advanced, C2→Fluent. Якщо не знайдено — пиши null.
"""


async def process_single_vacancy(
    record, cache: dict, cache_lock: asyncio.Lock,
    db_semaphore: asyncio.Semaphore,
) -> bool:
    """Обробляє один сирий запис вакансії: LLM-екстракція → persist у core.*.

    `cache`/`cache_lock` - спільний на весь прогін словник company/location/
    skill/source id, щоб уникнути повторних SELECT-ів get_or_create для тих
    самих назв у різних вакансіях цього ж батчу.
    """
    staging_id = record["id"]              # первинний ключ staging.raw_vacancies - для UPDATE/FK нижче
    source_name = record["source_name"]    # "work.ua"/"dou.ua"/"robota.ua" - для дов. sources

    raw_html = record["raw_html"]          # повний HTML/опис вакансії, зібраний скрапером
    raw_json = (
        record["raw_json"]                                    # asyncpg вже міг сам розпарсити JSONB у dict
        if isinstance(record["raw_json"], dict)
        else json.loads(record["raw_json"] or "{}")           # інакше парсимо рядок вручну (порожній → {})
    )

    title = raw_json.get("title", "Невідома посада")     # заголовок з картки скрапера (фолбек для persist)
    company_name = raw_json.get("company", "")           # назва компанії з картки (фолбек, якщо LLM не знайде)
    location_name = raw_json.get("location", "")         # місто з картки (фолбек)
    raw_salary = raw_json.get("salary", "")               # текстовий хінт зарплати з картки, як підказка LLM

    safe_text = await prepare_text_for_llm(raw_html)      # очищений від HTML-тегів текст, обрізаний під ліміт токенів
    prompt = f"Текст вакансії:\n{safe_text}\n\nВказана зарплата: {raw_salary}"   # промпт для LLM
    messages = [
        {"role": "system", "content": SYSTEM_INSTRUCTION},   # незмінна інструкція зі схемою JSON і правилами
        {"role": "user", "content": prompt},                  # власне текст цієї конкретної вакансії
    ]

    async def _persist(conn, ai_data: VacancySchema) -> str:
        # Фолбек: якщо LLM не витягла компанію/локацію з тексту (null), беремо
        # значення, яке скрапер уже мав у raw_json з картки оголошення.
        final_company = ai_data.company_name or company_name
        final_location = ai_data.location_name or location_name

        comp_id = await get_or_create_company(       # id рядка в dictionaries.companies (створює за потреби)
            conn, final_company, ai_data.company_industry,
            ai_data.website_url, cache, cache_lock,
        )
        loc_id = await get_or_create_location(        # id рядка в dictionaries.locations
            conn, final_location, ai_data.region, cache, cache_lock,
        )
        src_id = await get_or_create_source(conn, source_name, cache, cache_lock)  # id рядка в dictionaries.sources
        new_vacancy_id = await conn.fetchval(   # вставляємо структурований запис і одразу отримуємо його id
            """
            INSERT INTO core.vacancies
                (staging_id, title, company_id, location_id, source_id,
                 min_salary, max_salary, currency,
                 experience_years, english_level, it_related)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            RETURNING id;
            """,
            staging_id, str(title)[:200], comp_id, loc_id, src_id,
            ai_data.min_salary, ai_data.max_salary, ai_data.currency,
            ai_data.experience_years, ai_data.english_level, ai_data.it_related,
        )
        for skill in ai_data.skills:                    # список SkillSchema{name, category}, який повернула LLM
            skill_id = await resolve_skill_id(          # мапить сиру назву на канонічний id (через синоніми)
                conn, skill.name, skill.category, cache, cache_lock,
            )
            if skill_id:                                # None, якщо назва порожня/невалідна - пропускаємо
                await conn.execute(
                    "INSERT INTO core.vacancy_skills (vacancy_id, skill_id) "
                    "VALUES ($1, $2) ON CONFLICT DO NOTHING;",   # ON CONFLICT - та сама пара вже могла існувати
                    new_vacancy_id, skill_id,
                )
        # Сирий HTML більше не потрібен після успішної обробки - обнуляємо,
        # щоб не роздувати staging (він і так лишається джерелом правди по
        # external_id/raw_json, лише важкий текст прибираємо).
        await conn.execute(
            "UPDATE staging.raw_vacancies SET raw_html = NULL WHERE id = $1;",
            staging_id,
        )
        # Якщо запис раніше падав і потрапив у failed_records - позначаємо
        # вирішеним, інакше він назавжди виключений із вибірки WHERE f.id IS NULL нижче.
        await mark_resolved(conn, "vacancy", staging_id)
        return str(title)[:35]

    return await run_llm_record(
        staging_id=staging_id,
        record_type="vacancy",
        messages=messages,
        schema_cls=VacancySchema,
        db_semaphore=db_semaphore,
        persist=_persist,
    )


async def main() -> None:
    """Точка входу drain-режиму: обробляє батчі, поки черга не спорожніє
    або денний бюджет усіх LLM-провайдерів не вичерпається."""
    await AsyncDatabasePool.initialize()
    cache = {"companies": {}, "locations": {}, "skills": {}, "sources": {}}   # спільний кеш get_or_create на весь прогін
    cache_lock = asyncio.Lock()                          # захищає кеш від гонок при паралельних задачах
    db_semaphore = asyncio.Semaphore(15)                  # макс. 15 одночасних з'єднань з БД на запис
    llm_semaphore = asyncio.Semaphore(LLM_CONCURRENCY)    # макс. LLM_CONCURRENCY (типово 6) одночасних LLM-викликів

    print(f"🚀 Обробка вакансій (LLM-каскад: {cascade_summary()})...")
    total_success = total_fail = 0    # лічильники за ввесь прогін (по всіх батчах), для підсумкового звіту
    batch_no = 0                      # номер поточного батчу (для логів і перевірки "перший раз чи ні")
    no_progress = 0                   # скільки батчів ПОСПІЛЬ дали 0 успіхів (детектор глухого кута)

    # Drain-режим: кожен прогін доганяє до стелі — батчі по BATCH_LIMIT, поки
    # черга не спорожніє або денний бюджет усіх провайдерів не вичерпається.
    while True:
        if not any_available():
            print(f"   ⏹️ Денний бюджет провайдерів вичерпано ({budget_summary()}).")
            break

        async with AsyncDatabasePool.get_connection() as conn:
            records = await conn.fetch(
                """
                -- Round-robin по джерелах: беремо найстарший необроблений запис
                -- кожного source_name по черзі (rn=1 усіх джерел, потім rn=2…).
                -- Без цього heap-порядок віддавав би увесь беклог work.ua першим,
                -- і DOU/robota «голодували» б за денним бюджетом каскаду.
                SELECT id, source_name, external_id, raw_html, raw_json
                FROM (
                    SELECT s.id, s.source_name, s.external_id, s.raw_html, s.raw_json,
                           ROW_NUMBER() OVER (
                               PARTITION BY s.source_name ORDER BY s.id
                           ) AS rn
                    FROM staging.raw_vacancies s
                    LEFT JOIN core.vacancies c ON s.id = c.staging_id
                    LEFT JOIN staging.failed_records f
                           ON f.staging_id  = s.id
                          AND f.record_type = 'vacancy'
                          AND f.is_resolved = FALSE
                    WHERE s.raw_html IS NOT NULL
                      AND s.raw_html != ''
                      AND c.id IS NULL
                      AND f.id IS NULL
                ) q
                ORDER BY q.rn, q.source_name
                LIMIT $1;
                """,
                BATCH_LIMIT,
            )

        if not records:
            print("   ✅ Черга вакансій порожня." if batch_no else "⚠️ Немає нових вакансій для обробки.")
            break

        batch_no += 1
        print(f"   📦 Батч {batch_no}: {len(records)} вакансій...")

        async def _bounded(r):                          # обгортка: тримає слот семафора на час обробки ОДНОГО запису
            async with llm_semaphore:
                return await process_single_vacancy(r, cache, cache_lock, db_semaphore)

        results = await asyncio.gather(                 # запускаємо всі задачі батчу одразу (семафор сам обмежить паралелізм)
            *[_bounded(r) for r in records],
            return_exceptions=True,                      # виняток в одній задачі не валить решту gather()
        )
        success = sum(1 for r in results if r is True)  # True повертає run_llm_record лише при успішному persist
        total_success += success
        total_fail += len(results) - success            # усе, що не True (False або виняток) - трактуємо як "не вдалося"

        # Захист від «вхолосту»: два батчі поспіль без жодного успіху (усі в
        # cooldown) → стоп, добере наступний прогін.
        if success == 0:
            no_progress += 1
            if no_progress >= 2:
                print("   ⏹️ Два батчі без прогресу — зупиняємось до наступного прогону.")
                break
        else:
            no_progress = 0

    print(f"\n📊 Вакансії: ✅ {total_success} успішно, ❌ {total_fail} помилок ({batch_no} батч(ів)).")
    print(f"📈 LLM budget: {budget_summary()}")


if __name__ == "__main__":
    asyncio.run(main())
