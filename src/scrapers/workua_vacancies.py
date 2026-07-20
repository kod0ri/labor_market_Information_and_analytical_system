"""
Перша стадія ETL: HTML-скрапінг вакансій work.ua у staging.raw_vacancies.

Для кожної активної категорії (src/scrapers/categories.py) обходить сторінки
пагінації списку вакансій, звіряє знайдені external_id з уже наявними в БД
(щоб не тягнути й не парсити повторно вже зібрані сторінки), і завантажує
лише нові картки. Парсинг тут навмисно "тонкий" (title/company) - глибоке
структуроване вилучення полів (навички/ЗП/досвід) робить LLM-каскад на
другій стадії (src/processor/nlp_vacancies.py) з raw_html, збереженого тут.
"""

import asyncio
import json
import os
from typing import Dict, Any

import aiohttp
from bs4 import BeautifulSoup

from src.db.database import AsyncDatabasePool
from src.scrapers.categories import active_categories
from src.scrapers.utils import fetch_html, parse_card_links

BASE_URL = "https://www.work.ua"
# days=122: горизонт пошуку вакансій (~4 місяці). Достатньо для охоплення ринку без перегляду архіву.
SEARCH_DAYS = 122
# Ліміт сторінок НА КАТЕГОРІЮ: рубрик тепер ~14, тож загальний обсяг прогону
# обмежуємо тут, а не одним великим лімітом як за часів IT-only збору.
MAX_PAGES = int(os.getenv("WORKUA_MAX_PAGES", "10"))


def _sync_parse_vacancy(html: str, url: str) -> Dict[str, Any]:
    """Витягує лише title/company з картки вакансії для швидкого прев'ю в
    логах і фолбеку в nlp_vacancies.py, якщо LLM не розпізнає ці поля.
    Синхронна (BeautifulSoup - CPU-bound), викликається через to_thread."""
    soup = BeautifulSoup(html, "lxml")     # парсер сторінки вакансії

    title_tag = soup.find("h1")             # заголовок посади завжди в єдиному <h1> сторінки
    title = title_tag.text.strip() if title_tag else "Невідома посада"

    company_tag = soup.find("a", class_="inline-block mb-sm")   # посилання на профіль компанії з цим CSS-класом
    company = company_tag.text.strip() if company_tag else ""

    return {"title": title, "company": company, "url": url}   # пишеться в staging.raw_vacancies.raw_json


async def process_vacancy_page(
    session: aiohttp.ClientSession,
    url: str,
    external_id: str,
    category_label: str,
    semaphore: asyncio.Semaphore,
) -> None:
    """Завантажує й зберігає ОДНУ вакансію. semaphore обмежує кількість
    одночасних HTTP-запитів до work.ua (окремо від пізнішого LLM_CONCURRENCY
    на стадії NLP - тут ліміт про мережеву ввічливість, там - про LLM-квоти)."""
    async with semaphore:               # чекаємо вільний "слот" - не більше 10 одночасних запитів (див. main())
        html = await fetch_html(session, url)   # повний HTML сторінки вакансії (None, якщо 404/вичерпані ретраї)
        if not html:
            return

        parsed_data = await asyncio.to_thread(_sync_parse_vacancy, html, url)  # {title, company, url} у окремому потоці
        raw_json = json.dumps(parsed_data, ensure_ascii=False)   # ensure_ascii=False - кирилиця лишається читабельною в БД

        # ON CONFLICT DO NOTHING + RETURNING id: якщо запис уже є (гонка між
        # паралельними задачами чи повторний прогін) - INSERT просто нічого
        # не вставляє і RETURNING віддає порожньо, inserted_id стає None.
        query = """
            INSERT INTO staging.raw_vacancies (source_name, external_id, search_category, raw_html, raw_json)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (source_name, external_id) DO NOTHING
            RETURNING id;
        """

        async with AsyncDatabasePool.get_connection() as conn:
            inserted_id = await conn.fetchval(
                query, "work.ua", external_id, category_label, html, raw_json
            )
            if inserted_id:
                print(f"   📥 Нова вакансія: {parsed_data['title'][:40]}...")


def _sync_parse_list_page(list_html: str) -> Dict[str, str]:
    """{external_id: url} усіх карток вакансій на сторінці списку."""
    return parse_card_links(list_html, "/jobs/")


async def _scrape_category(
    session: aiohttp.ClientSession,
    slug: str,
    category_label: str,
    semaphore: asyncio.Semaphore,
) -> None:
    """Обходить пагінацію ОДНІЄЇ категорії, поки є сторінки (до MAX_PAGES)
    або сторінка порожня/недоступна - обидва випадки трактуються як кінець
    списку для цієї категорії, а не помилка всього прогону."""
    page = 1                        # починаємо з першої сторінки видачі
    while page <= MAX_PAGES:        # обмежуємо глибину пагінації для однієї категорії
        url = f"{BASE_URL}/{slug}/?days={SEARCH_DAYS}&page={page}"   # напр. /jobs-it/?days=122&page=3
        print(f"\n📄 [{category_label}] вакансії, сторінка {page}...")

        list_html = await fetch_html(session, url)
        if not list_html:            # сторінка недоступна (404/мережа) - зупиняємо цю категорію
            break

        page_jobs = await asyncio.to_thread(_sync_parse_list_page, list_html)  # {external_id: url} усіх карток на сторінці
        if not page_jobs:             # список порожній - дійшли до кінця пагінації
            break

        external_ids = list(page_jobs.keys())   # для batch-перевірки, що вже є в БД, нижче

        # Перевіряємо ОДНИМ batch-запитом (ANY($2::varchar[])), які external_id
        # з цієї сторінки вже є в БД, замість окремого SELECT на кожну вакансію -
        # так пропускаємо вже зібрані картки, не витрачаючи на них HTTP-запит.
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
        existing_ids = {record["external_id"] for record in existing_records}   # set - швидка перевірка "in" нижче

        page_tasks = [                                          # створюємо задачу лише для СПРАВДІ нових оголошень
            process_vacancy_page(session, job_url, ext_id, category_label, semaphore)
            for ext_id, job_url in page_jobs.items()
            if ext_id not in existing_ids
        ]

        if page_tasks:
            await asyncio.gather(*page_tasks)   # завантажуємо всі нові картки сторінки паралельно (під семафором)
        else:
            print("   ✨ Нових вакансій на цій сторінці не знайдено.")

        page += 1    # переходимо до наступної сторінки пагінації


async def main() -> None:
    """Точка входу: обходить усі активні категорії (SCRAPE_CATEGORIES з .env
    чи всі 14, якщо не задано) послідовно одна за одною."""
    await AsyncDatabasePool.initialize()

    semaphore = asyncio.Semaphore(10)   # не більше 10 одночасних HTTP-запитів до work.ua (мережева ввічливість)
    categories = active_categories()     # усі 14 категорій або підмножина зі SCRAPE_CATEGORIES

    async with aiohttp.ClientSession() as session:
        print(f"🔍 work.ua: збір вакансій по {len(categories)} категоріях ринку...")
        for cat in categories:
            await _scrape_category(session, cat.workua_slug, cat.label, semaphore)

    print("\n✅ Скрейпінг вакансій завершено.")


if __name__ == "__main__":
    asyncio.run(main())
