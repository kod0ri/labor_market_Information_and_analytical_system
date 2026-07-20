"""
Автентифікація — FastAPI маршрути.

Вхід перевіряється проти таблиці auth.users (пароль — лише хеш, звірка
constant-time). Захардкоджений env-акаунт більше не порівнюється у відкритому
вигляді: він засівається у БД як адмін на старті (src/auth/bootstrap.py).

Публічної реєстрації немає — користувачів заводить адмін через CLI
(scripts/create_user.py). Тому тут лише login та me.
"""

import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.ratelimit import rate_limiter
from src.auth.repository import UserRepository
from src.auth.security import (
    CurrentUser,
    create_token,
    get_current_user,
    verify_password,
)
from src.db.database import AsyncDatabasePool

router = APIRouter()

# Захист від перебору паролів на відкритому домені. 10 спроб/хв на IP —
# з запасом для людини, але неприйнятно мало для брутфорсу.
_LOGIN_RATE_LIMIT = int(os.getenv("LOGIN_RATE_LIMIT", "10"))


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limiter(_LOGIN_RATE_LIMIT, 60))],
)
async def login(body: LoginRequest):
    """Перевіряє логін/пароль і видає JWT. rate_limiter на роуті обмежує
    брутфорс по IP; фіктивний хеш нижче обмежує ще й enumeration за часом."""
    async with AsyncDatabasePool.get_connection() as conn:
        user = await UserRepository.get_by_username(conn, body.username)   # None, якщо такого логіна нема

    # Звіряємо хеш навіть за відсутності користувача — щоб час відповіді
    # не залежав від того, чи існує логін (захист від user enumeration).
    stored_hash = user["password_hash"] if user else (
        "pbkdf2_sha256$600000$AAAAAAAAAAAAAAAAAAAAAA==$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="   # фіктивний валідний за форматом хеш
    )
    password_ok = verify_password(body.password, stored_hash)   # завжди виконує повний PBKDF2-цикл, навіть для фіктивного хеша

    if user is None or not user["is_active"] or not password_ok:   # об'єднана перевірка - однакова помилка для всіх трьох випадків
        raise HTTPException(status_code=401, detail="Невірний логін або пароль")

    token = create_token(user_id=user["id"], username=user["username"])
    return TokenResponse(access_token=token, username=user["username"])


@router.get("/me")
async def me(user: CurrentUser = Depends(get_current_user)):
    return {"id": user.id, "username": user.username}
