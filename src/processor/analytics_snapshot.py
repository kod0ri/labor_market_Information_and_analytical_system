"""
Модуль агрегації аналітичних знімків ринку праці.
Заповнює таблицю analytics.daily_market_snapshots на основі
оброблених даних з core.vacancies та core.resumes.

Запускається як фінальний крок пайплайну — після currency_converter.
"""

import asyncio
from datetime import date

from src.db.database import AsyncDatabasePool

# SQL-агрегація по категоріях вакансій.
# Джойнимо через staging щоб отримати search_category.
# Зарплати беремо з _usd_eq полів (вже нормалізовані конвертером).
VACANCIES_AGGREGATION_SQL = """
    SELECT
        COALESCE(s.search_category, 'UNKNOWN')      AS category,
        COUNT(v.id)                                 AS total_vacancies,
        -- ... код зарплат ...
    FROM core.vacancies v
    JOIN staging.raw_vacancies s ON v.staging_id = s.id
    -- Використовуємо range замість ::date для роботи B-Tree індексу
    WHERE v.created_at >= $1::timestamp 
      AND v.created_at < ($1::timestamp + INTERVAL '1 day')
    GROUP BY COALESCE(s.search_category, 'UNKNOWN');
"""

# Резюме не мають search_category — групуємо по NULL (загальний зріз).
# Для розширення: можна групувати по title через regexp у майбутньому.
RESUMES_AGGREGATION_SQL = """
    SELECT
        COUNT(r.id)     AS total_resumes,
        AVG(
            CASE
                WHEN r.min_salary_usd_eq IS NOT NULL AND r.max_salary_usd_eq IS NOT NULL
                    THEN (r.min_salary_usd_eq + r.max_salary_usd_eq) / 2.0
                WHEN r.min_salary_usd_eq IS NOT NULL
                    THEN r.min_salary_usd_eq
                WHEN r.max_salary_usd_eq IS NOT NULL
                    THEN r.max_salary_usd_eq
            END
        )               AS avg_resume_salary_usd
    FROM core.resumes r
    WHERE r.created_at::date = $1;
"""

UPSERT_SNAPSHOT_SQL = """
    INSERT INTO analytics.daily_market_snapshots
        (snapshot_date, category, total_vacancies, total_resumes,
         avg_vacancy_salary_usd, avg_resume_salary_usd)
    VALUES
        ($1, $2, $3, $4, $5, $6)
    ON CONFLICT (snapshot_date, category)
    DO UPDATE SET
        total_vacancies        = EXCLUDED.total_vacancies,
        total_resumes          = EXCLUDED.total_resumes,
        avg_vacancy_salary_usd = EXCLUDED.avg_vacancy_salary_usd,
        avg_resume_salary_usd  = EXCLUDED.avg_resume_salary_usd,
        created_at             = CURRENT_TIMESTAMP;
"""


async def build_snapshot(target_date: date | None = None) -> None:
    """
    Будує або оновлює знімок для вказаної дати.
    За замовчуванням — сьогодні (UTC).

    Args:
        target_date: Дата знімку. None = сьогодні.
                     Передавай конкретну дату для перерахунку історії.
    """
    if target_date is None:
        target_date = date.today()

    print(f"📸 Побудова аналітичного знімку за {target_date}...")

    async with AsyncDatabasePool.get_connection() as conn:
        # --- Агрегація резюме (один рядок, без категорій) ---
        resume_row = await conn.fetchrow(RESUMES_AGGREGATION_SQL, target_date)
        total_resumes = resume_row["total_resumes"] if resume_row else 0
        avg_resume_salary = (
            float(resume_row["avg_resume_salary_usd"])
            if resume_row and resume_row["avg_resume_salary_usd"] is not None
            else None
        )

        # --- Агрегація вакансій по категоріях ---
        vacancy_rows = await conn.fetch(VACANCIES_AGGREGATION_SQL, target_date)

        if not vacancy_rows:
            # Немає вакансій за цю дату — записуємо загальний рядок щоб дата була в таблиці
            print(
                f"   ⚠️ Вакансій за {target_date} не знайдено. Записуємо порожній знімок."
            )
            await conn.execute(
                UPSERT_SNAPSHOT_SQL,
                target_date,
                'ALL_CATEGORIES',  # Жодних None/NULL
                0,
                total_resumes,
                None,
                avg_resume_salary,
            )
            print("   ✅ Порожній знімок збережено.")
            return

        # --- UPSERT кожної категорії ---
        upsert_data = []
        for row in vacancy_rows:
            category = row["category"]
            total_vac = row["total_vacancies"]
            avg_vac_salary = (
                float(row["avg_vacancy_salary_usd"])
                if row["avg_vacancy_salary_usd"] is not None
                else None
            )

            upsert_data.append(
                (
                    target_date,
                    category,
                    total_vac,
                    total_resumes,  # резюме не мають категорій — однакове значення для всіх рядків
                    avg_vac_salary,
                    avg_resume_salary,
                )
            )

        async with conn.transaction():
            await conn.executemany(UPSERT_SNAPSHOT_SQL, upsert_data)

        categories_str = ", ".join(
            f"{r['category']}({r['total_vacancies']})" for r in vacancy_rows
        )
        print(
            f"   ✅ Збережено {len(upsert_data)} категорій: {categories_str}\n"
            f"   📊 Резюме за день: {total_resumes} | "
            f"Середня зарплата резюме: "
            f"{'${:.0f}'.format(avg_resume_salary) if avg_resume_salary else 'н/д'}"
        )


async def backfill_history(days_back: int = 30) -> None:
    """
    Перераховує знімки за останні N днів.
    Корисно після першого деплою або при зміні логіки агрегації.

    Args:
        days_back: Кількість днів для перерахунку.
    """
    from datetime import timedelta

    today = date.today()
    dates = [today - timedelta(days=i) for i in range(days_back)]

    print(f"🔄 Backfill: перераховуємо {days_back} днів ({dates[-1]} → {dates[0]})...")

    for target_date in reversed(dates):  # від старіших до новіших
        await build_snapshot(target_date)

    print("✅ Backfill завершено.")


async def run_snapshot() -> None:
    """Точка входу для пайплайну — знімок за сьогодні."""
    await build_snapshot()


if __name__ == "__main__":
    import sys

    async def _main():
        await AsyncDatabasePool.initialize()
        try:
            # python analytics_snapshot.py backfill 7  → перерахунок за 7 днів
            if len(sys.argv) >= 2 and sys.argv[1] == "backfill":
                days = int(sys.argv[2]) if len(sys.argv) >= 3 else 30
                await backfill_history(days)
            else:
                await run_snapshot()
        finally:
            await AsyncDatabasePool.close_all()

    asyncio.run(_main())
