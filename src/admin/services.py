"""
Адміністративна підсистема — конкретні сервіси.

SRP (Single Responsibility Principle): кожен клас має рівно одну
відповідальність і одну причину для зміни.

OCP (Open/Closed Principle): нові адмін-сервіси додаються як нові класи,
що реалізують відповідний Protocol — без зміни існуючих класів.

LSP (Liskov Substitution Principle): усі конкретні класи можна замінити
на будь-яку іншу реалізацію свого протоколу без зміни поведінки системи.
"""

from typing import Any


class StatsService:
    """Збирає агреговану статистику по всіх таблицях системи."""

    async def get_system_stats(self, conn: Any) -> dict[str, Any]:
        vacancies_total = await conn.fetchval("SELECT COUNT(*) FROM core.vacancies")
        resumes_total = await conn.fetchval("SELECT COUNT(*) FROM core.resumes")
        skills_count = await conn.fetchval("SELECT COUNT(*) FROM dictionaries.skills")
        companies_count = await conn.fetchval("SELECT COUNT(*) FROM dictionaries.companies")
        locations_count = await conn.fetchval("SELECT COUNT(*) FROM dictionaries.locations")

        raw_vacancies_pending = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM staging.raw_vacancies s
            LEFT JOIN core.vacancies c ON s.id = c.staging_id
            WHERE s.raw_html IS NOT NULL AND s.raw_html != '' AND c.id IS NULL
            """
        )
        raw_resumes_pending = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM staging.raw_resumes s
            LEFT JOIN core.resumes c ON s.id = c.staging_id
            WHERE s.raw_text IS NOT NULL AND s.raw_text != '' AND c.id IS NULL
            """
        )

        return {
            "processed": {
                "vacancies": vacancies_total,
                "resumes": resumes_total,
            },
            "dictionaries": {
                "skills": skills_count,
                "companies": companies_count,
                "locations": locations_count,
            },
            "pipeline_queue": {
                "vacancies_pending": raw_vacancies_pending,
                "resumes_pending": raw_resumes_pending,
            },
        }


class FailureService:
    """Надає доступ до записів про помилки пайплайну та їх вирішення."""

    async def get_failures(self, conn: Any, limit: int = 50) -> list[dict[str, Any]]:
        rows = await conn.fetch(
            """
            SELECT id, record_type, staging_id, error_type, error_detail,
                   attempt_count, is_resolved, failed_at
            FROM staging.failed_records
            WHERE is_resolved = FALSE
            ORDER BY failed_at DESC
            LIMIT $1
            """,
            limit,
        )
        return [
            {
                "id": r["id"],
                "record_type": r["record_type"],
                "staging_id": r["staging_id"],
                "error_type": r["error_type"],
                "error_detail": r["error_detail"],
                "attempt_count": r["attempt_count"],
                "is_resolved": r["is_resolved"],
                "failed_at": r["failed_at"].isoformat() if r["failed_at"] else None,
            }
            for r in rows
        ]

    async def resolve_failure(self, conn: Any, failure_id: int) -> bool:
        result = await conn.execute(
            """
            UPDATE staging.failed_records
            SET is_resolved = TRUE, resolved_at = CURRENT_TIMESTAMP
            WHERE id = $1 AND is_resolved = FALSE
            """,
            failure_id,
        )
        return result == "UPDATE 1"


class PipelineService:
    """Моніторинг стану пайплайну: черга, помилки, останні операції."""

    async def get_pipeline_status(self, conn: Any) -> dict[str, Any]:
        pending_vacancies = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM staging.raw_vacancies s
            LEFT JOIN core.vacancies c ON s.id = c.staging_id
            WHERE s.raw_html IS NOT NULL AND s.raw_html != '' AND c.id IS NULL
            """
        )
        pending_resumes = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM staging.raw_resumes s
            LEFT JOIN core.resumes c ON s.id = c.staging_id
            WHERE s.raw_text IS NOT NULL AND s.raw_text != '' AND c.id IS NULL
            """
        )
        unresolved_failures = await conn.fetchval(
            "SELECT COUNT(*) FROM staging.failed_records WHERE is_resolved = FALSE"
        )
        failure_by_type = await conn.fetch(
            """
            SELECT error_type, COUNT(*) AS cnt
            FROM staging.failed_records
            WHERE is_resolved = FALSE
            GROUP BY error_type
            ORDER BY cnt DESC
            """
        )
        last_vacancy_row = await conn.fetchrow(
            "SELECT created_at FROM core.vacancies ORDER BY created_at DESC LIMIT 1"
        )
        last_resume_row = await conn.fetchrow(
            "SELECT created_at FROM core.resumes ORDER BY created_at DESC LIMIT 1"
        )

        return {
            "queue": {
                "vacancies_pending": pending_vacancies,
                "resumes_pending": pending_resumes,
            },
            "failures": {
                "total_unresolved": unresolved_failures,
                "by_type": {r["error_type"]: r["cnt"] for r in failure_by_type},
            },
            "last_processed": {
                "vacancy_at": (
                    last_vacancy_row["created_at"].isoformat()
                    if last_vacancy_row
                    else None
                ),
                "resume_at": (
                    last_resume_row["created_at"].isoformat()
                    if last_resume_row
                    else None
                ),
            },
        }
