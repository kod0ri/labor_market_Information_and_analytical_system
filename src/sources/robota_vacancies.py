"""
Збір IT-вакансій з robota.ua через публічний GraphQL API (dracula.robota.ua).

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

GRAPHQL_URL = "https://dracula.robota.ua/"

# rubrics.id = "1" → рубрика «IT, комп'ютери, інтернет» на robota.ua.
RUBRIC_IT = "1"
# Період максимально доступний у публічному фільтрі — останній місяць.
PERIOD = "MONTH"
PAGE_SIZE = int(os.getenv("ROBOTA_PAGE_SIZE", "40"))
# ~PAGE_SIZE×MAX_PAGES вакансій за прогін; staging дешевий, LLM бере по 100/раз.
MAX_PAGES = int(os.getenv("ROBOTA_MAX_PAGES", "25"))

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
    if not salary:
        return ""
    lo = salary.get("amountFrom") or 0
    hi = salary.get("amountTo") or 0
    cur = salary.get("currency") or "UAH"
    if lo and hi:
        return f"{lo}-{hi} {cur}"
    if hi:
        return f"до {hi} {cur}"
    if lo:
        return f"від {lo} {cur}"
    return ""


async def _fetch_page(session: aiohttp.ClientSession, page: int, retries: int = 3) -> dict[str, Any] | None:
    payload = {
        "query": SEARCH_QUERY,
        "variables": {
            "filter": {
                "rubrics": {"id": RUBRIC_IT, "subrubricIds": []},
                "period": PERIOD,
                "showWithoutSalary": True,
            },
            "pagination": {"page": page, "count": PAGE_SIZE},
        },
    }
    for attempt in range(retries):
        try:
            async with session.post(
                GRAPHQL_URL, headers=HEADERS, json=payload,
                timeout=aiohttp.ClientTimeout(total=25),
            ) as resp:
                if resp.status == 429:
                    await asyncio.sleep(5 * (attempt + 1))
                    continue
                if resp.status != 200:
                    print(f"   ❌ robota.ua HTTP {resp.status} (сторінка {page})")
                    if attempt == retries - 1:
                        return None
                    await asyncio.sleep(2 ** attempt)
                    continue
                data = await resp.json()
                if data.get("errors"):
                    print(f"   ❌ GraphQL помилка: {data['errors'][0].get('message')}")
                    return None
                return data.get("data", {}).get("publishedVacancies")
        except Exception as e:
            if attempt == retries - 1:
                print(f"   ❌ Мережа robota.ua (сторінка {page}): {e}")
                return None
            await asyncio.sleep(2 ** attempt)
    return None


async def main() -> None:
    await AsyncDatabasePool.initialize()

    inserted_total = 0
    async with aiohttp.ClientSession() as session:
        print("🔍 robota.ua: збір IT-вакансій через GraphQL...")

        first = await _fetch_page(session, 0)
        if not first:
            print("   ⚠️ robota.ua недоступна або порожня відповідь — пропускаємо джерело.")
            return

        total = first.get("totalCount") or 0
        print(f"   📊 Знайдено ~{total} IT-вакансій за останній місяць.")

        page = 0
        while page < MAX_PAGES:
            block = first if page == 0 else await _fetch_page(session, page)
            items = (block or {}).get("items") or []
            if not items:
                break

            external_ids = [str(it["id"]) for it in items]
            async with AsyncDatabasePool.get_connection() as conn:
                existing = await conn.fetch(
                    """
                    SELECT external_id FROM staging.raw_vacancies
                    WHERE source_name = $1 AND external_id = ANY($2::varchar[]);
                    """,
                    "robota.ua", external_ids,
                )
            existing_ids = {r["external_id"] for r in existing}

            new_rows = [it for it in items if str(it["id"]) not in existing_ids]
            if new_rows:
                async with AsyncDatabasePool.get_connection() as conn:
                    for it in new_rows:
                        raw_html = it.get("fullDescription") or ""
                        if not raw_html.strip():
                            continue
                        raw_json = json.dumps({
                            "title": it.get("title", ""),
                            "company": (it.get("company") or {}).get("name", ""),
                            "location": (it.get("city") or {}).get("ua", ""),
                            "salary": _salary_str(it.get("salary")),
                        }, ensure_ascii=False)
                        ins_id = await conn.fetchval(
                            """
                            INSERT INTO staging.raw_vacancies
                                (source_name, external_id, search_category, raw_html, raw_json)
                            VALUES ($1, $2, $3, $4, $5)
                            ON CONFLICT (source_name, external_id) DO NOTHING
                            RETURNING id;
                            """,
                            "robota.ua", str(it["id"]), "IT", raw_html, raw_json,
                        )
                        if ins_id:
                            inserted_total += 1
            else:
                print(f"   ✨ Сторінка {page}: нових вакансій немає.")

            page += 1

    print(f"✅ robota.ua: додано {inserted_total} нових вакансій у staging (далі — LLM).")


if __name__ == "__main__":
    asyncio.run(main())
