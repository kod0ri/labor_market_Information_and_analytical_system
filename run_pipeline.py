import asyncio
from prefect import flow, task
from prefect.logging import get_run_logger

from src.scrapers import workua_vacancies, workua_resumes
from src.processor import nlp_vacancies, nlp_resumes, currency_converter
from src.db.database import AsyncDatabasePool  # <--- Імпортуємо пул

@task(name="Scrape Vacancies", retries=2, retry_delay_seconds=10)
async def task_scrape_vacancies():
    logger = get_run_logger()
    logger.info("Починаємо збір вакансій...")
    await workua_vacancies.main()

@task(name="Scrape Resumes", retries=2, retry_delay_seconds=10)
async def task_scrape_resumes():
    logger = get_run_logger()
    logger.info("Починаємо збір резюме...")
    await workua_resumes.main()

@task(name="NLP Process Vacancies", retries=1)
async def task_nlp_vacancies():
    logger = get_run_logger()
    logger.info("Запуск NLP обробки вакансій (Groq)...")
    await nlp_vacancies.main()

@task(name="NLP Process Resumes", retries=1)
async def task_nlp_resumes():
    logger = get_run_logger()
    logger.info("Запуск NLP обробки резюме (Groq)...")
    await nlp_resumes.main()

@task(name="Convert Currencies")
async def task_convert_currencies():
    logger = get_run_logger()
    logger.info("Нормалізація зарплат у USD...")
    await currency_converter.run_conversion() 

@flow(name="Labor Market ETL Pipeline")
async def main_pipeline():
    logger = get_run_logger()
    logger.info("🚀 Старт ETL пайплайну!")

    try:
        # ЕТАП 1: Скрейпінг (працюють паралельно)
        logger.info("--- Етап 1: Збір даних ---")
        await asyncio.gather(
            task_scrape_vacancies(), # type: ignore
            task_scrape_resumes()    # type: ignore
        )

        # ЕТАП 2: NLP Обробка
        logger.info("--- Етап 2: NLP обробка ---")
        await asyncio.gather(
            task_nlp_vacancies(),    # type: ignore
            task_nlp_resumes()       # type: ignore
        )

        # ЕТАП 3: Нормалізація валют
        logger.info("--- Етап 3: Конвертація валют ---")
        await task_convert_currencies()  # type: ignore 

        logger.info("✅ Пайплайн успішно завершив роботу!")
        
    finally:
        # ЗАВЖДИ закриваємо пул в кінці, незалежно від помилок
        await AsyncDatabasePool.close_all()
        logger.info("🔒 Підключення до бази даних безпечно закрито.")

if __name__ == "__main__":
    asyncio.run(main_pipeline())