"""
Утиліта нормалізації навичок.

FIX #7: Двофазний підхід до лока.
Проблема оригіналу: весь asyncpg IO (fetchval × 3) виконувався ВСЕРЕДИНІ
cache_lock — це serializes весь pipeline через один лок на мережеві операції.

Рішення:
  Фаза 1 — перевірка кешу (мікросекунди, під локом)
  Фаза 2 — запити до БД (мілісекунди, БЕЗ лока)
  Фаза 3 — запис в кеш (мікросекунди, під локом)

Race condition при паралельному INSERT вирішується через ON CONFLICT DO NOTHING
і fallback SELECT після нього.
"""

import asyncio
from typing import Union

import asyncpg

_ConnType = Union[asyncpg.Connection, asyncpg.pool.PoolConnectionProxy]


async def resolve_skill_id(
    conn: _ConnType,
    raw_name: str,
    category: str,
    cache: dict,
    cache_lock: asyncio.Lock,
) -> int | None:
    if not raw_name or not raw_name.strip():
        return None

    cleaned = raw_name.strip()[:99]
    cache_key = cleaned.lower()

    # Фаза 1: читання кешу (швидко, під локом)
    async with cache_lock:
        if cache_key in cache["skills"]:
            return cache["skills"][cache_key]

    # Фаза 2: запити до БД (повільно, БЕЗ лока — не блокуємо інші задачі)
    skill_id: int | None = await conn.fetchval(
        """
        SELECT skill_id FROM dictionaries.skill_synonyms
        WHERE LOWER(synonym) = LOWER($1)
        LIMIT 1;
        """,
        cleaned,
    )

    if not skill_id:
        skill_id = await conn.fetchval(
            """
            SELECT id FROM dictionaries.skills
            WHERE LOWER(name) = LOWER($1)
            LIMIT 1;
            """,
            cleaned,
        )

    if not skill_id:
        canonical = cleaned if not cleaned.islower() else cleaned.capitalize()
        skill_id = await conn.fetchval(
            """
            INSERT INTO dictionaries.skills (name, category)
            VALUES ($1, $2)
            ON CONFLICT DO NOTHING
            RETURNING id;
            """,
            canonical, category,
        )
        if not skill_id:
            # Хтось вставив між нашим SELECT і INSERT — просто читаємо
            skill_id = await conn.fetchval(
                "SELECT id FROM dictionaries.skills WHERE LOWER(name) = LOWER($1);",
                canonical,
            )

    # Фаза 3: запис в кеш (під локом)
    if skill_id:
        async with cache_lock:
            cache["skills"][cache_key] = skill_id

    return skill_id