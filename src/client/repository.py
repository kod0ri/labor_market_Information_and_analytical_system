"""
Клієнтська підсистема — Repository (Репозиторій).

Repository (Architectural Pattern): абстрагує доступ до бази даних від
бізнес-логіки. Facade і маршрути не містять SQL — вони делегують
роботу з даними репозиторіям.

ISP: IVacancyRepository та IResumeRepository — окремі інтерфейси,
бо хоча вони схожі — в SQL-запитах є суттєві відмінності
(vacancy_skills vs resume_skills, company_id присутній лише у вакансіях).
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class IVacancyRepository(Protocol):
    async def find_many(
        self, conn: Any, filters: dict[str, Any], limit: int, offset: int
    ) -> list[dict[str, Any]]: ...

    async def count(self, conn: Any, filters: dict[str, Any]) -> int: ...


@runtime_checkable
class IResumeRepository(Protocol):
    async def find_many(
        self, conn: Any, filters: dict[str, Any], limit: int, offset: int
    ) -> list[dict[str, Any]]: ...

    async def count(self, conn: Any, filters: dict[str, Any]) -> int: ...


class VacancyRepository:
    """Реалізація репозиторію вакансій — усі SQL-запити зосереджені тут."""

    async def find_many(
        self, conn: Any, filters: dict[str, Any], limit: int, offset: int
    ) -> list[dict[str, Any]]:
        where_clauses, params = self._build_where(filters)
        where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        params.extend([limit, offset])

        sql = f"""
            SELECT
                v.id,
                v.title,
                c.name          AS company_name,
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
            LEFT JOIN core.vacancy_skills vs ON v.id = vs.vacancy_id
            LEFT JOIN dictionaries.skills s ON vs.skill_id = s.id
            {where_sql}
            GROUP BY v.id, c.name, l.city_name, l.region
            ORDER BY v.created_at DESC
            LIMIT ${len(params) - 1} OFFSET ${len(params)}
        """
        rows = await conn.fetch(sql, *params)
        return [
            {**{k: v for k, v in dict(r).items() if k != "skills"},
             "skills": list(r["skills"]) if r["skills"] else []}
            for r in rows
        ]

    async def count(self, conn: Any, filters: dict[str, Any]) -> int:
        where_clauses, params = self._build_where(filters)
        where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        sql = f"""
            SELECT COUNT(DISTINCT v.id)
            FROM core.vacancies v
            LEFT JOIN dictionaries.locations l ON v.location_id = l.id
            {where_sql}
        """
        return await conn.fetchval(sql, *params)

    def _build_where(
        self, filters: dict[str, Any]
    ) -> tuple[list[str], list[Any]]:
        clauses: list[str] = []
        params: list[Any] = []

        if filters.get("skill"):
            params.append(filters["skill"].lower())
            clauses.append(
                f"""EXISTS (
                    SELECT 1 FROM core.vacancy_skills vs2
                    JOIN dictionaries.skills s2 ON vs2.skill_id = s2.id
                    WHERE vs2.vacancy_id = v.id AND LOWER(s2.name) = ${len(params)}
                )"""
            )
        if filters.get("location"):
            params.append(f"%{filters['location']}%")
            clauses.append(f"LOWER(l.city_name) LIKE LOWER(${len(params)})")
        if filters.get("min_salary_usd") is not None:
            params.append(filters["min_salary_usd"])
            clauses.append(
                f"COALESCE(v.min_salary_usd_eq, v.max_salary_usd_eq) >= ${len(params)}"
            )
        if filters.get("experience_max") is not None:
            params.append(filters["experience_max"])
            clauses.append(f"v.experience_years <= ${len(params)}")
        if filters.get("english_level"):
            params.append(filters["english_level"])
            clauses.append(f"v.english_level = ${len(params)}")
        if filters.get("source"):
            params.append(filters["source"])
            clauses.append(
                f"""EXISTS (
                    SELECT 1 FROM dictionaries.sources src
                    WHERE src.id = v.source_id AND src.name = ${len(params)}
                )"""
            )

        return clauses, params


class ResumeRepository:
    """Реалізація репозиторію резюме — усі SQL-запити зосереджені тут."""

    async def find_many(
        self, conn: Any, filters: dict[str, Any], limit: int, offset: int
    ) -> list[dict[str, Any]]:
        where_clauses, params = self._build_where(filters)
        where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        params.extend([limit, offset])

        sql = f"""
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
            LEFT JOIN core.resume_skills rs ON r.id = rs.resume_id
            LEFT JOIN dictionaries.skills s ON rs.skill_id = s.id
            {where_sql}
            GROUP BY r.id, l.city_name, l.region
            ORDER BY r.created_at DESC
            LIMIT ${len(params) - 1} OFFSET ${len(params)}
        """
        rows = await conn.fetch(sql, *params)
        return [
            {**{k: v for k, v in dict(r).items() if k != "skills"},
             "skills": list(r["skills"]) if r["skills"] else []}
            for r in rows
        ]

    async def count(self, conn: Any, filters: dict[str, Any]) -> int:
        where_clauses, params = self._build_where(filters)
        where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        sql = f"""
            SELECT COUNT(DISTINCT r.id)
            FROM core.resumes r
            LEFT JOIN dictionaries.locations l ON r.location_id = l.id
            {where_sql}
        """
        return await conn.fetchval(sql, *params)

    def _build_where(
        self, filters: dict[str, Any]
    ) -> tuple[list[str], list[Any]]:
        clauses: list[str] = []
        params: list[Any] = []

        if filters.get("skill"):
            params.append(filters["skill"].lower())
            clauses.append(
                f"""EXISTS (
                    SELECT 1 FROM core.resume_skills rs2
                    JOIN dictionaries.skills s2 ON rs2.skill_id = s2.id
                    WHERE rs2.resume_id = r.id AND LOWER(s2.name) = ${len(params)}
                )"""
            )
        if filters.get("location"):
            params.append(f"%{filters['location']}%")
            clauses.append(f"LOWER(l.city_name) LIKE LOWER(${len(params)})")
        if filters.get("min_salary_usd") is not None:
            params.append(filters["min_salary_usd"])
            clauses.append(
                f"COALESCE(r.min_salary_usd_eq, r.max_salary_usd_eq) >= ${len(params)}"
            )
        if filters.get("experience_max") is not None:
            params.append(filters["experience_max"])
            clauses.append(f"r.experience_years >= ${len(params)}")
        if filters.get("english_level"):
            params.append(filters["english_level"])
            clauses.append(f"r.english_level = ${len(params)}")
        if filters.get("source"):
            params.append(filters["source"])
            clauses.append(
                f"""EXISTS (
                    SELECT 1 FROM dictionaries.sources src
                    WHERE src.id = r.source_id AND src.name = ${len(params)}
                )"""
            )

        return clauses, params
