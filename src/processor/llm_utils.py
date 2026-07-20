"""
Спільні допоміжні функції для NLP-обробки: підготовка тексту під LLM-промпт,
парсинг retry-after з помилок провайдерів, get_or_create для трьох довідників
(companies/locations/sources) - усі три ідентичні за формою (INSERT ...
ON CONFLICT DO UPDATE ... RETURNING id, з in-memory кешем поверх), бо
покликані вирішувати ту саму задачу нормалізації: не плодити дублікат
запису в dictionaries.* для кожної вакансії/резюме з тим самим текстовим
значенням (див. слайд «База даних і нормалізація» презентації).
"""

import asyncio
import re
from typing import Union

import asyncpg
from bs4 import BeautifulSoup

_ConnType = Union[asyncpg.Connection, asyncpg.pool.PoolConnectionProxy]


def _parse_retry_after(error: Exception) -> float:
    """Витягує рекомендовану провайдером паузу з тексту помилки 429.

    Провайдери (Cerebras/Groq/...) повертають людський текст на кшталт
    "please try again in 1m43.5s" - тут немає структурованого retry-after
    заголовка, тому парсимо рядок регуляркою. Якщо формат не впізнано -
    консервативний дефолт 10s, аби не спамити провайдера одразу повторно.
    """
    text = str(error)   # повний текст винятку openai-клієнта, у ньому шукаємо підказку часу
    # формат "1m43.5s" або просто "8s"
    m = re.search(r"try again in (?:(\d+)m)?([0-9.]+)s", text)   # група 1 - хвилини (опційно), група 2 - секунди
    if m:
        minutes = int(m.group(1) or 0)     # якщо хвилин нема в тексті - 0
        seconds = float(m.group(2))        # секунди завжди присутні у знайденому збігу
        # +1.0s - невеликий запас поверх точного часу, щоб не поцілити
        # рівно в момент, коли лічильник провайдера ще не скинувся.
        return minutes * 60 + seconds + 1.0
    # fallback: голе число без одиниць
    m = re.search(r"try again in ([0-9.]+)", text)   # рідший формат без "m"/"s" суфіксів
    if m:
        return float(m.group(1)) + 1.0
    return 10.0    # текст помилки взагалі не містить підказки - консервативний дефолт


def _sync_prepare_text(raw_text: str) -> str:
    """Синхронна (CPU-bound) частина очищення HTML - виконується в окремому
    потоці через asyncio.to_thread, щоб не блокувати event loop на парсингу
    великих HTML-сторінок під час паралельної обробки багатьох записів."""
    # Обрізаємо до 1500 символів: досить контексту для LLM-екстракції полів,
    # але не роздуваємо промпт (менше токенів = менше витрат денного бюджету).
    return BeautifulSoup(raw_text, "lxml").get_text(separator=" ", strip=True)[:1500]


async def prepare_text_for_llm(raw_text: str | None) -> str:
    """Async-обгортка над _sync_prepare_text для виклику з корутин без
    блокування event loop."""
    if not raw_text:
        return ""
    return await asyncio.to_thread(_sync_prepare_text, raw_text)


async def get_or_create_source(
    conn: _ConnType,
    name: str,
    cache: dict,
    cache_lock: asyncio.Lock,
) -> int | None:
    """Резолвить джерело (work.ua/DOU.ua/robota.ua) у dictionaries.sources.id.

    ON CONFLICT DO UPDATE SET name = EXCLUDED.name замість DO NOTHING - трюк,
    щоб RETURNING id спрацював і при конфлікті теж (звичайний DO NOTHING
    нічого не повертає для вже існуючого рядка, довелося б робити окремий
    SELECT). cache/cache_lock - щоб не бити той самий INSERT по 200 разів
    за батч для тих самих кількох назв джерел.
    """
    async with cache_lock:                        # ФАЗА 1: швидка перевірка кешу (мікросекунди, під локом)
        if name in cache.get("sources", {}):
            return cache["sources"][name]

    source_id = await conn.fetchval(               # ФАЗА 2: запит до БД БЕЗ лока (не блокує інші задачі на час I/O)
        """
        INSERT INTO dictionaries.sources (name)
        VALUES ($1)
        ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
        RETURNING id;
        """,
        name,
    )

    async with cache_lock:                         # ФАЗА 3: записуємо знайдений/створений id назад у кеш
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
    """Резолвить назву міста (+опційно область) у dictionaries.locations.id.

    COALESCE у SET region = ... - при повторному записі того самого міста
    НЕ затираємо вже відому область значенням NULL/іншим від нового джерела;
    перший непорожній region перемагає й лишається назавжди.
    """
    if not city_name:            # LLM повернула null - немає що резолвити
        return None
    city_name = city_name[:99]              # обрізаємо під довжину колонки VARCHAR(99) у БД
    country = (country or "Ukraine")[:99]   # дефолт "Ukraine", якщо не задано
    cache_key = f"{country}::{city_name}"   # складений ключ кешу (той самий город у різних країнах - різні записи)

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
        # RETURNING інколи не повертає рядок при перегонах двох паралельних
        # INSERT-ів на той самий (city_name, country) під конкурентним
        # апдейтом - підстраховуємось явним SELECT замість падіння на NULL id.
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
    if not name:              # LLM не витягла назву компанії з тексту
        return None
    name = name[:200]         # обрізаємо під довжину колонки VARCHAR(200)

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
