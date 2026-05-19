import os
import asyncpg
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()


class AsyncDatabasePool:
    _pool: asyncpg.Pool | None = None

    @classmethod
    async def initialize(cls) -> None:
        if cls._pool is not None:
            return
        try:
            cls._pool = await asyncpg.create_pool(
                user=os.environ["DB_USER"],
                password=os.environ["DB_PASSWORD"],
                database=os.environ["DB_NAME"],
                host=os.getenv("DB_HOST", "localhost"),
                port=os.getenv("DB_PORT", "5432"),
                min_size=5,
                max_size=30,
            )
            print("✅ Пул з'єднань з БД ініціалізовано.")
        except KeyError as e:
            print(f"❌ Відсутня змінна оточення {e}")
            raise
        except Exception as e:
            print(f"❌ Помилка підключення до БД: {e}")
            raise

    @classmethod
    @asynccontextmanager
    async def get_connection(cls):
        if cls._pool is None:
            await cls.initialize()
        assert cls._pool is not None
        async with cls._pool.acquire() as conn:
            yield conn

    @classmethod
    async def close_all(cls) -> None:
        if cls._pool is not None:
            pool, cls._pool = cls._pool, None
            await pool.close()
            print("🛑 Пул з'єднань закрито.")
