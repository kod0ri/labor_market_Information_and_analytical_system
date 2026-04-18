import asyncio
import aiohttp
from bs4 import BeautifulSoup
import logging
from psycopg2.extras import Json
import random

# Імпортуємо пул з'єднань, створений на Кроці 2
from src.db.database import DatabasePool

# Налаштування логування
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

CATEGORIES = {
    "IT": "https://www.work.ua/resumes-it/",
    "Sales": "https://www.work.ua/resumes-sales/",
    "Marketing": "https://www.work.ua/resumes-marketing/",
    "Retail": "https://www.work.ua/resumes-retail/",
    "Finance": "https://www.work.ua/resumes-finance/",
}

MAX_PAGES = 2
CONCURRENT_REQUESTS = 5  # Кількість одночасних запитів (семафор)


def save_to_db(resume_id, category_name, raw_text, full_url):
    """Синхронне збереження в БД з використанням пулу з'єднань"""
    raw_json_data = {"url": full_url, "category": category_name}

    with DatabasePool.get_connection() as conn:
        with conn.cursor() as cursor:
            try:
                cursor.execute(
                    """
                    INSERT INTO staging.raw_resumes 
                    (source_name, external_id, raw_text, raw_json)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (source_name, external_id) DO NOTHING;
                """,
                    ("work.ua", str(resume_id), raw_text, Json(raw_json_data)),
                )

                inserted = cursor.rowcount > 0
                conn.commit()
                return inserted
            except Exception as e:
                logger.error(f"Помилка БД при збереженні ID {resume_id}: {e}")
                conn.rollback()
                return False


async def fetch_html(session, url, semaphore):
    """Асинхронне завантаження сторінки з обмеженням швидкості"""
    async with semaphore:
        # Невелика рандомізована затримка для захисту від бану
        await asyncio.sleep(random.uniform(0.5, 1.5))
        try:
            async with session.get(url, headers=HEADERS) as response:
                if response.status == 200:
                    return await response.text()
                else:
                    logger.warning(f"Неуспішний статус {response.status} для {url}")
                    return None
        except Exception as e:
            logger.error(f"Помилка завантаження {url}: {e}")
            return None


async def process_resume(session, resume_id, category_name, semaphore):
    """Обробка одного резюме: завантаження, парсинг, збереження"""
    full_url = f"https://www.work.ua/resumes/{resume_id}/"

    html = await fetch_html(session, full_url, semaphore)
    if not html:
        return False

    soup = BeautifulSoup(html, "html.parser")
    main_content = soup.find("div", class_="card")

    if main_content:
        text = main_content.get_text(separator=" ", strip=True)
    else:
        text = soup.get_text(separator=" ", strip=True)

    if not text:
        return False

    # Виконуємо синхронний запис у БД в окремому потоці, щоб не блокувати Event Loop
    inserted = await asyncio.to_thread(
        save_to_db, resume_id, category_name, text, full_url
    )

    if inserted:
        logger.info(f"✅ Збережено: ID {resume_id} ({category_name})")
    else:
        logger.debug(f"⏩ Пропущено (вже є): ID {resume_id}")

    return inserted


async def process_category(session, category_name, base_url, semaphore):
    """Обробка всіх сторінок однієї категорії"""
    logger.info(f"🚀 Початок парсингу категорії: {category_name}")
    total_saved = 0

    for page in range(1, MAX_PAGES + 1):
        current_url = base_url if page == 1 else f"{base_url}?page={page}"
        logger.info(f"📄 Категорія {category_name}, сторінка {page}")

        html = await fetch_html(session, current_url, semaphore)
        if not html:
            break

        soup = BeautifulSoup(html, "html.parser")
        links = soup.find_all("a")
        resume_ids = set()

        for link in links:
            href = link.get("href")
            # Явно перевіряємо, що href є рядком (вирішує всі помилки Pylance)
            if isinstance(href, str):
                parts = [p for p in href.split("/") if p]

                if len(parts) >= 2 and parts[0] == "resumes" and parts[1].isdigit():
                    resume_ids.add(parts[1])

        if not resume_ids:
            logger.warning(f"На сторінці {page} не знайдено резюме.")
            continue

        # Запускаємо обробку всіх знайдених резюме на сторінці ОДНОЧАСНО
        tasks = [
            process_resume(session, r_id, category_name, semaphore)
            for r_id in resume_ids
        ]
        results = await asyncio.gather(*tasks)

        total_saved += sum(results)

    return total_saved


async def main():
    # Ініціалізація пулу з'єднань (викликаємо один раз)
    DatabasePool.initialize()

    # Семафор обмежує кількість одночасних запитів до сайту
    semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)

    async with aiohttp.ClientSession() as session:
        tasks = []
        for category_name, base_url in CATEGORIES.items():
            # Запускаємо категорії паралельно
            tasks.append(process_category(session, category_name, base_url, semaphore))

        results = await asyncio.gather(*tasks)

    total_all = sum(results)
    logger.info(
        f"🎉 Парсинг повністю завершено! Загалом додано нових резюме: {total_all}"
    )


if __name__ == "__main__":
    # Запуск асинхронного Event Loop
    asyncio.run(main())
