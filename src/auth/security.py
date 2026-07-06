"""
Безпека автентифікації: хешування паролів та JWT-токени.

Хешування — стандартна бібліотека (hashlib.pbkdf2_hmac), без зовнішніх
залежностей і compiled-розширень. Формат збереженого хеша самодостатній:

    pbkdf2_sha256$<iterations>$<base64 salt>$<base64 hash>

Звірка пароля — constant-time (hmac.compare_digest), щоб не зливати
інформацію через час відповіді.

JWT_SECRET ОБОВ'ЯЗКОВИЙ — застосунок не стартує з відомим дефолтом.
"""

import base64
import hashlib
import hmac
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# ── Конфігурація ──────────────────────────────────────────────────────────────

ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24

# Дефолти, які раніше були захардкоджені — тепер вважаються небезпечними.
_FORBIDDEN_SECRETS = {
    "labor-market-secret-key-change-in-prod",
    "REPLACE_WITH_openssl_rand_hex_32",
    "changeme",
    "",
}

# pbkdf2: 600k ітерацій sha256 — рекомендація OWASP (2023).
_PBKDF2_ALGO = "pbkdf2_sha256"
_PBKDF2_ITERATIONS = 600_000


def get_secret_key() -> str:
    """
    Повертає JWT-секрет або кидає зрозумілу помилку, якщо він не заданий
    чи лишився дефолтним. Викликається на старті застосунку (fail fast).
    """
    secret = os.getenv("JWT_SECRET", "")
    if secret.strip() in _FORBIDDEN_SECRETS:
        raise RuntimeError(
            "JWT_SECRET не задано або використовує небезпечний дефолт. "
            "Згенеруйте секрет: `openssl rand -hex 32` і додайте у .env."
        )
    if len(secret) < 16:
        raise RuntimeError("JWT_SECRET занадто короткий (мінімум 16 символів).")
    return secret


# ── Хешування паролів ─────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return "{}${}${}${}".format(
        _PBKDF2_ALGO,
        _PBKDF2_ITERATIONS,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(dk).decode("ascii"),
    )


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, b64_salt, b64_hash = stored.split("$")
        if algo != _PBKDF2_ALGO:
            return False
        salt = base64.b64decode(b64_salt)
        expected = base64.b64decode(b64_hash)
        candidate = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, int(iterations)
        )
        return hmac.compare_digest(candidate, expected)
    except (ValueError, TypeError):
        return False


# ── JWT ───────────────────────────────────────────────────────────────────────

def create_token(*, user_id: int, username: str) -> str:
    payload = {
        "sub": username,
        "uid": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, get_secret_key(), algorithm=ALGORITHM)


@dataclass
class CurrentUser:
    id: int | None
    username: str


_bearer = HTTPBearer()


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, get_secret_key(), algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Термін дії токена вичерпано")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Недійсний токен")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> CurrentUser:
    """
    Залежність FastAPI: декодує токен, звіряє, що акаунт ще існує й активний,
    оновлює last_seen_at (для «онлайн») і повертає поточного користувача.
    Усі акаунти — адміністратори, тож окремої перевірки ролі немає. Старі
    токени без uid доповнюються з БД.

    is_active перевіряється на КОЖНОМУ запиті: деактивація чи видалення акаунта
    відкликає його токен одразу, а не по закінченні терміну дії.
    """
    # Локальний імпорт розриває цикл security ↔ repository.
    from src.auth.repository import UserRepository
    from src.db.database import AsyncDatabasePool

    payload = decode_token(credentials.credentials)
    username = payload.get("sub")
    if not username:
        raise HTTPException(status_code=401, detail="Недійсний токен")

    user_id = payload.get("uid")

    async with AsyncDatabasePool.get_connection() as conn:
        if user_id is None:
            row = await UserRepository.get_by_username(conn, username)
            if row is None or not row["is_active"]:
                raise HTTPException(status_code=401, detail="Користувача не знайдено")
            user_id = row["id"]
            await UserRepository.touch_last_seen(conn, int(user_id))
        else:
            is_active = await UserRepository.touch_and_get_active(conn, int(user_id))
            if is_active is None or not is_active:
                raise HTTPException(status_code=401, detail="Акаунт неактивний або видалений")

    return CurrentUser(id=int(user_id), username=username)
