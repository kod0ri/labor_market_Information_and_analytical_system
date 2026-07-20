"""
Збір вакансій з robota.ua через публічний GraphQL API (dracula.robota.ua).
Проходимо всі категорії ринку з довідника src.scrapers.categories (не лише IT).

robota.ua — український job-борд (не російський), повнопольне джерело як work.ua:
дає назву, місто, зарплату, компанію та повний HTML-опис вакансії. Опис кладемо
у staging.raw_html → LLM на етапі 2 витягує навички, досвід, рівень англійської.
Тобто robota.ua йде тим самим LLM-шляхом, що й work.ua/DOU, і дає повну статистику.

Сайт за Cloudflare — потрібні браузерні заголовки (User-Agent/Origin/Referer),
інакше повертається челендж «Just a moment…».

Резюме (CVdb) на robota.ua доступні лише платним роботодавцям (потрібна авторизація),
тому тут збираємо ЛИШЕ вакансії; резюме лишаються за work.ua.
"""

import asyncio
import json
import os
from typing import Any

import aiohttp

from src.db.database import AsyncDatabasePool
from src.scrapers.categories import active_categories

GRAPHQL_URL = "https://dracula.robota.ua/"

# Період максимально доступний у публічному фільтрі — останній місяць.
PERIOD = "MONTH"
PAGE_SIZE = int(os.getenv("ROBOTA_PAGE_SIZE", "40"))
# Ліміт сторінок НА РУБРИКУ: рубрик ~14, тож дефолт нижчий, ніж за часів
# IT-only збору (25), щоб прогін лишався порівнянним за обсягом.
MAX_PAGES = int(os.getenv("ROBOTA_MAX_PAGES", "5"))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Content-Type": "application/json",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "uk-UA,uk;q=0.9",
    "Origin": "https://robota.ua",
    "Referer": "https://robota.ua/",
}

SEARCH_QUERY = """
query PublishedVacancies($filter: PublishedVacanciesFilterInput!, $pagination: PublishedVacanciesPaginationInput!) {
  publishedVacancies(filter: $filter, pagination: $pagination) {
    totalCount
    items {
      id
      title
      fullDescription
      city { ua }
      salary { amountFrom amountTo currency }
      company { name }
    }
  }
}
"""


def _salary_str(salary: dict[str, Any] | None) -> str:
    """Будує текстовий хінт зарплати для LLM (0/0 → невказана)."""
    if not salary:                        # у GraphQL-відповіді поле salary взагалі відсутнє
        return ""
    lo = salary.get("amountFrom") or 0    # 0, якщо мінімум не вказаний роботодавцем
    hi = salary.get("amountTo") or 0      # 0, якщо максимум не вказаний
    cur = salary.get("currency") or "UAH"  # дефолт - гривня
    if lo and hi:                          # вказано і мінімум, і максимум
        return f"{lo}-{hi} {cur}"
    if hi:                                  # лише "до"
        return f"до {hi} {cur}"
    if lo:                                  # лише "від"
        return f"від {lo} {cur}"
    return ""                                # обидва 0 - зарплата не вказана взагалі


async def _fetch_page(
    session: aiohttp.ClientSession, rubric_id: str, page: int, retries: int = 3
) -> dict[str, Any] | None:
    """Один GraphQL-запит однієї сторінки однієї рубрики. Повертає сирий
    об'єкт `publishedVacancies` (totalCount + items) або None при невдачі
    (мережа/429/GraphQL-помилка) - виклики нижче трактують None як кінець списку."""
    payload = {
        "query": SEARCH_QUERY,
        "variables": {
            "filter": {
                "rubrics": {"id": rubric_id, "subrubricIds": []},
                "period": PERIOD,
                "showWithoutSalary": True,
            },
            "pagination": {"page": page, "count": PAGE_SIZE},
        },
    }
    for attempt in range(retries):
        try:
            async with session.post(
                GRAPHQL_URL, headers=HEADERS, json=payload,      # HEADERS - браузероподібні, інакше Cloudflare-челендж
                timeout=aiohttp.ClientTimeout(total=25),
            ) as resp:
                if resp.status == 429:                            # rate-limit - зростаюча пауза, як і в work.ua-скрапері
                    await asyncio.sleep(5 * (attempt + 1))
                    continue
                if resp.status != 200:                            # будь-яка інша неуспішна HTTP-відповідь
                    print(f"   ❌ robota.ua HTTP {resp.status} (сторінка {page})")
                    if attempt == retries - 1:
                        return None
                    await asyncio.sleep(2 ** attempt)               # експоненційний backoff
                    continue
                data = await resp.json()               # GraphQL завжди повертає 200, помилки - усередині тіла
                if data.get("errors"):                  # перевіряємо саме GraphQL-рівень помилок
                    print(f"   ❌ GraphQL помилка: {data['errors'][0].get('message')}")
                    return None
                return data.get("data", {}).get("publishedVacancies")   # корисне навантаження відповіді
        except Exception as e:
            if attempt == retries - 1:
                print(f"   ❌ Мережа robota.ua (сторінка {page}): {e}")
                return None
            await asyncio.sleep(2 ** attempt)
    return None


