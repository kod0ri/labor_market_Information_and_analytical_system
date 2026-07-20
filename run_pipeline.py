"""
Оркестрація повного ETL-циклу через Prefect: збір → NLP-збагачення →
конвертація валют → аналітичний знімок. Кожна @task обгортає вже існуючу
main()-точку входу відповідного модуля (scrapers/sources/processor) - сама
бізнес-логіка живе там, тут лише порядок виконання й Prefect-спостережуваність
(PENDING/RUNNING/FAILED стан кожного кроку, автоматичні retries).
"""

import asyncio
from prefect import flow, task, get_run_logger

from src.db.database import AsyncDatabasePool
from src.scrapers import workua_vacancies, workua_resumes
from src.sources import dou_rss, robota_vacancies
from src.processor import nlp_vacancies, nlp_resumes, currency_converter
from src.processor.analytics_snapshot import run_snapshot


# retries=2 на скрапери - мережеві джерела (work.ua) час від часу тимчасово
# недоступні; NLP/конвертація/знімок нижче retries НЕ мають - їхні власні
# внутрішні механізми (LLM-каскад, ідемпотентний UPSERT) вже обробляють
# часткові збої, і сліпий Prefect-retry цілого кроку лише подвоїв би роботу.
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


@task(name="Collect DOU RSS", retries=1, retry_delay_seconds=10)
async def task_collect_dou():
    """DOU.ua RSS → staging (далі LLM-обробка на етапі 2)."""
    logger = get_run_logger()
    logger.info("Збір вакансій з DOU.ua RSS...")
    await dou_rss.main()


@task(name="Collect robota.ua", retries=1, retry_delay_seconds=10)
async def task_collect_robota():
    """robota.ua GraphQL → staging (далі LLM-обробка на етапі 2)."""
    logger = get_run_logger()
    logger.info("Збір вакансій з robota.ua...")
    await robota_vacancies.main()


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


@flow(name="Labor Market ETL Pipeline", log_prints=True)   # log_prints=True - print() у задачах теж потрапляє в Prefect-логи
async def etl_flow():
    logger = get_run_logger()             # структурований логер Prefect (видно у UI/логах flow-запуску)
    logger.info("🚀 Старт ETL пайплайну!")

    try:
        await AsyncDatabasePool.initialize()   # єдиний пул на весь flow - усі задачі нижче користуються ним

        # asyncio.gather() запускає async-задачі конкурентно в ОДНОМУ event loop.
        # Попередній паттерн .submit() + asyncio.to_thread(future.result) породжував
        # окремий thread → новий event loop → asyncpg.Pool, створений у головному loop,
        # недосяжний → RuntimeError: Future attached to a different loop.
        # Prefect @task декоратори при прямому виклику всередині @flow продовжують
        # відстежувати стан задачі (PENDING/RUNNING/FAILED) і retry логіку.

        logger.info("--- Етап 1: Збір даних (паралельно) ---")
        # work.ua (вакансії+резюме) + DOU + robota.ua → staging; LLM-обробка на етапі 2.
        # Лишаємо лише джерела з повними полями (ЗП/досвід/англ./гео/навички);
        # структуровані job-борди без цих полів прибрано — вони псували статистику.
        await asyncio.gather(          # усі 4 джерела одночасно - незалежні одне від одного, різні сайти
            task_scrape_vacancies(),
            task_scrape_resumes(),
            task_collect_dou(),
            task_collect_robota(),
        )

        logger.info("--- Етап 2: NLP обробка (паралельно) ---")
        await asyncio.gather(           # вакансії й резюме одночасно - обидва тягнуть з ТОГО Ж LLM-каскаду (спільний бюджет)
            task_nlp_vacancies(),
            task_nlp_resumes(),
        )

        logger.info("--- Етап 3: Конвертація валют ---")
        await task_convert_currencies()

        logger.info("--- Етап 4: Аналітичний знімок ---")
        await task_build_snapshot()

        logger.info("✅ Пайплайн успішно завершив роботу!")

    except Exception as e:
        logger.error(f"❌ Критична помилка в пайплайні: {e}")
        raise
    finally:
        await AsyncDatabasePool.close_all()
        logger.info("🔒 Підключення до БД закрито.")


if __name__ == "__main__":
    try:
        asyncio.run(etl_flow())
    except (KeyboardInterrupt, asyncio.CancelledError):
        # etl_flow()'s finally: уже закрив пул з'єднань до цього моменту -
        # тут лише глушимо шумний traceback Prefect/asyncio від Ctrl+C.
        print("\n⏹️ Пайплайн перервано користувачем (Ctrl+C). З'єднання з БД закрито коректно.")
