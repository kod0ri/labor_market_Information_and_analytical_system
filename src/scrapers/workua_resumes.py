"""
Перша стадія ETL: HTML-скрапінг резюме work.ua у staging.raw_resumes.

Дзеркальна структура до workua_vacancies.py (той самий алгоритм пагінації
й дедуплікації), відрізняється лише таблицею/полями та тим, що work.ua -
ЄДИНЕ з трьох джерел, яке взагалі віддає резюме (robota.ua ховає CVdb за
пейволом, DOU.ua резюме не має, лише вакансії).
"""

import asyncio
import json
import os

import aiohttp
from bs4 import BeautifulSoup

from src.db.database import AsyncDatabasePool
from src.scrapers.categories import active_categories
from src.scrapers.utils import fetch_html, parse_card_links

BASE_URL = "https://www.work.ua"
# Ліміт сторінок НА КАТЕГОРІЮ (рубрик ~14) — див. коментар у workua_vacancies.
MAX_PAGES = int(os.getenv("WORKUA_RESUMES_MAX_PAGES", "10"))


def _sync_parse_resume(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    title_tag = soup.find("h1")                                # заголовок резюме - завжди єдиний <h1> сторінки
    title = title_tag.text.strip() if title_tag else "Невідоме резюме"
    return {"title": title, "url": url}


def _sync_parse_list_page(list_html: str) -> dict[str, str]:
    return parse_card_links(list_html, "/resumes/")   # {external_id: url}, шлях-префікс саме /resumes/ (не /jobs/)


async def process_resume_page(
    session: aiohttp.ClientSession,
    url: str,
    external_id: str,
    semaphore: asyncio.Semaphore,
) -> None:
    async with semaphore:                # не більше 10 одночасних запитів (спільний ліміт мережевої ввічливості)
        html = await fetch_html(session, url)
        if not html:
            return

        parsed_data = await asyncio.to_thread(_sync_parse_resume, html, url)
        raw_json = json.dumps(parsed_data, ensure_ascii=False)   # {title, url} для колонки raw_json

        # Стовпець зветься raw_text, але сюди пишеться ПОВНИЙ HTML сторінки -
        # текст із розмітки (BeautifulSoup .get_text) витягується пізніше,
        # на LLM-стадії (prepare_text_for_llm), а не тут; таке саме рішення,
        # як raw_html у staging.raw_vacancies (зберігаємо сирі дані для повторної обробки).
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


async def _scrape_category(
    session: aiohttp.ClientSession,
    slug: str,
    category_label: str,
    semaphore: asyncio.Semaphore,
) -> None:
    page = 1
    while page <= MAX_PAGES:
        url = f"{BASE_URL}/{slug}/?page={page}"    # slug тут - workua_resumes_slug (jobs- замінено на resumes-)
        print(f"\n📄 [{category_label}] резюме, сторінка {page}...")

        list_html = await fetch_html(session, url)
        if not list_html:               # недоступна сторінка - зупиняємо цю категорію
            break

        page_resumes = await asyncio.to_thread(_sync_parse_list_page, list_html)   # {external_id: url} усіх карток
        if not page_resumes:             # порожньо - дійшли до кінця пагінації
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
        existing_ids = {r["external_id"] for r in existing_records}   # set для швидкого "in"-пошуку нижче

        page_tasks = [                              # лише нові резюме отримують задачу на завантаження
            process_resume_page(session, resume_url, ext_id, semaphore)
            for ext_id, resume_url in page_resumes.items()
            if ext_id not in existing_ids
        ]

        if page_tasks:
            await asyncio.gather(*page_tasks)
        else:
            print("   ✨ Нових резюме на цій сторінці не знайдено.")

        page += 1


async def main() -> None:
    await AsyncDatabasePool.initialize()
    semaphore = asyncio.Semaphore(10)
    categories = active_categories()

    async with aiohttp.ClientSession() as session:
        print(f"🔍 work.ua: збір резюме по {len(categories)} категоріях ринку...")
        for cat in categories:
            await _scrape_category(session, cat.workua_resumes_slug, cat.label, semaphore)

    print("\n✅ Скрейпінг резюме завершено.")


if __name__ == "__main__":
    asyncio.run(main())
