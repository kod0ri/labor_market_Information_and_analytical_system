import asyncio
import re
from typing import Union

import asyncpg
from bs4 import BeautifulSoup

_ConnType = Union[asyncpg.Connection, asyncpg.pool.PoolConnectionProxy]


def _parse_retry_after(error: Exception) -> float:
    text = str(error)
    # формат "1m43.5s" або просто "8s"
    m = re.search(r"try again in (?:(\d+)m)?([0-9.]+)s", text)
    if m:
        minutes = int(m.group(1) or 0)
        seconds = float(m.group(2))
        return minutes * 60 + seconds + 1.0
    # fallback: голе число без одиниць
    m = re.search(r"try again in ([0-9.]+)", text)
    if m:
        return float(m.group(1)) + 1.0
    return 10.0


def _sync_prepare_text(raw_text: str) -> str:
    return BeautifulSoup(raw_text, "lxml").get_text(separator=" ", strip=True)[:1500]


async def prepare_text_for_llm(raw_text: str | None) -> str:
    if not raw_text:
        return ""
    return await asyncio.to_thread(_sync_prepare_text, raw_text)


async def get_or_create_source(
    conn: _ConnType,
    name: str,
    cache: dict,
    cache_lock: asyncio.Lock,
) -> int | None:
    async with cache_lock:
        if name in cache.get("sources", {}):
            return cache["sources"][name]

    source_id = await conn.fetchval(
        """
        INSERT INTO dictionaries.sources (name)
        VALUES ($1)
        ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
        RETURNING id;
        """,
        name,
    )

    async with cache_lock:
        cache.setdefault("sources", {})[name] = source_id
    return source_id


async def get_or_create_location(
    conn: _ConnType,
    city_name: str | None,
    region: str | None,
    cache: dict,
    cache_lock: asyncio.Lock,
    country: str = "Ukraine",
) -> int | None:
    if not city_name:
        return None
    city_name = city_name[:99]
    country = (country or "Ukraine")[:99]
    cache_key = f"{country}::{city_name}"

    async with cache_lock:
        if cache_key in cache["locations"]:
            return cache["locations"][cache_key]

    loc_id = await conn.fetchval(
        """
        INSERT INTO dictionaries.locations (city_name, region, country)
        VALUES ($1, $2, $3)
        ON CONFLICT (city_name, country) DO UPDATE
            SET region = COALESCE(dictionaries.locations.region, EXCLUDED.region)
        RETURNING id;
        """,
        city_name, region, country,
    )
    if not loc_id:
        loc_id = await conn.fetchval(
            "SELECT id FROM dictionaries.locations WHERE city_name = $1 AND country = $2 LIMIT 1;",
            city_name, country,
        )

    async with cache_lock:
        cache["locations"][cache_key] = loc_id
    return loc_id


async def get_or_create_company(
    conn: _ConnType,
    name: str | None,
    industry: str | None,
    website: str | None,
    cache: dict,
    cache_lock: asyncio.Lock,
) -> int | None:
    """Резолв компанії (groq-free). Спільний для LLM- та прямого шляхів."""
    if not name:
        return None
    name = name[:200]

    async with cache_lock:
        if name in cache["companies"]:
            return cache["companies"][name]

    comp_id = await conn.fetchval(
        """
        INSERT INTO dictionaries.companies (name, industry, website_url)
        VALUES ($1, $2, $3)
        ON CONFLICT (name) DO UPDATE
            SET industry    = COALESCE(dictionaries.companies.industry, EXCLUDED.industry),
                website_url = COALESCE(dictionaries.companies.website_url, EXCLUDED.website_url)
        RETURNING id;
        """,
        name, industry, website,
    )
    if not comp_id:
        comp_id = await conn.fetchval(
            "SELECT id FROM dictionaries.companies WHERE name = $1;", name
        )

    async with cache_lock:
        cache["companies"][name] = comp_id
    return comp_id
