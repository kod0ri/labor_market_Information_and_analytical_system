"""
Модуль агрегації аналітичних знімків ринку праці.
Заповнює таблицю analytics.daily_market_snapshots на основі
оброблених даних з core.vacancies та core.resumes.
Запускається як фінальний крок пайплайну — після currency_converter.
"""

import asyncio
import sys
from datetime import date, timedelta

from src.db.database import AsyncDatabasePool

# FIX #1: Відновлено повний SELECT з полем avg_vacancy_salary_usd.
# Попередня версія мала "-- ... код зарплат ..." замість реального коду —
# це валідний SQL-коментар, але поле було відсутнє → KeyError при fetchrow.
VACANCIES_AGGREGATION_SQL = """
    SELECT
        COALESCE(s.search_category, 'UNKNOWN')      AS category,
        COUNT(v.id)                                  AS total_vacancies,
        AVG(
            CASE
                WHEN v.min_salary_usd_eq IS NOT NULL AND v.max_salary_usd_eq IS NOT NULL
                    THEN (v.min_salary_usd_eq + v.max_salary_usd_eq) / 2.0
                WHEN v.min_salary_usd_eq IS NOT NULL
                    THEN v.min_salary_usd_eq
                WHEN v.max_salary_usd_eq IS NOT NULL
                    THEN v.max_salary_usd_eq
            END
        )                                            AS avg_vacancy_salary_usd
    FROM core.vacancies v
    JOIN staging.raw_vacancies s ON v.staging_id = s.id
    WHERE v.created_at >= $1::timestamp
      AND v.created_at <  ($1::timestamp + INTERVAL '1 day')
    GROUP BY COALESCE(s.search_category, 'UNKNOWN');
"""

RESUMES_AGGREGATION_SQL = """
    SELECT
        COUNT(r.id) AS total_resumes,
        AVG(
            CASE
                WHEN r.min_salary_usd_eq IS NOT NULL AND r.max_salary_usd_eq IS NOT NULL
                    THEN (r.min_salary_usd_eq + r.max_salary_usd_eq) / 2.0
                WHEN r.min_salary_usd_eq IS NOT NULL
                    THEN r.min_salary_usd_eq
                WHEN r.max_salary_usd_eq IS NOT NULL
                    THEN r.max_salary_usd_eq
            END
        ) AS avg_resume_salary_usd
    FROM core.resumes r
    WHERE r.created_at >= $1::timestamp
      AND r.created_at <  ($1::timestamp + INTERVAL '1 day');
"""

UPSERT_SNAPSHOT_SQL = """
    INSERT INTO analytics.daily_market_snapshots
        (snapshot_date, category, total_vacancies, total_resumes,
         avg_vacancy_salary_usd, avg_resume_salary_usd)
    VALUES ($1, $2, $3, $4, $5, $6)
    ON CONFLICT (snapshot_date, category)
    DO UPDATE SET
        total_vacancies        = EXCLUDED.total_vacancies,
        total_resumes          = EXCLUDED.total_resumes,
        avg_vacancy_salary_usd = EXCLUDED.avg_vacancy_salary_usd,
        avg_resume_salary_usd  = EXCLUDED.avg_resume_salary_usd,
        created_at             = CURRENT_TIMESTAMP;
"""


async def build_snapshot(target_date: date | None = None) -> None:
    if target_date is None:
        target_date = date.today()

    print(f"📸 Побудова аналітичного знімку за {target_date}...")

    async with AsyncDatabasePool.get_connection() as conn:
        resume_row = await conn.fetchrow(RESUMES_AGGREGATION_SQL, target_date)
        total_resumes = resume_row["total_resumes"] if resume_row else 0
        avg_resume_salary = (
            float(resume_row["avg_resume_salary_usd"])
            if resume_row and resume_row["avg_resume_salary_usd"] is not None
            else None
        )

        vacancy_rows = await conn.fetch(VACANCIES_AGGREGATION_SQL, target_date)

        if not vacancy_rows:
            print(f"   ⚠️ Вакансій за {target_date} не знайдено. Записуємо порожній знімок.")
            await conn.execute(
                UPSERT_SNAPSHOT_SQL,
                target_date, "ALL", 0,
                total_resumes, None, avg_resume_salary,
            )
            print("   ✅ Порожній знімок збережено.")
            return

        # Вакансії — по категоріях (search_category). Резюме у цьому пайплайні
        # НЕ категоризуються, тож НЕ дублюємо їхні добові показники в кожен
        # рядок-категорію (це множило б total_resumes у стільки разів, скільки
        # категорій, при сумуванні по даті). Резюме йдуть одним рядком 'ALL'.
        upsert_data = [
            (
                target_date,
                row["category"],
                row["total_vacancies"],
                0,
                float(row["avg_vacancy_salary_usd"]) if row["avg_vacancy_salary_usd"] is not None else None,
                None,
            )
            for row in vacancy_rows
        ]
        upsert_data.append(
            (target_date, "ALL", 0, total_resumes, None, avg_resume_salary)
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
    today = date.today()
    dates = [today - timedelta(days=i) for i in range(days_back)]
    print(f"🔄 Backfill: перераховуємо {days_back} днів ({dates[-1]} → {dates[0]})...")
    for target_date in reversed(dates):
        await build_snapshot(target_date)
    print("✅ Backfill завершено.")


async def run_snapshot() -> None:
    await build_snapshot()


if __name__ == "__main__":
    async def _main():
        await AsyncDatabasePool.initialize()
        try:
            if len(sys.argv) >= 2 and sys.argv[1] == "backfill":
                days = int(sys.argv[2]) if len(sys.argv) >= 3 else 30
                await backfill_history(days)
            else:
                await run_snapshot()
        finally:
            await AsyncDatabasePool.close_all()

    asyncio.run(_main())