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

# LLM стабільно позначає особистісні якості як Hard (дефолт схеми) — словник
# страхує категорію на вставці, щоб hard/soft-аналітика не з'їжджала.
_SOFT_SKILL_NAMES: set[str] = {
    "комунікація", "комунікабельність", "communication", "communication skills",
    "лідерство", "leadership", "ініціативність", "впевненість", "відповідальність",
    "уважність", "стресостійкість", "командна робота", "робота в команді", "teamwork",
    "тайм-менеджмент", "time management", "критичне мислення", "critical thinking",
    "адаптивність", "організованість", "пунктуальність", "самостійність",
    "креативність", "creativity", "problem solving", "вирішення проблем",
    "багатозадачність", "multitasking", "мотивація", "емпатія", "гнучкість",
    "дисциплінованість", "аналітичне мислення", "переговори", "презентації",
    "менторство", "mentoring", "самонавчання", "навчання інших",
}
_SOFT_SKILL_SUBSTRINGS: tuple[str, ...] = (
    "комунікаб", "відповідальн", "ініціатив", "стресостійк", "лідерськ",
)


def _normalize_category(name: str, category: str) -> str:
    """Виправляє категорію навички за словником/підрядками, якщо LLM
    помилково позначила очевидну soft-skill як Hard (див. docstring модуля)."""
    if category == "Soft":            # LLM вже сама вгадала правильно - нічого виправляти
        return "Soft"
    low = name.strip().lower()        # регістронезалежне порівняння зі словником нижче
    if low in _SOFT_SKILL_NAMES or any(m in low for m in _SOFT_SKILL_SUBSTRINGS):  # точний збіг АБО підрядок кореня слова
        return "Soft"
    return category if category in ("Hard", "Soft") else "Hard"   # невідома категорія від LLM → безпечний дефолт Hard


async def resolve_skill_id(
    conn: _ConnType,
    raw_name: str,
    category: str,
    cache: dict,
    cache_lock: asyncio.Lock,
) -> int | None:
    """Резолвить сиру назву навички в dictionaries.skills.id.

    Порядок пошуку: 1) skill_synonyms (LLM видає "JS"/"Node"/"ReactJS" - усе
    мапиться на канонічний skill_id через таблицю синонімів), 2) точний
    збіг у skills, 3) якщо ніде нема - створюємо нову навичку. Без цього
    кроку кожен варіант написання став би окремим рядком і зіпсував gap-аналіз.
    """
    if not raw_name or not raw_name.strip():   # порожня/пробільна назва - нема що резолвити
        return None

    cleaned = raw_name.strip()[:99]     # обрізаємо під довжину колонки VARCHAR(99)
    cache_key = cleaned.lower()         # ключ кешу регістронезалежний (Python != Python у БД без LOWER())

    # Фаза 1: читання кешу (швидко, під локом)
    async with cache_lock:
        if cache_key in cache["skills"]:
            return cache["skills"][cache_key]

    # Фаза 2: запити до БД (повільно, БЕЗ лока — не блокуємо інші задачі)
    skill_id: int | None = await conn.fetchval(     # крок 1 - чи є вже такий СИНОНІМ (JS→JavaScript тощо)
        """
        SELECT skill_id FROM dictionaries.skill_synonyms
        WHERE LOWER(synonym) = LOWER($1)
        LIMIT 1;
        """,
        cleaned,
    )

    if not skill_id:                      # синоніма нема - пробуємо точний збіг канонічної назви
        skill_id = await conn.fetchval(
            """
            SELECT id FROM dictionaries.skills
            WHERE LOWER(name) = LOWER($1)
            LIMIT 1;
            """,
            cleaned,
        )

    if not skill_id:    # навички справді ще нема в довіднику - створюємо нову
        canonical = cleaned if not cleaned.islower() else cleaned.capitalize()   # "python" → "Python", але "JS" лишаємо як є
        skill_id = await conn.fetchval(
            """
            INSERT INTO dictionaries.skills (name, category)
            VALUES ($1, $2)
            ON CONFLICT DO NOTHING
            RETURNING id;
            """,
            canonical, _normalize_category(canonical, category),   # категорія перевірена/виправлена перед записом
        )
        if not skill_id:
            # Хтось вставив між нашим SELECT і INSERT — просто читаємо
            skill_id = await conn.fetchval(
                "SELECT id FROM dictionaries.skills WHERE LOWER(name) = LOWER($1);",
                canonical,
            )

    # Фаза 3: запис в кеш (під локом)
    if skill_id:                    # None лишаємо некешованим - раптова помилка БД не застрягне як "постійний" None
        async with cache_lock:
            cache["skills"][cache_key] = skill_id

    return skill_id