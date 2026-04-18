import asyncio
import aiohttp
from bs4 import BeautifulSoup
import logging
from psycopg2.extras import Json
import random

# Імпортуємо пул з'єднань, створений на попередньому кроці
from src.db.database import DatabasePool

# Налаштування логування
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Словник категорій для парсингу
CATEGORIES = {
    "IT": "https://www.work.ua/jobs-it/",
    "Marketing": "https://www.work.ua/jobs-marketing/",
    "Administration": "https://www.work.ua/jobs-administration/",
}

MAX_PAGES = 2
CONCURRENT_REQUESTS = 5  # Кількість одночасних запитів (семафор)


def save_to_db(
    job_id, category_name, full_description, title, link, salary, company, location
):
    """Синхронне збереження вакансії в БД з використанням пулу з'єднань"""
    raw_json_data = {
        "title": title,
        "url": link,
        "salary": salary,
        "company": company,
        "location": location,
    }

    with DatabasePool.get_connection() as conn:
        with conn.cursor() as cursor:
            try:
                cursor.execute(
                    """
                    INSERT INTO staging.raw_vacancies 
                    (source_name, external_id, raw_html, raw_json, search_category)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (source_name, external_id) DO NOTHING;
                """,
                    (
                        "work.ua",
                        str(job_id),
                        full_description,
                        Json(raw_json_data),
                        category_name,
                    ),
                )

                inserted = cursor.rowcount > 0
                conn.commit()
                return inserted
            except Exception as e:
                logger.error(f"Помилка БД при збереженні вакансії {job_id}: {e}")
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


async def process_vacancy(session, job_id, title, link, category_name, semaphore):
    """Обробка однієї вакансії: завантаження сторінки, парсинг даних, збереження"""
    html = await fetch_html(session, link, semaphore)
    if not html:
        return False

    soup = BeautifulSoup(html, "html.parser")

    # 1. Шукаємо опис
    description_div = soup.find("div", id="job-description")
    description = description_div.text.strip() if description_div else ""

    # 2. Шукаємо зарплату
    salary = ""
    for tag in soup.find_all(["b", "span", "h5"]):
        text = tag.text.strip()
        if any(currency in text for currency in ["грн", "₴", "$", "€"]):
            if len(text) < 40 and any(char.isdigit() for char in text):
                salary = text
                break

    # 3. Шукаємо ЧИСТУ компанію
    company = ""
    company_icon = soup.find("span", class_="glyphicon-company")
    if company_icon and company_icon.parent:
        name_tag = company_icon.parent.find(["a", "b"])
        if name_tag:
            company = name_tag.text.strip()
        else:
            raw_text = company_icon.parent.get_text(separator="|")
            parts = raw_text.split("|")
            company = parts[1].strip() if len(parts) > 1 else raw_text.strip()

    # 4. Шукаємо ЧИСТЕ місто
    location = ""
    location_icon = soup.find("span", class_="glyphicon-map-marker")
    if location_icon and location_icon.parent:
        raw_loc_text = location_icon.parent.get_text(separator="|")
        clean_loc = (
            raw_loc_text.split("|")[1].strip()
            if len(raw_loc_text.split("|")) > 1
            else raw_loc_text.strip()
        )
        location = clean_loc.split(",")[0].strip()

    # Зберігаємо в БД (в окремому потоці)
    inserted = await asyncio.to_thread(
        save_to_db,
        job_id,
        category_name,
        description,
        title,
        link,
        salary,
        company,
        location,
    )

    if inserted:
        logger.info(f"✅ Збережено: [{category_name}] {title} (ID: {job_id})")
    else:
        logger.debug(f"⏩ Пропущено (вже є в БД): {title} (ID: {job_id})")

    return inserted


async def process_category(session, category_name, base_url, semaphore):
    """Обробка всіх сторінок однієї категорії"""
    logger.info(f"🚀 ПОЧИНАЄМО ПАРСИНГ КАТЕГОРІЇ: {category_name}")
    total_saved = 0

    for page in range(1, MAX_PAGES + 1):
        current_url = base_url if page == 1 else f"{base_url}?page={page}"
        logger.info(f"📄 Категорія {category_name}, сторінка {page}...")

        html = await fetch_html(session, current_url, semaphore)
        if not html:
            break

        soup = BeautifulSoup(html, "html.parser")
        job_headers = soup.find_all("h2")

        if not job_headers:
            logger.warning(f"⚠️ Вакансії у категорії '{category_name}' закінчилися.")
            break

        tasks = []
        for header in job_headers:
            link_tag = header.find("a")

            if link_tag:
                href = link_tag.get("href")
                # Перевіряємо тип і наявність підрядка безпечно
                if isinstance(href, str) and "/jobs/" in href:
                    title = link_tag.text.strip()
                    job_id = href.split("/")[-2]
                    link = "https://www.work.ua" + href

                    tasks.append(
                        process_vacancy(
                            session, job_id, title, link, category_name, semaphore
                        )
                    )

        # Запускаємо обробку вакансій зі сторінки ОДНОЧАСНО
        if tasks:
            results = await asyncio.gather(*tasks)
            total_saved += sum(results)

    return total_saved


async def main():
    # Ініціалізація пулу з'єднань
    DatabasePool.initialize()

    semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)

    async with aiohttp.ClientSession() as session:
        tasks = []
        for category_name, base_url in CATEGORIES.items():
            tasks.append(process_category(session, category_name, base_url, semaphore))

        results = await asyncio.gather(*tasks)

    total_all = sum(results)
    logger.info(f"\n🎉 Парсинг завершено! Усього додано нових вакансій: {total_all}")


if __name__ == "__main__":
    asyncio.run(main())
