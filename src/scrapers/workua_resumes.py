import asyncio
import aiohttp
from bs4 import BeautifulSoup
import json
from src.db.database import AsyncDatabasePool

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
BASE_URL = "https://www.work.ua"
SEARCH_URL = f"{BASE_URL}/resumes-it/"


async def fetch_html(session, url, semaphore, retries=3):
    async with semaphore:
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


async def process_resume_page(session, url, external_id, semaphore):
    html = await fetch_html(session, url, semaphore)
    if not html:
        return

    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.find("h1")
    title = title_tag.text.strip() if title_tag else "Невідоме резюме"

    raw_json = json.dumps({"title": title, "url": url}, ensure_ascii=False)

    query = """
        INSERT INTO staging.raw_resumes (source_name, external_id, raw_text, raw_json)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (source_name, external_id) DO NOTHING
        RETURNING id;
    """

    async with AsyncDatabasePool.get_connection() as conn:
        inserted_id = await conn.fetchval(query, "work.ua", external_id, html, raw_json)
        if inserted_id:
            print(f"   📥 Нове резюме: {title[:40]}...")


async def main():
    await AsyncDatabasePool.initialize()
    semaphore = asyncio.Semaphore(10)

    async with aiohttp.ClientSession() as session:
        print("🔍 Починаємо збір резюме...")
        tasks = []
        page = 1
        max_pages = 50

        async with AsyncDatabasePool.get_connection() as conn:
            while page <= max_pages:
                # Зверни увагу: для резюме параметр починається з ? а не &
                url = f"{SEARCH_URL}?page={page}"
                print(f"📄 Обробка резюме, сторінка {page}...")
                
                list_html = await fetch_html(session, url, semaphore)
                if not list_html:
                    break

                soup = BeautifulSoup(list_html, "html.parser")
                cards = soup.find_all("div", class_="card-hover")
                
                if not cards:
                    break

                page_resumes = {}
                for card in cards:
                    link_tag = card.find("a", href=True)
                    if not link_tag:
                        continue

                    href = link_tag.get("href")
                    if isinstance(href, str) and href.startswith("/resumes/"):
                        external_id = href.split("/")[2]
                        page_resumes[external_id] = f"{BASE_URL}{href}"

                if not page_resumes:
                    break

                external_ids = list(page_resumes.keys())
                existing_records = await conn.fetch(
                    "SELECT external_id FROM staging.raw_resumes WHERE source_name = $1 AND external_id = ANY($2::varchar[]);",
                    "work.ua",
                    external_ids,
                )
                existing_ids = {record["external_id"] for record in existing_records}

                for ext_id, resume_url in page_resumes.items():
                    if ext_id not in existing_ids:
                        tasks.append(process_resume_page(session, resume_url, ext_id, semaphore))

                page += 1

        if tasks:
            print(f"🚀 Завантажуємо {len(tasks)} нових резюме паралельно...")
            await asyncio.gather(*tasks)
        else:
            print("✨ Нових резюме не знайдено.")

if __name__ == "__main__":
    asyncio.run(main())