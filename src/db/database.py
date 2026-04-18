import os
from psycopg2.pool import ThreadedConnectionPool  # Прямий імпорт пулу (вирішує Ruff F401)
from contextlib import contextmanager
from dotenv import load_dotenv

load_dotenv()

class DatabasePool:
    # Явно вказуємо тип для Pylance
    _pool: ThreadedConnectionPool | None = None

    @classmethod
    def initialize(cls):
        """Ініціалізація пулу з'єднань при першому виклику."""
        if cls._pool is None:
            try:
                cls._pool = ThreadedConnectionPool(
                    minconn=1,
                    maxconn=10,
                    host=os.getenv("DB_HOST", "localhost"),
                    port=os.getenv("DB_PORT", "5432"),
                    database=os.getenv("DB_NAME", "postgres"),
                    user=os.getenv("DB_USER", "postgres"),
                    password=os.getenv("DB_PASSWORD", "postgres")
                )
                print("Database connection pool initialized.")
            except Exception as e:
                print(f"Error initializing database pool: {e}")
                raise

    @classmethod
    @contextmanager
    def get_connection(cls):
        if cls._pool is None:
            cls.initialize()
            
        # Заспокоюємо Pylance: гарантуємо, що _pool більше не None
        assert cls._pool is not None
        
        conn = cls._pool.getconn()
        try:
            yield conn
        finally:
            cls._pool.putconn(conn)

    @classmethod
    def close_all(cls):
        if cls._pool is not None:
            cls._pool.closeall()
            print("Database connection pool closed.")