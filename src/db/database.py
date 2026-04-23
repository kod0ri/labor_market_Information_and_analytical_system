import os
import asyncpg
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()


class AsyncDatabasePool:
    _pool: asyncpg.Pool | None = None

    @classmethod
    async def initialize(cls):
        """Асинхронна ініціалізація пулу з'єднань."""
        if cls._pool is None:
            try:
                cls._pool = await asyncpg.create_pool(
                    user=os.getenv("DB_USER", "postgres"),
                    password=os.getenv("DB_PASSWORD", "postgres"),
                    database=os.getenv("DB_NAME", "postgres"),
                    host=os.getenv("DB_HOST", "localhost"),
                    port=os.getenv("DB_PORT", "5432"),
                    min_size=5,  # Збільшено мінімальну кількість
                    max_size=30, # Збільшено максимальну кількість для паралельних тасок
                )
                print("✅ Асинхронний пул з'єднань з БД ініціалізовано.")
            except Exception as e:
                print(f"❌ Помилка підключення до БД: {e}")
                raise

    @classmethod
    @asynccontextmanager
    async def get_connection(cls):
        """Асинхронний контекстний менеджер для отримання з'єднання з пулу."""
        if cls._pool is None:
            await cls.initialize()

        assert cls._pool is not None

        # Контекстний менеджер гарантує повернення з'єднання в пул
        async with cls._pool.acquire() as conn:
            yield conn

    @classmethod
    async def close_all(cls):
        """Закриття пулу."""
        if cls._pool is not None:
            await cls._pool.close()
            cls._pool = None
            print("🛑 Пул з'єднань закрито.")