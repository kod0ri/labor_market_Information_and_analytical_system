"""
Утиліта нормалізації навичок.

Проблема яку вирішуємо:
    LLM повертає 'python', 'Python3', 'py', 'Python 3' — всі як різні навички.
    В результаті БД засмічується дублями, аналітика по навичках некоректна.

Рішення — дворівнева нормалізація:
    1. Пошук в таблиці skill_synonyms (точний збіг після trim+lower)
       → якщо знайшли, повертаємо canonical skill_id
    2. Пошук в dictionaries.skills по LOWER(name)
       → якщо знайшли, повертаємо той самий skill_id
    3. Якщо не знайшли — INSERT нової канонічної навички з нормалізованою назвою

Кеш зберігає результати щоб не ходити в БД на кожну навичку.
"""

import asyncio
from typing import Union

import asyncpg


# asyncpg повертає PoolConnectionProxy при acquire() з пулу, а не чистий Connection.
# PoolConnectionProxy проксує всі методи Connection, але є окремим типом.
# Використовуємо Union щоб Pylance не скаржився, або просто прибираємо строгу анотацію.
_ConnType = Union[asyncpg.Connection, asyncpg.pool.PoolConnectionProxy]


async def resolve_skill_id(
    conn: _ConnType,
    raw_name: str,
    category: str,
    cache: dict,
    cache_lock: asyncio.Lock,
) -> int | None:
    """
    Нормалізує назву навички і повертає canonical skill_id.

    Алгоритм:
        raw_name → strip → перевірка кешу → синонім у БД → LOWER match → INSERT

    Args:
        conn:       З'єднання з БД (Connection або PoolConnectionProxy).
        raw_name:   Сира назва від LLM ('python3', 'ReactJS', 'DRF' тощо).
        category:   'Hard' або 'Soft' — використовується тільки при INSERT нової навички.
        cache:      Спільний dict {'skills': {'python3': 42, ...}}.
        cache_lock: asyncio.Lock — захист кешу від race condition.

    Returns:
        skill_id або None якщо raw_name порожній.
    """
    if not raw_name or not raw_name.strip():
        return None

    cleaned = raw_name.strip()[:99]
    cache_key = cleaned.lower()  # ключ кешу завжди lower

    async with cache_lock:
        if cache_key in cache["skills"]:
            return cache["skills"][cache_key]

        # --- Рівень 1: Пошук через таблицю синонімів ---
        skill_id: int | None = await conn.fetchval(
            """
            SELECT skill_id
            FROM dictionaries.skill_synonyms
            WHERE LOWER(synonym) = LOWER($1)
            LIMIT 1;
            """,
            cleaned,
        )

        # --- Рівень 2: Пошук по LOWER(name) в канонічній таблиці ---
        if not skill_id:
            skill_id = await conn.fetchval(
                """
                SELECT id
                FROM dictionaries.skills
                WHERE LOWER(name) = LOWER($1)
                LIMIT 1;
                """,
                cleaned,
            )

        # --- Рівень 3: Нова навичка — INSERT з нормалізованою назвою ---
        if not skill_id:
            # Canonical form: зберігаємо як прийшло від LLM (вже trimmed),
            # але якщо це повністю lowercase — capitalize першу літеру.
            canonical = cleaned if not cleaned.islower() else cleaned.capitalize()

            skill_id = await conn.fetchval(
                """
                INSERT INTO dictionaries.skills (name, category)
                VALUES ($1, $2)
                ON CONFLICT DO NOTHING
                RETURNING id;
                """,
                canonical,
                category,
            )

            # ON CONFLICT DO NOTHING не повертає id — fetchval дасть None.
            # Це може статись якщо між нашим SELECT і INSERT хтось вставив той самий рядок.
            if not skill_id:
                skill_id = await conn.fetchval(
                    "SELECT id FROM dictionaries.skills WHERE LOWER(name) = LOWER($1);",
                    canonical,
                )

        # Кешуємо результат щоб наступний виклик з тим самим словом не ходив у БД
        if skill_id:
            cache["skills"][cache_key] = skill_id

        return skill_id