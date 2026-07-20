"""
Єдиний на процес пул з'єднань asyncpg - Singleton через classmethods/
class-level стан замість екземпляра, щоб і api/main.py (FastAPI lifespan),
і run_pipeline.py (Prefect flow), і кожен CLI-скрипт (nlp_vacancies.py тощо)
працювали з ОДНИМ пулом, ініціалізованим рівно один раз за процес.
"""

import os
import asyncpg
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()


class AsyncDatabasePool:
    _pool: asyncpg.Pool | None = None

    @classmethod
    async def initialize(cls) -> None:
        """Створює пул один раз - повторні виклики (з різних модулів, що
        незалежно імпортують цей клас) безпечно ігноруються завдяки перевірці
        `_pool is not None` вище."""
        if cls._pool is not None:
            return
        try:
            cls._pool = await asyncpg.create_pool(
                user=os.environ["DB_USER"],           # os.environ[...] (не .getenv) - навмисно КИДАЄ KeyError, якщо не задано
                password=os.environ["DB_PASSWORD"],
                database=os.environ["DB_NAME"],
                host=os.getenv("DB_HOST", "localhost"),   # host/port МОЖУТЬ мати розумний дефолт - .getenv доречний
                port=os.getenv("DB_PORT", "5432"),
                # min_size=5: пул тримає готові з'єднання навіть у простої, щоб
                # перший запит не чекав на встановлення TCP+auth з нуля;
                # max_size=30: стеля під пікове навантаження (search-запити +
                # паралельні db_semaphore(15) з'єднання NLP-стадії одночасно).
                min_size=5,
                max_size=30,
            )
            print("✅ Пул з'єднань з БД ініціалізовано.")
        except KeyError as e:
            # Обов'язкова змінна оточення відсутня (DB_USER/PASSWORD/NAME) -
            # явне повідомлення замість криптичного asyncpg-винятку нижче.
            print(f"❌ Відсутня змінна оточення {e}")
            raise
        except Exception as e:
            print(f"❌ Помилка підключення до БД: {e}")
            raise

    @classmethod
    @asynccontextmanager
    async def get_connection(cls):
        """Контекст-менеджер: віддає з'єднання з пулу й гарантовано повертає
        його назад (навіть при винятку) завдяки `async with cls._pool.acquire()`.
        Лінива ініціалізація - виклик до initialize() у CLI-скриптах, що
        забули явно ініціалізувати пул, все одно спрацює."""
        if cls._pool is None:
            await cls.initialize()
        assert cls._pool is not None    # для type checker'а - після initialize() пул гарантовано не None
        async with cls._pool.acquire() as conn:   # бере одне з'єднання з пулу; повертає його автоматично на виході
            yield conn

    @classmethod
    async def close_all(cls) -> None:
        """Закриває пул і скидає посилання - наступний initialize() створить
        новий пул з нуля (важливо для тестів і graceful shutdown)."""
        if cls._pool is not None:
            # Спершу відв'язуємо cls._pool від старого об'єкта, ПОТІМ закриваємо
            # його - так паралельна корутина, що встигне прочитати cls._pool
            # між цими рядками, або отримає None (і сама ре-ініціалізує), або
            # ще старий пул до закриття, але ніколи "напівзакритий" стан.
            pool, cls._pool = cls._pool, None
            await pool.close()
            print("🛑 Пул з'єднань закрито.")
