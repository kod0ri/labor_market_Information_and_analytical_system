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


async def fetch_html(session, url, semaphore, retries=3):
    async with semaphore:
        for attempt in range(retries):
            try:
                async with session.get(url, headers=HEADERS, timeout=15) as response:
                    if response.status == 200:
                        return await response.text()
                    elif response.status == 429:
                        await asyncio.sleep(5 * (attempt + 1))
                    else:
                        response.raise_for_status()
            except Exception as e:
                if attempt == retries - 1:
                    print(f"   ❌ Помилка мережі ({url}): {e}")
                    return None
                await asyncio.sleep(2**attempt)
        return None


async def process_vacancy_page(session, url, external_id, semaphore):
    """Кожна таска самостійно бере з'єднання з БД для збереження."""
    html = await fetch_html(session, url, semaphore)
    if not html:
        return

    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.find("h1")
    title = title_tag.text.strip() if title_tag else "Невідома посада"

    company_tag = soup.find("a", class_="inline-block mb-sm")
    company = company_tag.text.strip() if company_tag else ""

    raw_json = json.dumps(
        {"title": title, "company": company, "url": url}, ensure_ascii=False
    )

    query = """
        INSERT INTO staging.raw_vacancies (source_name, external_id, raw_html, raw_json)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (source_name, external_id) DO NOTHING
        RETURNING id;
    """

    # Беремо окреме з'єднання з пулу ВИКЛЮЧНО для запису
    async with AsyncDatabasePool.get_connection() as conn:
        inserted_id = await conn.fetchval(query, "work.ua", external_id, html, raw_json)
        if inserted_id:
            print(f"   📥 Нова вакансія: {title[:40]}...")


async def main():
    await AsyncDatabasePool.initialize()
    semaphore = asyncio.Semaphore(5)

    async with aiohttp.ClientSession() as session:
        print("🔍 Шукаємо сторінки вакансій...")
        list_html = await fetch_html(session, SEARCH_URL, semaphore)

        if not list_html:
            print("❌ Не вдалося завантажити головну сторінку.")
            return

        soup = BeautifulSoup(list_html, "html.parser")
        cards = soup.find_all("div", class_="card-hover")

        tasks = []
        # Тут з'єднання використовується лише послідовно для перевірки існування
        async with AsyncDatabasePool.get_connection() as conn:
            for card in cards:
                link_tag = card.find("a", href=True)
                if not link_tag:
                    continue

                href = link_tag.get("href")
                if not isinstance(href, str) or not href.startswith("/jobs/"):
                    continue

                external_id = href.split("/")[2]
                url = f"{BASE_URL}{href}"

                exists = await conn.fetchval(
                    "SELECT id FROM staging.raw_vacancies WHERE source_name = $1 AND external_id = $2;",
                    "work.ua",
                    external_id,
                )
                if not exists:
                    # Більше не передаємо conn!
                    tasks.append(
                        process_vacancy_page(session, url, external_id, semaphore)
                    )

        if tasks:
            print(f"🚀 Завантажуємо {len(tasks)} нових вакансій паралельно...")
            await asyncio.gather(*tasks)
        else:
            print("✨ Нових вакансій не знайдено.")


if __name__ == "__main__":
    asyncio.run(main())
