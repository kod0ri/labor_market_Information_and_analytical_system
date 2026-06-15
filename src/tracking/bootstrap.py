"""
Bootstrap трекінгу — ідемпотентне створення таблиці analytics.visits.

Схема analytics вже існує (init_db/00_schemas.sql). Для вже наповнених баз,
де init_db/*.sql не виконуються повторно, таблиця створюється тут на старті.
"""

from src.db.database import AsyncDatabasePool

_DDL = """
CREATE TABLE IF NOT EXISTS analytics.visits (
    id         BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    visitor_id UUID        NOT NULL,
    path       VARCHAR(200),
    seen_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_visits_seen_at
    ON analytics.visits (seen_at DESC);

CREATE INDEX IF NOT EXISTS idx_visits_visitor_seen
    ON analytics.visits (visitor_id, seen_at DESC);
"""


async def ensure_tracking_schema() -> None:
    async with AsyncDatabasePool.get_connection() as conn:
        await conn.execute(_DDL)
