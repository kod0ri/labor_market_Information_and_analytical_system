from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from src.db.database import AsyncDatabasePool

router = APIRouter()

_SOURCE_TABLE: dict[str, str] = {
    "vacancy": "core.vacancies",
    "resume": "core.resumes",
}
_SKILL_JOIN: dict[str, str] = {
    "vacancy": "core.vacancy_skills vs ON s.id = vs.skill_id",
    "resume": "core.resume_skills rs ON s.id = rs.skill_id",
}
_SKILL_COUNT_COL: dict[str, str] = {
    "vacancy": "vs.vacancy_id",
    "resume": "rs.resume_id",
}
_LOCATION_JOIN: dict[str, str] = {
    "vacancy": "core.vacancies t ON l.id = t.location_id",
    "resume": "core.resumes t ON l.id = t.location_id",
}


# ─── Response models ──────────────────────────────────────────────────────────

class OverviewResponse(BaseModel):
    total_vacancies: int
    total_resumes: int
    vacancies_with_salary: int
    resumes_with_salary: int
    avg_vacancy_salary_usd: Optional[float]
    avg_resume_salary_usd: Optional[float]


class DailySnapshotItem(BaseModel):
    snapshot_date: date
    category: str
    total_vacancies: int
    total_resumes: int
    avg_vacancy_salary_usd: Optional[float]
    avg_resume_salary_usd: Optional[float]


class SkillStat(BaseModel):
    name: str
    category: str
    count: int


class LocationStat(BaseModel):
    city_name: str
    region: Optional[str]
    count: int


class SalaryBucket(BaseModel):
    range_label: str
    min_usd: Optional[int]
    max_usd: Optional[int]
    count: int


class SkillGapItem(BaseModel):
    name: str
    category: str
    vacancy_count: int
    resume_count: int
    gap: int


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/overview", response_model=OverviewResponse)
async def get_overview():
    """
    Загальна статистика ринку: кількість вакансій/резюме, середні зарплати.
    Використовуй для картки-дашборду на головній сторінці.
    """
    async with AsyncDatabasePool.get_connection() as conn:
        row = await conn.fetchrow("""
            SELECT
                (SELECT COUNT(*) FROM core.vacancies)::int AS total_vacancies,
                (SELECT COUNT(*) FROM core.resumes)::int   AS total_resumes,
                (SELECT COUNT(*) FROM core.vacancies
                 WHERE min_salary_usd_eq IS NOT NULL OR max_salary_usd_eq IS NOT NULL
                )::int AS vacancies_with_salary,
                (SELECT COUNT(*) FROM core.resumes
                 WHERE min_salary_usd_eq IS NOT NULL OR max_salary_usd_eq IS NOT NULL
                )::int AS resumes_with_salary,
                (SELECT ROUND(AVG(
                    CASE WHEN min_salary_usd_eq IS NOT NULL AND max_salary_usd_eq IS NOT NULL
                         THEN (min_salary_usd_eq + max_salary_usd_eq) / 2.0
                         ELSE COALESCE(min_salary_usd_eq, max_salary_usd_eq)
                    END
                )::numeric, 0)::float
                 FROM core.vacancies
                 WHERE min_salary_usd_eq IS NOT NULL OR max_salary_usd_eq IS NOT NULL
                ) AS avg_vacancy_salary_usd,
                (SELECT ROUND(AVG(
                    CASE WHEN min_salary_usd_eq IS NOT NULL AND max_salary_usd_eq IS NOT NULL
                         THEN (min_salary_usd_eq + max_salary_usd_eq) / 2.0
                         ELSE COALESCE(min_salary_usd_eq, max_salary_usd_eq)
                    END
                )::numeric, 0)::float
                 FROM core.resumes
                 WHERE min_salary_usd_eq IS NOT NULL OR max_salary_usd_eq IS NOT NULL
                ) AS avg_resume_salary_usd;
        """)
    return dict(row)


@router.get("/snapshots", response_model=list[DailySnapshotItem])
async def get_snapshots(days: int = Query(default=30, ge=1, le=365, description="Кількість днів назад")):
    """
    Часовий ряд: вакансії, резюме, зарплати по дням.
    Використовуй для лінійних графіків (recharts LineChart / Chart.js Line).
    """
    async with AsyncDatabasePool.get_connection() as conn:
        rows = await conn.fetch("""
            SELECT
                snapshot_date,
                category,
                total_vacancies,
                total_resumes,
                avg_vacancy_salary_usd,
                avg_resume_salary_usd
            FROM analytics.daily_market_snapshots
            WHERE snapshot_date >= CURRENT_DATE - ($1::int || ' days')::interval
            ORDER BY snapshot_date ASC, category;
        """, days)
    return [dict(r) for r in rows]


