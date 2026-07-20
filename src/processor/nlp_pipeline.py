"""
Спільний оркестратор LLM-обробки одного staging-запису.

nlp_vacancies і nlp_resumes мали ідентичний каркас: перевірка бюджету, цикл
спроб, виклик каскаду, витяг JSON, валідація схемою, обробка
AllProvidersExhausted / AllProvidersBusy / ValidationError / інших помилок,
запис провалів і retry. Відрізнявся лише крок запису в БД (різні таблиці й
колонки). Тут винесено весь спільний каркас; специфіка передається через
`persist` (виконується всередині транзакції) і `schema_cls`.

Тримання цієї логіки в одному місці робить її тестованою (фейковий `complete`
+ фейковий `persist`, без БД і без мережі) — див. tests/test_nlp_pipeline.py.
"""

import asyncio
import re
from typing import Awaitable, Callable

from pydantic import BaseModel, ValidationError

from src.db.database import AsyncDatabasePool
from src.processor.failure_tracker import record_failure
from src.processor.llm_cascade import (
    complete,
    any_available,
    budget_summary,
    AllProvidersExhausted,
    AllProvidersBusy,
)

# persist(conn, ai_data) виконує запис у БД у межах транзакції й повертає
# короткий підпис запису (напр. назву посади) для лог-рядка про успіх.
PersistFn = Callable[[object, BaseModel], Awaitable[str]]


async def run_llm_record(
    *,
    staging_id: int,
    record_type: str,
    messages: list[dict],
    schema_cls: type[BaseModel],
    db_semaphore: asyncio.Semaphore,
    persist: PersistFn,
    max_attempts: int = 3,
) -> bool:
    """
    Обробляє один запис через LLM-каскад і зберігає результат через `persist`.
    Повертає True при успіху, False — якщо запис відкладено (ліміти) або провалено.
    Семантика повністю відповідає попереднім process_single_* у nlp_*.
    """
    if not any_available():
        print(f"   ⏸️ [ID {staging_id}] LLM-бюджет усіх провайдерів вичерпано ({budget_summary()}), пропускаємо.")
        return False

    transient_busy = False       # True, поки причина невдачі - зайнятість провайдерів, не якість LLM
    for attempt in range(max_attempts):    # до 3 спроб на один запис (max_attempts за замовчуванням)
        try:
            response_text, provider, model = await complete(messages)  # текст відповіді + хто саме відповів

            # LLM іноді огортає JSON у markdown-огорожі (```json ... ```) чи додає
            # пояснювальний текст перед/після, попри інструкцію "лише JSON" -
            # витягуємо перший фігурний блок замість повного json.loads(response_text).
            match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if not match:
                raise ValueError("LLM не повернула валідний JSON")

            # Pydantic-валідація: некоректні типи/відсутні поля/галюцинації
            # структури впадуть у ValidationError нижче й підуть на retry.
            ai_data = schema_cls.model_validate_json(match.group(0))

            # db_semaphore обмежує паралельні З'ЄДНАННЯ з БД (тут - запис),
            # окремо від LLM_CONCURRENCY, що обмежує паралельні LLM-виклики -
            # ці два ресурси мають різні природні стелі й не повинні ділити один ліміт.
            async with db_semaphore:
                async with AsyncDatabasePool.get_connection() as conn:
                    async with conn.transaction():
                        label = await persist(conn, ai_data)

            print(f"   💾 Успішно [{provider}/{model}]: [ID {staging_id}] {label}...")
            return True

        except AllProvidersExhausted:
            print(f"   ⏸️ [ID {staging_id}] Бюджет усіх провайдерів вичерпано ({budget_summary()}), пропускаємо.")
            return False

        except AllProvidersBusy as e:
            transient_busy = True    # позначаємо: причина - зовнішня зайнятість, не помилка даних
            print(f"   ⏳ [ID {staging_id}] Усі провайдери зайняті (спроба {attempt + 1}/{max_attempts}). Чекаємо {e.retry_after:.1f}s...")
            await asyncio.sleep(e.retry_after)   # чекаємо стільки, скільки підказав каскад, і йдемо на новий attempt

        except ValidationError as ve:
            # Схемна помилка - не тимчасова зайнятість провайдера, тож скидаємо
            # transient_busy: якщо це остання спроба, запис піде у failed_records,
            # а не мовчки залишиться "на потім" як при rate-limit.
            transient_busy = False
            failed_fields = [str(err.get("loc", [""])[0]) for err in ve.errors()]  # які саме поля не пройшли валідацію
            detail = f"fields={failed_fields}"    # короткий рядок-діагноз для failed_records.error_detail
            print(f"   ⚠️ [ID {staging_id}] Галюцинація LLM (спроба {attempt + 1}/{max_attempts}). {detail}")
            if attempt == max_attempts - 1:
                async with db_semaphore:
                    async with AsyncDatabasePool.get_connection() as conn:
                        await record_failure(conn, record_type, staging_id, "validation", detail, attempt + 1)
            await asyncio.sleep(1)

        except Exception as e:
            print(f"   ❌ [ID {staging_id}] Помилка: {e}")
            async with db_semaphore:
                async with AsyncDatabasePool.get_connection() as conn:
                    await record_failure(conn, record_type, staging_id, "unknown", str(e), attempt + 1)
            return False

    # transient_busy лишається True тільки якщо ВСІ max_attempts спроб впали саме
    # через AllProvidersBusy (кожна ValidationError/Exception одразу скидає його
    # в False) - тобто причина повністю зовнішня (ліміти), не якість LLM-виводу.
    # Вичерпали спроби лише через rate-limit — НЕ фіксуємо провал,
    # лишаємо запис у staging на наступний прогін.
    if transient_busy:
        print(f"   ⏸️ [ID {staging_id}] Ліміти провайдерів — відкладаємо на наступний прогін.")
        return False

    print(f"   💀 [ID {staging_id}] Вичерпано {max_attempts} спроби.")
    async with db_semaphore:
        async with AsyncDatabasePool.get_connection() as conn:
            await record_failure(
                conn, record_type, staging_id,
                "validation", f"Exhausted {max_attempts} attempts", max_attempts,
            )
    return False
