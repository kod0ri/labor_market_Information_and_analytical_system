import asyncio
from prefect import flow, task, get_run_logger

from src.db.database import AsyncDatabasePool
from src.scrapers import workua_vacancies, workua_resumes
from src.processor import nlp_vacancies, nlp_resumes, currency_converter
from src.processor.analytics_snapshot import run_snapshot


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
    logger.info("Запуск NLP обробки вакансій...")
    await nlp_vacancies.main()


@task(name="NLP Process Resumes")
async def task_nlp_resumes():
    logger = get_run_logger()
    logger.info("Запуск NLP обробки резюме...")
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


@flow(name="Labor Market ETL Pipeline", log_prints=True)
async def etl_flow():
    logger = get_run_logger()
    logger.info("🚀 Старт ETL пайплайну!")

    try:
        await AsyncDatabasePool.initialize()

        # FIX #6: Використовуємо .submit() замість asyncio.gather(task()).
        # Проблема оригіналу: asyncio.gather(prefect_task()) обходить Prefect's task runner —
        # retry логіка, стани (PENDING/RUNNING/FAILED) і логування не працюють коректно.
        # Це пояснювало чому Етап 2 "зникав" без помилки — Prefect не бачив задачі.
        #
        # .submit() реєструє задачу в Prefect, повертає Future.
        # .result() очікує завершення і пробрасує виняток якщо задача failed.

        logger.info("--- Етап 1: Збір даних (паралельно) ---")
        future_vac = task_scrape_vacancies.submit()
        future_res = task_scrape_resumes.submit()
        # Чекаємо обидві задачі — якщо одна впала, raise тут
        await asyncio.gather(
            asyncio.to_thread(future_vac.result),
            asyncio.to_thread(future_res.result),
        )

        logger.info("--- Етап 2: NLP обробка (паралельно) ---")
        future_nlp_vac = task_nlp_vacancies.submit()
        future_nlp_res = task_nlp_resumes.submit()
        await asyncio.gather(
            asyncio.to_thread(future_nlp_vac.result),
            asyncio.to_thread(future_nlp_res.result),
        )

        logger.info("--- Етап 3: Конвертація валют ---")
        future_conv = task_convert_currencies.submit()
        await asyncio.to_thread(future_conv.result)

        logger.info("--- Етап 4: Аналітичний знімок ---")
        future_snap = task_build_snapshot.submit()
        await asyncio.to_thread(future_snap.result)

        logger.info("✅ Пайплайн успішно завершив роботу!")

    except Exception as e:
        logger.error(f"❌ Критична помилка в пайплайні: {e}")
        raise
    finally:
        await AsyncDatabasePool.close_all()
        logger.info("🔒 Підключення до БД закрито.")


if __name__ == "__main__":
    asyncio.run(etl_flow())