@router.get("/skills", response_model=list[SkillStat])
async def get_top_skills(
    type: Literal["vacancy", "resume"] = Query(default="vacancy", description="vacancy або resume"),
    limit: int = Query(default=20, ge=1, le=100),
    category: Optional[Literal["Hard", "Soft"]] = Query(default=None, description="Фільтр за категорією"),
):
    """
    Топ навичок по попиту (vacancy) або пропозиції (resume).
    Використовуй для горизонтального bar chart.
    """
    join = _SKILL_JOIN[type]
    count_col = _SKILL_COUNT_COL[type]

    category_filter = "AND s.category = $2" if category else ""
    params = [limit, category] if category else [limit]

    query = f"""
        SELECT s.name, s.category, COUNT({count_col}) AS count
        FROM dictionaries.skills s
        JOIN {join}
        WHERE 1=1 {category_filter}
        GROUP BY s.id, s.name, s.category
        ORDER BY count DESC
        LIMIT $1;
    """
    async with AsyncDatabasePool.get_connection() as conn:
        rows = await conn.fetch(query, *params)
    return [dict(r) for r in rows]


@router.get("/skills/gap", response_model=list[SkillGapItem])
async def get_skill_gap(limit: int = Query(default=20, ge=1, le=50)):
    """
    Gap-аналіз: попит (вакансії) vs пропозиція (резюме) по навичкам.
    gap > 0 → дефіцит спеціалістів. gap < 0 → перенасичення ринку.
    Використовуй для порівняльного bar chart (grouped або stacked).
    """
    async with AsyncDatabasePool.get_connection() as conn:
        rows = await conn.fetch("""
            SELECT
                s.name,
                s.category,
                COUNT(DISTINCT vs.vacancy_id) AS vacancy_count,
                COUNT(DISTINCT rs.resume_id)  AS resume_count,
                COUNT(DISTINCT vs.vacancy_id) - COUNT(DISTINCT rs.resume_id) AS gap
            FROM dictionaries.skills s
            LEFT JOIN core.vacancy_skills vs ON s.id = vs.skill_id
            LEFT JOIN core.resume_skills  rs ON s.id = rs.skill_id
            GROUP BY s.id, s.name, s.category
            HAVING COUNT(DISTINCT vs.vacancy_id) > 0 OR COUNT(DISTINCT rs.resume_id) > 0
            ORDER BY ABS(COUNT(DISTINCT vs.vacancy_id) - COUNT(DISTINCT rs.resume_id)) DESC
            LIMIT $1;
        """, limit)
    return [dict(r) for r in rows]


@router.get("/locations", response_model=list[LocationStat])
async def get_top_locations(
    type: Literal["vacancy", "resume"] = Query(default="vacancy"),
    limit: int = Query(default=10, ge=1, le=50),
):
    """
    Географічний розподіл вакансій/резюме.
    Використовуй для bar chart або choropleth map.
    """
    join = _LOCATION_JOIN[type]
    query = f"""
        SELECT l.city_name, l.region, COUNT(t.id)::int AS count
        FROM dictionaries.locations l
        JOIN {join}
        GROUP BY l.id, l.city_name, l.region
        ORDER BY count DESC
        LIMIT $1;
    """
    async with AsyncDatabasePool.get_connection() as conn:
        rows = await conn.fetch(query, limit)
    return [dict(r) for r in rows]


@router.get("/salary-distribution", response_model=list[SalaryBucket])
async def get_salary_distribution(
    type: Literal["vacancy", "resume"] = Query(default="vacancy"),
):
    """
    Розподіл зарплат по діапазонах (гістограма).
    Використовуй для BarChart де X — діапазон, Y — кількість.
    """
    table = _SOURCE_TABLE[type]
    query = f"""
        SELECT
            range_label,
            min_usd,
            max_usd,
            COUNT(*)::int AS count
        FROM (
            SELECT
                mid,
                CASE
                    WHEN mid <  500  THEN '<$500'
                    WHEN mid < 1000  THEN '$500–1k'
                    WHEN mid < 2000  THEN '$1k–2k'
                    WHEN mid < 3000  THEN '$2k–3k'
                    WHEN mid < 5000  THEN '$3k–5k'
                    ELSE              '>$5k'
                END AS range_label,
                CASE
                    WHEN mid <  500  THEN NULL
                    WHEN mid < 1000  THEN 500
                    WHEN mid < 2000  THEN 1000
                    WHEN mid < 3000  THEN 2000
                    WHEN mid < 5000  THEN 3000
                    ELSE              5000
                END AS min_usd,
                CASE
                    WHEN mid <  500  THEN 500
                    WHEN mid < 1000  THEN 1000
                    WHEN mid < 2000  THEN 2000
                    WHEN mid < 3000  THEN 3000
                    WHEN mid < 5000  THEN 5000
                    ELSE              NULL
                END AS max_usd
            FROM (
                SELECT (
                    COALESCE(min_salary_usd_eq, max_salary_usd_eq) +
                    COALESCE(max_salary_usd_eq, min_salary_usd_eq)
                ) / 2.0 AS mid
                FROM {table}
                WHERE min_salary_usd_eq IS NOT NULL
                   OR max_salary_usd_eq IS NOT NULL
            ) raw
        ) bucketed
        GROUP BY range_label, min_usd, max_usd
        ORDER BY min_usd NULLS FIRST;
    """
    async with AsyncDatabasePool.get_connection() as conn:
        rows = await conn.fetch(query)
    return [dict(r) for r in rows]