async def _scrape_rubric(
    session: aiohttp.ClientSession, rubric_id: str, category_label: str
) -> int:
    """Проходить одну рубрику, повертає кількість доданих у staging вакансій."""
    first = await _fetch_page(session, rubric_id, 0)   # перша сторінка одразу дає й totalCount для логів
    if not first:
        print(f"   ⚠️ [{category_label}] порожня відповідь — пропускаємо рубрику.")
        return 0

    total = first.get("totalCount") or 0     # орієнтовна загальна кількість вакансій рубрики (лише для логу)
    print(f"   📊 [{category_label}] ~{total} вакансій за останній місяць.")

    inserted = 0        # скільки НОВИХ рядків реально додано в staging для цієї рубрики
    page = 0
    while page < MAX_PAGES:
        block = first if page == 0 else await _fetch_page(session, rubric_id, page)   # перевикористовуємо вже отриману 1-шу сторінку
        items = (block or {}).get("items") or []    # список вакансій цієї сторінки (порожньо, якщо block=None)
        if not items:
            break

        external_ids = [str(it["id"]) for it in items]   # robota.ua id - число, приводимо до рядка під колонку varchar
        async with AsyncDatabasePool.get_connection() as conn:
            existing = await conn.fetch(
                """
                SELECT external_id FROM staging.raw_vacancies
                WHERE source_name = $1 AND external_id = ANY($2::varchar[]);
                """,
                "robota.ua", external_ids,
            )
        existing_ids = {r["external_id"] for r in existing}   # set для швидкого "in"-пошуку нижче

        new_rows = [it for it in items if str(it["id"]) not in existing_ids]   # лише справді нові вакансії
        if new_rows:
            async with AsyncDatabasePool.get_connection() as conn:
                for it in new_rows:
                    raw_html = it.get("fullDescription") or ""    # повний HTML-опис - те, що обробить LLM
                    if not raw_html.strip():                       # порожній опис - запис марний для NLP-стадії
                        continue
                    raw_json = json.dumps({
                        "title": it.get("title", ""),
                        "company": (it.get("company") or {}).get("name", ""),   # company може бути null у відповіді
                        "location": (it.get("city") or {}).get("ua", ""),        # city теж може бути null
                        "salary": _salary_str(it.get("salary")),                  # текстовий хінт для LLM-промпту
                    }, ensure_ascii=False)
                    ins_id = await conn.fetchval(
                        """
                        INSERT INTO staging.raw_vacancies
                            (source_name, external_id, search_category, raw_html, raw_json)
                        VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT (source_name, external_id) DO NOTHING
                        RETURNING id;
                        """,
                        "robota.ua", str(it["id"]), category_label, raw_html, raw_json,
                    )
                    if ins_id:
                        inserted += 1
        else:
            print(f"   ✨ [{category_label}] сторінка {page}: нових вакансій немає.")

        page += 1

    return inserted


async def main() -> None:
    """Точка входу: послідовно обходить усі активні рубрики ринку (не лише IT)."""
    await AsyncDatabasePool.initialize()

    categories = active_categories()
    inserted_total = 0
    async with aiohttp.ClientSession() as session:
        print(f"🔍 robota.ua: збір вакансій через GraphQL ({len(categories)} рубрик)...")
        for cat in categories:
            inserted_total += await _scrape_rubric(session, cat.robota_rubric_id, cat.label)

    print(f"✅ robota.ua: додано {inserted_total} нових вакансій у staging (далі — LLM).")


if __name__ == "__main__":
    asyncio.run(main())
