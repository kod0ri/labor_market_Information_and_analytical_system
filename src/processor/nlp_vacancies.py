import os
import json
import re
import asyncio
from bs4 import BeautifulSoup
from pydantic import ValidationError
from groq import AsyncGroq
from dotenv import load_dotenv

from src.db.database import AsyncDatabasePool
from src.processor.schemas import VacancySchema
from src.processor.skill_normalizer import resolve_skill_id
from src.processor.failure_tracker import record_failure, mark_resolved

load_dotenv()
client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))

# TPM ліміт Groq free tier = 6000 tokens/хв
# ~850 input + ~250 output = ~1100 tokens/запит
# Безпечний паралелізм: 6000 / 1100 ≈ 5, беремо 3 з запасом
GROQ_SEMAPHORE_SIZE = 3

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
    "region": "Київська область"
}
УВАГА: skills - це ЗАВЖДИ масив об'єктів (БЕЗ вказання досвіду для кожної навички, тільки name та category), min_salary та max_salary - це ЗАВЖДИ цілі числа (не рядки).
"""


def prepare_text_for_llm(raw_text: str | None) -> str:
    if not raw_text:
        return ""
    text = BeautifulSoup(raw_text, "html.parser").get_text(separator=" ", strip=True)
    return text[:1500]


async def get_or_create_company(conn, name, industry, website, cache, cache_lock):
    if not name:
        return None
    name = name[:200]

    async with cache_lock:
        if name in cache["companies"]:
            return cache["companies"][name]

        comp_id = await conn.fetchval(
            """
            INSERT INTO dictionaries.companies (name, industry, website_url) VALUES ($1, $2, $3)
            ON CONFLICT (name) DO UPDATE
                SET industry    = COALESCE(dictionaries.companies.industry, EXCLUDED.industry),
                    website_url = COALESCE(dictionaries.companies.website_url, EXCLUDED.website_url)
            RETURNING id;
            """,
            name, industry, website,
        )
        if not comp_id:
            comp_id = await conn.fetchval(
                "SELECT id FROM dictionaries.companies WHERE name = $1;", name
            )

        cache["companies"][name] = comp_id
        return comp_id


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


async def process_single_vacancy(record, cache, cache_lock, semaphore):
    staging_id    = record["id"]
    raw_html      = record["raw_html"]
    raw_json      = (
        record["raw_json"]
        if isinstance(record["raw_json"], dict)
        else json.loads(record["raw_json"] or "{}")
    )

    title         = raw_json.get("title", "Невідома посада")
    company_name  = raw_json.get("company", "")
    location_name = raw_json.get("location", "")
    raw_salary    = raw_json.get("salary", "")

    # Стрипаємо HTML один раз — далі працюємо тільки з текстом
    safe_text = prepare_text_for_llm(raw_html)
    prompt    = f"Текст вакансії:\n{safe_text}\n\nВказана зарплата: {raw_salary}"

    max_attempts = 5
    for attempt in range(max_attempts):
        try:
            async with semaphore:
                chat_completion = await client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": SYSTEM_INSTRUCTION},
                        {"role": "user",   "content": prompt},
                    ],
                    model="llama-3.1-8b-instant",
                    temperature=0,
                    response_format={"type": "json_object"},
                )

            response_text = chat_completion.choices[0].message.content
            if not response_text:
                raise ValueError("Отримано порожню відповідь від LLM")

            match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if not match:
                raise ValueError("LLM не повернула валідний JSON об'єкт")

            ai_data = VacancySchema.model_validate_json(match.group(0))

            final_company  = ai_data.company_name  or company_name
            final_location = ai_data.location_name or location_name

            async with AsyncDatabasePool.get_connection() as conn:
                async with conn.transaction():
                    comp_id = await get_or_create_company(
                        conn, final_company, ai_data.company_industry,
                        ai_data.website_url, cache, cache_lock,
                    )
                    loc_id = await get_or_create_location(
                        conn, final_location, ai_data.region, cache, cache_lock,
                    )

                    new_vacancy_id = await conn.fetchval(
                        """
                        INSERT INTO core.vacancies
                            (staging_id, title, company_id, location_id,
                             min_salary, max_salary, currency,
                             experience_years, english_level)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                        RETURNING id;
                        """,
                        staging_id, str(title)[:200], comp_id, loc_id,
                        ai_data.min_salary, ai_data.max_salary, ai_data.currency,
                        ai_data.experience_years, ai_data.english_level,
                    )

                    for skill in ai_data.skills:
                        skill_id = await resolve_skill_id(
                            conn, skill.name, skill.category, cache, cache_lock,
                        )
                        if skill_id:
                            await conn.execute(
                                "INSERT INTO core.vacancy_skills (vacancy_id, skill_id) "
                                "VALUES ($1, $2) ON CONFLICT DO NOTHING;",
                                new_vacancy_id, skill_id,
                            )

                    # ✅ Пункт 4: очищаємо raw_html одразу після успішного парсингу.
                    # Структуровані дані вже в core.vacancies — сирий HTML більше не потрібен.
                    # Економія: ~50-200 KB × кількість записів = суттєво для диску.
                    await conn.execute(
                        "UPDATE staging.raw_vacancies SET raw_html = NULL WHERE id = $1;",
                        staging_id,
                    )

                    # ✅ Пункт 5: якщо цей запис раніше падав — знімаємо позначку помилки
                    await mark_resolved(conn, "vacancy", staging_id)

            print(f"   💾 Успішно: [ID {staging_id}] {str(title)[:30]}...")
            return True

        except ValidationError as ve:
            failed_fields = [str(err.get("loc", [""])[0]) for err in ve.errors()]
            detail = f"fields={failed_fields}"
            print(
                f"   ⚠️ [ID {staging_id}] Галюцинація LLM "
                f"(спроба {attempt + 1}/{max_attempts}). {detail}"
            )
            if attempt == max_attempts - 1:
                async with AsyncDatabasePool.get_connection() as conn:
                    await record_failure(
                        conn, "vacancy", staging_id, "validation", detail, attempt + 1,
                    )
            await asyncio.sleep(1)

        except Exception as e:
            is_rate_limit = "429" in str(e) or "rate_limit" in str(e).lower()

            if is_rate_limit:
                wait = min(60, 5 * (2 ** attempt))
                print(
                    f"   ⏳ [ID {staging_id}] Rate limit "
                    f"(спроба {attempt + 1}/{max_attempts}). Чекаємо {wait}s..."
                )
                await asyncio.sleep(wait)
            else:
                print(f"   ❌ [ID {staging_id}] Невідновлювана помилка: {e}")
                async with AsyncDatabasePool.get_connection() as conn:
                    await record_failure(
                        conn, "vacancy", staging_id, "unknown", str(e), attempt + 1,
                    )
                return False

    # Вичерпали всі спроби — фіксуємо фінальну помилку
    print(f"   💀 [ID {staging_id}] Вичерпано всі {max_attempts} спроби. Пропускаємо.")
    async with AsyncDatabasePool.get_connection() as conn:
        await record_failure(
            conn, "vacancy", staging_id,
            "validation", f"Exhausted {max_attempts} attempts", max_attempts,
        )
    return False


async def main():
    await AsyncDatabasePool.initialize()
    cache = {"companies": {}, "locations": {}, "skills": {}}
    cache_lock = asyncio.Lock()
    semaphore  = asyncio.Semaphore(GROQ_SEMAPHORE_SIZE)

    async with AsyncDatabasePool.get_connection() as conn:
        records = await conn.fetch(
            """
            SELECT s.id, s.external_id, s.raw_html, s.raw_json
            FROM staging.raw_vacancies s
            LEFT JOIN core.vacancies c ON s.id = c.staging_id
            -- ✅ Пункт 5: пропускаємо записи що вже падали і ще не виправлені
            LEFT JOIN staging.failed_records f
                   ON f.staging_id  = s.id
                  AND f.record_type = 'vacancy'
                  AND f.is_resolved = FALSE
            WHERE s.raw_html IS NOT NULL
              AND s.raw_html != ''
              AND c.id IS NULL
              AND f.id IS NULL
            LIMIT 100;
            """
        )

    if not records:
        print("⚠️ Немає нових вакансій для обробки.")
        return

    print(
        f"🚀 Старт ASYNC обробки {len(records)} вакансій "
        f"(Groq + Pydantic, паралелізм={GROQ_SEMAPHORE_SIZE})..."
    )
    tasks = [
        process_single_vacancy(record, cache, cache_lock, semaphore)
        for record in records
    ]
    results = await asyncio.gather(*tasks)

    success = sum(1 for r in results if r)
    failed  = len(results) - success
    print(f"\n📊 Результат: ✅ {success} успішно, ❌ {failed} помилок.")


if __name__ == "__main__":
    asyncio.run(main())