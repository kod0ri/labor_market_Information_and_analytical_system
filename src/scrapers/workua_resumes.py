import asyncio
import json

import aiohttp
from bs4 import BeautifulSoup

from src.db.database import AsyncDatabasePool
from src.scrapers.utils import fetch_html, parse_card_links

BASE_URL = "https://www.work.ua"
SEARCH_URL = f"{BASE_URL}/resumes-it/"


def _sync_parse_resume(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    title_tag = soup.find("h1")
    title = title_tag.text.strip() if title_tag else "Невідоме резюме"
    return {"title": title, "url": url}


def _sync_parse_list_page(list_html: str) -> dict[str, str]:
    return parse_card_links(list_html, "/resumes/")


async def process_resume_page(
    session: aiohttp.ClientSession,
    url: str,
    external_id: str,
    semaphore: asyncio.Semaphore,
) -> None:
    async with semaphore:
        html = await fetch_html(session, url)
        if not html:
            return

        parsed_data = await asyncio.to_thread(_sync_parse_resume, html, url)
        raw_json = json.dumps(parsed_data, ensure_ascii=False)

        query = """
            INSERT INTO staging.raw_resumes
                (source_name, external_id, raw_text, raw_json)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (source_name, external_id) DO NOTHING
            RETURNING id;
        """
        async with AsyncDatabasePool.get_connection() as conn:
            inserted_id = await conn.fetchval(
                query, "work.ua", external_id, html, raw_json
            )
            if inserted_id:
                print(f"   📥 Нове резюме: {parsed_data['title'][:40]}...")


async def main() -> None:
    await AsyncDatabasePool.initialize()
    semaphore = asyncio.Semaphore(10)

    async with aiohttp.ClientSession() as session:
        print("🔍 Починаємо збір резюме...")
        page = 1
        max_pages = 50

        while page <= max_pages:
            url = f"{SEARCH_URL}?page={page}"
            print(f"\n📄 Обробка резюме, сторінка {page}...")

            list_html = await fetch_html(session, url)
            if not list_html:
                break

            page_resumes = await asyncio.to_thread(_sync_parse_list_page, list_html)
            if not page_resumes:
                break

            external_ids = list(page_resumes.keys())

            # З'єднання береться і повертається в пул після кожної сторінки.
            async with AsyncDatabasePool.get_connection() as conn:
                existing_records = await conn.fetch(
                    """
                    SELECT external_id FROM staging.raw_resumes
                    WHERE source_name = $1 AND external_id = ANY($2::varchar[]);
                    """,
                    "work.ua", external_ids,
                )
            existing_ids = {r["external_id"] for r in existing_records}

            page_tasks = [
                process_resume_page(session, resume_url, ext_id, semaphore)
                for ext_id, resume_url in page_resumes.items()
                if ext_id not in existing_ids
            ]

            if page_tasks:
                await asyncio.gather(*page_tasks)
            else:
                print("   ✨ Нових резюме на цій сторінці не знайдено.")

            page += 1

    print("\n✅ Скрейпінг резюме завершено.")


if __name__ == "__main__":
    asyncio.run(main())
