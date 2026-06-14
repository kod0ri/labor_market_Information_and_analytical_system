"""
Bootstrap автентифікації — ідемпотентна підготовка на старті застосунку.

1. ensure_auth_schema — створює схему auth + таблицю users, якщо їх ще нема.
   Потрібно для вже наповнених баз, де init_db/*.sql не виконуються повторно.
2. seed_admin — заводить початкового адміністратора з ADMIN_USERNAME /
   ADMIN_PASSWORD (якщо вони задані й такого користувача ще немає).

Усі акаунти системи — адміністратори з повним доступом; ролей немає.
Реєстрації через UI немає: акаунти заводять адмінською CLI
(scripts/create_user.py) або сидом з env.
"""

import os

from src.auth.repository import UserRepository
from src.auth.security import hash_password
from src.db.database import AsyncDatabasePool

_DDL = """
CREATE SCHEMA IF NOT EXISTS auth;

CREATE TABLE IF NOT EXISTS auth.users (
    id            INTEGER     GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username      VARCHAR(64) NOT NULL,
    password_hash TEXT        NOT NULL,
    is_active     BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at  TIMESTAMPTZ
);

-- Прибираємо колонку role з баз, де вона лишилась від попередньої версії:
-- система має лише адмінські акаунти, тож роль не потрібна.
ALTER TABLE auth.users DROP COLUMN IF EXISTS role;

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username_lower
    ON auth.users (lower(username));

CREATE INDEX IF NOT EXISTS idx_users_last_seen
    ON auth.users (last_seen_at DESC);
"""


async def ensure_auth_schema() -> None:
    async with AsyncDatabasePool.get_connection() as conn:
        await conn.execute(_DDL)


async def seed_admin() -> None:
    """Створює адміна з env, якщо заданий і ще не існує. Без перезапису пароля."""
    username = os.getenv("ADMIN_USERNAME", "").strip()
    password = os.getenv("ADMIN_PASSWORD", "")
    if not username or not password:
        print("ℹ️  ADMIN_USERNAME/ADMIN_PASSWORD не задані — адміна не засіяно.")
        return

    async with AsyncDatabasePool.get_connection() as conn:
        if await UserRepository.exists(conn, username):
            return
        await UserRepository.create(conn, username, hash_password(password))
        print(f"✅ Засіяно адміністратора '{username}'.")


async def init_auth() -> None:
    await ensure_auth_schema()
    await seed_admin()
