from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from src.db.database import AsyncDatabasePool

router = APIRouter()


class VacancyListItem(BaseModel):
    id: int
    title: str
    company_name: Optional[str]
    city_name: Optional[str]
    region: Optional[str]
    min_salary_usd_eq: Optional[float]
    max_salary_usd_eq: Optional[float]
    experience_years: Optional[int]
    english_level: Optional[str]
    created_at: datetime
    skills: list[str]


class PaginatedVacancies(BaseModel):
    total: int
    page: int
    limit: int
    items: list[VacancyListItem]


@router.get("/", response_model=PaginatedVacancies)
async def list_vacancies(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    skill: Optional[str] = Query(default=None, description="Фільтр за навичкою, напр. Python"),
    location: Optional[str] = Query(default=None, description="Фільтр за містом, напр. Київ"),
    min_salary_usd: Optional[int] = Query(default=None, description="Мінімальна зарплата в USD"),
    experience_years: Optional[int] = Query(default=None, description="Рівень досвіду в роках"),
):
    """
    Список вакансій з пагінацією та фільтрами.
    Використовуй для таблиці/карток з вакансіями та сайдбаром фільтрів.
    """
    offset = (page - 1) * limit
    params: list = []
    filters: list[str] = []

    if skill:
        params.append(skill.lower())
        filters.append(f"""
            EXISTS (
                SELECT 1 FROM core.vacancy_skills vs
                JOIN dictionaries.skills s ON vs.skill_id = s.id
                WHERE vs.vacancy_id = v.id AND LOWER(s.name) = ${len(params)}
            )
        """)

    if location:
        params.append(f"%{location}%")
        filters.append(f"LOWER(l.city_name) LIKE LOWER(${len(params)})")

    if min_salary_usd is not None:
        params.append(min_salary_usd)
        filters.append(f"COALESCE(v.min_salary_usd_eq, v.max_salary_usd_eq) >= ${len(params)}")

    if experience_years is not None:
        params.append(experience_years)
        filters.append(f"v.experience_years <= ${len(params)}")

    where_clause = "WHERE " + " AND ".join(filters) if filters else ""

    count_query = f"""
        SELECT COUNT(*)::int
        FROM core.vacancies v
        LEFT JOIN dictionaries.companies c ON v.company_id = c.id
        LEFT JOIN dictionaries.locations l ON v.location_id = l.id
        {where_clause};
    """

    params_for_list = params + [limit, offset]
    list_query = f"""
        SELECT
            v.id,
            v.title,
            c.name         AS company_name,
            l.city_name,
            l.region,
            v.min_salary_usd_eq,
            v.max_salary_usd_eq,
            v.experience_years,
            v.english_level,
            v.created_at,
            COALESCE(
                ARRAY_AGG(s.name ORDER BY s.name) FILTER (WHERE s.name IS NOT NULL),
                ARRAY[]::text[]
            ) AS skills
        FROM core.vacancies v
        LEFT JOIN dictionaries.companies c ON v.company_id = c.id
        LEFT JOIN dictionaries.locations l ON v.location_id = l.id
        LEFT JOIN core.vacancy_skills   vs ON v.id = vs.vacancy_id
        LEFT JOIN dictionaries.skills    s ON vs.skill_id = s.id
        {where_clause}
        GROUP BY v.id, c.name, l.city_name, l.region
        ORDER BY v.created_at DESC
        LIMIT ${len(params_for_list) - 1} OFFSET ${len(params_for_list)};
    """

    async with AsyncDatabasePool.get_connection() as conn:
        total = await conn.fetchval(count_query, *params)
        rows = await conn.fetch(list_query, *params_for_list)

    items = [
        VacancyListItem(
            **{k: v for k, v in dict(r).items() if k != "skills"},
            skills=list(r["skills"]) if r["skills"] else [],
        )
        for r in rows
    ]

    return PaginatedVacancies(total=total, page=page, limit=limit, items=items)
