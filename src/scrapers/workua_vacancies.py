import asyncio
import json
from typing import Dict, Any

import aiohttp
from bs4 import BeautifulSoup

from src.db.database import AsyncDatabasePool
from src.scrapers.utils import fetch_html

BASE_URL = "https://www.work.ua"
# days=122: горизонт пошуку вакансій (~4 місяці). Достатньо для охоплення ринку без перегляду архіву.
SEARCH_URL = f"{BASE_URL}/jobs-it/?days=122"


def _sync_parse_vacancy(html: str, url: str) -> Dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")

    title_tag = soup.find("h1")
    title = title_tag.text.strip() if title_tag else "Невідома посада"

    company_tag = soup.find("a", class_="inline-block mb-sm")
    company = company_tag.text.strip() if company_tag else ""

    return {"title": title, "company": company, "url": url}


async def process_vacancy_page(
    session: aiohttp.ClientSession,
    url: str,
    external_id: str,
    semaphore: asyncio.Semaphore,
) -> None:
    async with semaphore:
        html = await fetch_html(session, url)
        if not html:
            return

        parsed_data = await asyncio.to_thread(_sync_parse_vacancy, html, url)
        raw_json = json.dumps(parsed_data, ensure_ascii=False)

        query = """
            INSERT INTO staging.raw_vacancies (source_name, external_id, search_category, raw_html, raw_json)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (source_name, external_id) DO NOTHING
            RETURNING id;
        """

        async with AsyncDatabasePool.get_connection() as conn:
            inserted_id = await conn.fetchval(query, "work.ua", external_id, "IT", html, raw_json)
            if inserted_id:
                print(f"   📥 Нова вакансія: {parsed_data['title'][:40]}...")


def _sync_parse_list_page(list_html: str) -> Dict[str, str]:
    soup = BeautifulSoup(list_html, "lxml")
    cards = soup.find_all("div", class_="card-hover")

    page_jobs: Dict[str, str] = {}
    if not cards:
        return page_jobs

    for card in cards:
        link_tag = card.find("a", href=True)
        if not link_tag:
            continue

        href = link_tag.get("href")
        if isinstance(href, str) and href.startswith("/jobs/"):
            parts = href.split("/")
            if len(parts) > 2:
                external_id = parts[2]
                page_jobs[external_id] = f"{BASE_URL}{href}"

    return page_jobs


async def main() -> None:
    await AsyncDatabasePool.initialize()

    semaphore = asyncio.Semaphore(10)

    async with aiohttp.ClientSession() as session:
        print("🔍 Починаємо збір вакансій...")
        page = 1
        max_pages = 50

        while page <= max_pages:
            url = f"{SEARCH_URL}&page={page}"
            print(f"\n📄 Обробка вакансій, сторінка {page}...")

            list_html = await fetch_html(session, url)
            if not list_html:
                break

            page_jobs = await asyncio.to_thread(_sync_parse_list_page, list_html)
            if not page_jobs:
                break

            external_ids = list(page_jobs.keys())

            # З'єднання береться і повертається в пул після кожної сторінки.
            async with AsyncDatabasePool.get_connection() as conn:
                existing_records = await conn.fetch(
                    """
                    SELECT external_id
                    FROM staging.raw_vacancies
                    WHERE source_name = $1 AND external_id = ANY($2::varchar[]);
                    """,
                    "work.ua",
                    external_ids,
                )
            existing_ids = {record["external_id"] for record in existing_records}

            page_tasks = [
                process_vacancy_page(session, job_url, ext_id, semaphore)
                for ext_id, job_url in page_jobs.items()
                if ext_id not in existing_ids
            ]

            if page_tasks:
                await asyncio.gather(*page_tasks)
            else:
                print("   ✨ Нових вакансій на цій сторінці не знайдено.")

            page += 1

    print("\n✅ Скрейпінг вакансій завершено.")


if __name__ == "__main__":
    asyncio.run(main())
