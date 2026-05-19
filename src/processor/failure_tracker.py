"""
Утиліта запису невдалих обробок у staging.failed_records.

Замінює "print(❌ помилка)" на персистентний запис у БД.
Після фіксу причини помилки — можна зробити retry тільки по failed записам.
"""

from typing import Literal
from asyncpg.pool import PoolConnectionProxy
import asyncpg

_ConnType = asyncpg.Connection | PoolConnectionProxy

RecordType = Literal["vacancy", "resume"]
ErrorType = Literal["validation", "rate_limit", "unknown"]

UPSERT_FAILED_SQL = """
    INSERT INTO staging.failed_records
        (record_type, staging_id, attempt_count, error_type, error_detail)
    VALUES ($1, $2, $3, $4, $5)
    ON CONFLICT (record_type, staging_id)
    WHERE is_resolved = FALSE
    DO UPDATE SET
        attempt_count = staging.failed_records.attempt_count + 1,
        error_type    = EXCLUDED.error_type,
        error_detail  = EXCLUDED.error_detail,
        failed_at     = CURRENT_TIMESTAMP;
"""

RESOLVE_FAILED_SQL = """
    UPDATE staging.failed_records
    SET is_resolved = TRUE,
        resolved_at = CURRENT_TIMESTAMP
    WHERE record_type = $1
      AND staging_id  = $2
      AND is_resolved = FALSE;
"""


async def record_failure(
    conn: _ConnType,
    record_type: RecordType,
    staging_id: int,
    error_type: ErrorType,
    error_detail: str,
    attempt_count: int = 1,
) -> None:
    """
    Записує або оновлює запис про помилку обробки.
    При повторній помилці того самого запису — інкрементує attempt_count.
    """
    await conn.execute(
        UPSERT_FAILED_SQL,
        record_type,
        staging_id,
        attempt_count,
        error_type,
        error_detail[:2000],  # обрізаємо щоб не перевищити розумний розмір
    )


async def mark_resolved(
    conn: _ConnType,
    record_type: RecordType,
    staging_id: int,
) -> None:
    """
    Позначає запис як вирішений після успішного retry.
    Викликається з NLP процесора при успішному збереженні.
    """
    await conn.execute(RESOLVE_FAILED_SQL, record_type, staging_id)
