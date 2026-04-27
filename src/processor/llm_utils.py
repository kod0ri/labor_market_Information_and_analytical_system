import asyncio
import re
from typing import Union

import asyncpg
from bs4 import BeautifulSoup

_ConnType = Union[asyncpg.Connection, asyncpg.pool.PoolConnectionProxy]


def _parse_retry_after(error: Exception) -> float:
    match = re.search(r"try again in ([0-9.]+)(s|ms)", str(error))
    if match:
        value, unit = float(match.group(1)), match.group(2)
        return (value if unit == "s" else value / 1000) + 0.5
    return 10.0


def _sync_prepare_text(raw_text: str) -> str:
    return BeautifulSoup(raw_text, "lxml").get_text(separator=" ", strip=True)[:1500]


async def prepare_text_for_llm(raw_text: str | None) -> str:
    if not raw_text:
        return ""
    return await asyncio.to_thread(_sync_prepare_text, raw_text)


async def get_or_create_location(
    conn: _ConnType,
    city_name: str | None,
    region: str | None,
    cache: dict,
    cache_lock: asyncio.Lock,
) -> int | None:
    if not city_name:
        return None
    city_name = city_name[:99]
    cache_key = f"{city_name}|{region or ''}"

    async with cache_lock:
        if cache_key in cache["locations"]:
            return cache["locations"][cache_key]

    loc_id = await conn.fetchval(
        """
        INSERT INTO dictionaries.locations (city_name, region, country)
        VALUES ($1, $2, 'Ukraine')
        ON CONFLICT (city_name, COALESCE(region, ''), country) DO UPDATE
            SET region = COALESCE(dictionaries.locations.region, EXCLUDED.region)
        RETURNING id;
        """,
        city_name, region,
    )
    if not loc_id:
        loc_id = await conn.fetchval(
            "SELECT id FROM dictionaries.locations WHERE city_name = $1 LIMIT 1;",
            city_name,
        )

    async with cache_lock:
        cache["locations"][cache_key] = loc_id
    return loc_id
