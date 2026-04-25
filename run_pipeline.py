import asyncio
from prefect import flow, task, get_run_logger

from src.db.database import AsyncDatabasePool
from src.scrapers import workua_vacancies, workua_resumes
from src.processor import nlp_vacancies, nlp_resumes, currency_converter
from src.processor.analytics_snapshot import run_snapshot


# --- Визначення тасок (Tasks) ---
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


@task(name="NLP Process Vacancies")
async def task_nlp_vacancies():
    logger = get_run_logger()
    logger.info("Запуск NLP обробки вакансій (Groq)...")
    await nlp_vacancies.main()


@task(name="NLP Process Resumes")
async def task_nlp_resumes():
    logger = get_run_logger()
    logger.info("Запуск NLP обробки резюме (Groq)...")
    await nlp_resumes.main()


@task(name="Convert Currencies")
async def task_convert_currencies():
    logger = get_run_logger()
    logger.info("Нормалізація зарплат у USD...")
    await currency_converter.run_conversion()


@task(name="Build Analytics Snapshot")
async def task_build_snapshot():
    logger = get_run_logger()
    logger.info("Побудова аналітичного знімку...")
    await run_snapshot()


# --- Головний пайплайн (Flow) ---
@flow(name="Labor Market ETL Pipeline", log_prints=True)
async def etl_flow():
    logger = get_run_logger()
    logger.info("🚀 Старт ETL пайплайну!")

    try:
        # 1. Єдина точка ініціалізації бази даних
        await AsyncDatabasePool.initialize()

        # 2. Етап 1: Збір даних (паралельно)
        logger.info("--- Етап 1: Збір даних ---")
        await asyncio.gather(task_scrape_vacancies(), task_scrape_resumes())

        # 3. Етап 2: NLP обробка (паралельно, після Етапу 1)
        logger.info("--- Етап 2: NLP обробка ---")
        await asyncio.gather(task_nlp_vacancies(), task_nlp_resumes())

        # 4. Етап 3: Конвертація валют (послідовно — знімок залежить від цього кроку)
        logger.info("--- Етап 3: Конвертація валют ---")
        await task_convert_currencies()

        # 5. Етап 4: Аналітика (після конвертації — беремо вже нормалізовані USD-зарплати)
        logger.info("--- Етап 4: Аналітичний знімок ---")
        await task_build_snapshot()

        logger.info("✅ Пайплайн успішно завершив роботу!")

    except Exception as e:
        logger.error(f"❌ Критична помилка в пайплайні: {e}")
        raise
    finally:
        await AsyncDatabasePool.close_all()
        logger.info("🔒 Підключення до бази даних безпечно закрито.")


if __name__ == "__main__":
    asyncio.run(etl_flow())