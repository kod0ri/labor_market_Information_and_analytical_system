import asyncio
import aiohttp
from bs4 import BeautifulSoup
import json
from src.db.database import AsyncDatabasePool

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
BASE_URL = "https://www.work.ua"
SEARCH_URL = f"{BASE_URL}/jobs-it/?days=122"


async def fetch_html(session, url, retries=3):
    """Виконує запит БЕЗ семафора (семафор контролюється вище)."""
    for attempt in range(retries):
        try:
            async with session.get(url, headers=HEADERS, timeout=15) as response:
                if response.status == 200:
                    return await response.text()
                elif response.status == 429:
                    await asyncio.sleep(5 * (attempt + 1))
                elif response.status == 404:
                    return None
                else:
                    response.raise_for_status()
        except Exception as e:
            if attempt == retries - 1:
                print(f"   ❌ Помилка мережі ({url}): {e}")
                return None
            await asyncio.sleep(2**attempt)
    return None


def _sync_parse_vacancy(html: str, url: str) -> dict:
    """Синхронна функція для CPU-bound парсингу (lxml)."""
    soup = BeautifulSoup(html, "lxml")
    title_tag = soup.find("h1")
    title = title_tag.text.strip() if title_tag else "Невідома посада"

    company_tag = soup.find("a", class_="inline-block mb-sm")
    company = company_tag.text.strip() if company_tag else ""

    return {"title": title, "company": company, "url": url}


async def process_vacancy_page(session, url, external_id, semaphore):
    # УВЕСЬ процес (мережа + парсинг + БД) обмежено семафором
    async with semaphore:
        html = await fetch_html(session, url)
        if not html:
            return

        # Віддаємо парсинг у тред-пул
        parsed_data = await asyncio.to_thread(_sync_parse_vacancy, html, url)
        raw_json = json.dumps(parsed_data, ensure_ascii=False)

        query = """
            INSERT INTO staging.raw_vacancies (source_name, external_id, search_category, raw_html, raw_json)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (source_name, external_id) DO NOTHING
            RETURNING id;
        """
        
        async with AsyncDatabasePool.get_connection() as conn:
            inserted_id = await conn.fetchval(query, 'work.ua', external_id, 'IT', html, raw_json)
            if inserted_id:
                print(f"   📥 Нова вакансія: {parsed_data['title'][:40]}...")


def _sync_parse_list_page(list_html: str) -> dict:
    """Парсинг сторінки з переліком вакансій."""
    soup = BeautifulSoup(list_html, "lxml")
    cards = soup.find_all("div", class_="card-hover")
    
    page_jobs = {}
    if not cards:
        return page_jobs

    for card in cards:
        link_tag = card.find("a", href=True)
        if not link_tag:
            continue

        href = link_tag.get("href")
        if isinstance(href, str) and href.startswith("/jobs/"):
            external_id = href.split("/")[2]
            page_jobs[external_id] = f"{BASE_URL}{href}"
            
    return page_jobs


async def main():
    await AsyncDatabasePool.initialize()
    # Ліміт у 10 одночасних потоків безпечний для пулу БД
    semaphore = asyncio.Semaphore(10)

    async with aiohttp.ClientSession() as session:
        print("🔍 Починаємо збір вакансій...")
        page = 1
        max_pages = 50

        async with AsyncDatabasePool.get_connection() as conn:
            while page <= max_pages:
                url = f"{SEARCH_URL}&page={page}"
                print(f"\n📄 Обробка вакансій, сторінка {page}...")
                
                # Мейн-цикл обробляє пагінацію послідовно
                list_html = await fetch_html(session, url)
                if not list_html:
                    break 

                page_jobs = await asyncio.to_thread(_sync_parse_list_page, list_html)
                if not page_jobs:
                    break

                external_ids = list(page_jobs.keys())
                existing_records = await conn.fetch(
                    "SELECT external_id FROM staging.raw_vacancies WHERE source_name = $1 AND external_id = ANY($2::varchar[]);",
                    "work.ua",
                    external_ids,
                )
                existing_ids = {record["external_id"] for record in existing_records}

                # Формуємо таски ТІЛЬКИ для поточної сторінки
                page_tasks = [
                    process_vacancy_page(session, job_url, ext_id, semaphore)
                    for ext_id, job_url in page_jobs.items()
                    if ext_id not in existing_ids
                ]

                # Батчева обробка: виконуємо і чекаємо завершення тасок поточної сторінки
                if page_tasks:
                    await asyncio.gather(*page_tasks)
                else:
                    print("   ✨ Нових вакансій на цій сторінці не знайдено.")

                page += 1

if __name__ == "__main__":
    asyncio.run(main())