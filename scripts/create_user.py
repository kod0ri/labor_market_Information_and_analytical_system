#!/usr/bin/env python3
"""
Заведення / оновлення адмін-акаунта з командного рядка.

Усі акаунти системи — адміністратори (повний доступ до панелі, статистики,
метрик). Публічної реєстрації немає — це єдиний штатний спосіб додати акаунт.
Пароль зберігається лише як хеш (pbkdf2_sha256).

Приклади:
    # інтерактивно (пароль введеться приховано):
    python -m scripts.create_user --username bob

    # одразу з паролем:
    python -m scripts.create_user --username bob --password 's3cret'

    # оновити пароль наявного акаунта:
    python -m scripts.create_user --username bob --password 'new' --update

У Docker:
    docker compose exec api python -m scripts.create_user --username bob
"""

import argparse
import asyncio
import getpass
import sys

from src.auth.repository import UserRepository
from src.auth.security import hash_password
from src.db.database import AsyncDatabasePool


async def _run(username: str, password: str, update: bool) -> int:
    await AsyncDatabasePool.initialize()
    try:
        async with AsyncDatabasePool.get_connection() as conn:
            exists = await UserRepository.exists(conn, username)
            if exists and not update:
                print(f"❌ Акаунт '{username}' вже існує. Додайте --update, щоб змінити пароль.")
                return 1

            pwd_hash = hash_password(password)
            if exists:
                await conn.execute(
                    "UPDATE auth.users SET password_hash = $2 WHERE lower(username) = lower($1)",
                    username,
                    pwd_hash,
                )
                print(f"✅ Оновлено пароль акаунта '{username}'.")
            else:
                await UserRepository.create(conn, username, pwd_hash)
                print(f"✅ Створено адмін-акаунт '{username}'.")
        return 0
    finally:
        await AsyncDatabasePool.close_all()


def main() -> None:
    parser = argparse.ArgumentParser(description="Створити/оновити адмін-акаунт.")
    parser.add_argument("--username", required=True, help="Логін")
    parser.add_argument("--password", help="Пароль (якщо не вказано — спитає інтерактивно)")
    parser.add_argument(
        "--update", action="store_true", help="Оновити пароль наявного акаунта"
    )
    args = parser.parse_args()

    password = args.password
    if not password:
        password = getpass.getpass("Пароль: ")
        if password != getpass.getpass("Повторіть пароль: "):
            print("❌ Паролі не збігаються.")
            sys.exit(1)
    if len(password) < 8:
        print("❌ Пароль закороткий (мінімум 8 символів).")
        sys.exit(1)

    sys.exit(asyncio.run(_run(args.username, password, args.update)))


if __name__ == "__main__":
    main()
