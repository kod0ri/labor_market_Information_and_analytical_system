import os
import asyncio
import asyncpg
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()

class AsyncDatabasePool:
    _pool: asyncpg.Pool | None = None
    _init_lock: asyncio.Lock = asyncio.Lock()

    @classmethod
    async def initialize(cls) -> None:
        """Потокобезпечна асинхронна ініціалізація пулу з'єднань."""
        async with cls._init_lock:
            if cls._pool is None:
                try:
                    cls._pool = await asyncpg.create_pool(
                        user=os.environ["DB_USER"],         # Жодних дефолтів. Немає конфігу - падаємо.
                        password=os.environ["DB_PASSWORD"],
                        database=os.environ["DB_NAME"],
                        host=os.getenv("DB_HOST", "localhost"),
                        port=os.getenv("DB_PORT", "5432"),
                        min_size=5,
                        max_size=30,
                    )
                    print("✅ Асинхронний пул з'єднань з БД ініціалізовано.")
                except KeyError as e:
                    print(f"❌ Критична помилка: Відсутня змінна оточення {e}")
                    raise
                except Exception as e:
                    print(f"❌ Помилка підключення до БД: {e}")
                    raise

    @classmethod
    @asynccontextmanager
    async def get_connection(cls):
        """Отримання з'єднання з пулу. Гарантує ініціалізацію."""
        if cls._pool is None:
            await cls.initialize()

        assert cls._pool is not None

        async with cls._pool.acquire() as conn:
            yield conn

    @classmethod
    async def close_all(cls) -> None:
        """Безпечне закриття пулу."""
        async with cls._init_lock:
            if cls._pool is not None:
                await cls._pool.close()
                cls._pool = None
                print("🛑 Пул з'єднань закрито.")