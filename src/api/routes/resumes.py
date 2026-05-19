from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from src.db.database import AsyncDatabasePool

router = APIRouter()


class ResumeListItem(BaseModel):
    id: int
    title: str
    city_name: Optional[str]
    region: Optional[str]
    min_salary_usd_eq: Optional[float]
    max_salary_usd_eq: Optional[float]
    experience_years: Optional[int]
    english_level: Optional[str]
    created_at: datetime
    skills: list[str]


class PaginatedResumes(BaseModel):
    total: int
    page: int
    limit: int
    items: list[ResumeListItem]


@router.get("/", response_model=PaginatedResumes)
async def list_resumes(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    skill: Optional[str] = Query(default=None, description="Фільтр за навичкою, напр. Python"),
    location: Optional[str] = Query(default=None, description="Фільтр за містом, напр. Київ"),
    min_salary_usd: Optional[int] = Query(default=None, description="Мінімальна зарплата в USD"),
    experience_years: Optional[int] = Query(default=None, description="Досвід не менше N років"),
):
    """
    Список резюме з пагінацією та фільтрами.
    """
    offset = (page - 1) * limit
    params: list = []
    filters: list[str] = []

    if skill:
        params.append(skill.lower())
        filters.append(f"""
            EXISTS (
                SELECT 1 FROM core.resume_skills rs
                JOIN dictionaries.skills s ON rs.skill_id = s.id
                WHERE rs.resume_id = r.id AND LOWER(s.name) = ${len(params)}
            )
        """)

    if location:
        params.append(f"%{location}%")
        filters.append(f"LOWER(l.city_name) LIKE LOWER(${len(params)})")

    if min_salary_usd is not None:
        params.append(min_salary_usd)
        filters.append(f"COALESCE(r.min_salary_usd_eq, r.max_salary_usd_eq) >= ${len(params)}")

    if experience_years is not None:
        params.append(experience_years)
        filters.append(f"r.experience_years >= ${len(params)}")

    where_clause = "WHERE " + " AND ".join(filters) if filters else ""

    count_query = f"""
        SELECT COUNT(*)::int
        FROM core.resumes r
        LEFT JOIN dictionaries.locations l ON r.location_id = l.id
        {where_clause};
    """

    params_for_list = params + [limit, offset]
    list_query = f"""
        SELECT
            r.id,
            r.title,
            l.city_name,
            l.region,
            r.min_salary_usd_eq,
            r.max_salary_usd_eq,
            r.experience_years,
            r.english_level,
            r.created_at,
            COALESCE(
                ARRAY_AGG(s.name ORDER BY s.name) FILTER (WHERE s.name IS NOT NULL),
                ARRAY[]::text[]
            ) AS skills
        FROM core.resumes r
        LEFT JOIN dictionaries.locations l ON r.location_id = l.id
        LEFT JOIN core.resume_skills    rs ON r.id = rs.resume_id
        LEFT JOIN dictionaries.skills    s ON rs.skill_id = s.id
        {where_clause}
        GROUP BY r.id, l.city_name, l.region
        ORDER BY r.created_at DESC
        LIMIT ${len(params_for_list) - 1} OFFSET ${len(params_for_list)};
    """

    async with AsyncDatabasePool.get_connection() as conn:
        total = await conn.fetchval(count_query, *params)
        rows = await conn.fetch(list_query, *params_for_list)

    items = [
        ResumeListItem(
            **{k: v for k, v in dict(r).items() if k != "skills"},
            skills=list(r["skills"]) if r["skills"] else [],
        )
        for r in rows
    ]

    return PaginatedResumes(total=total, page=page, limit=limit, items=items)
