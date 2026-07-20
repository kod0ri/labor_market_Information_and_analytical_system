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
    if secret.strip() in _FORBIDDEN_SECRETS:      # порожньо або відомий приклад-заглушка з .env.example
        raise RuntimeError(
            "JWT_SECRET не задано або використовує небезпечний дефолт. "
            "Згенеруйте секрет: `openssl rand -hex 32` і додайте у .env."
        )
    if len(secret) < 16:                            # занадто короткий - легко підібрати
        raise RuntimeError("JWT_SECRET занадто короткий (мінімум 16 символів).")
    return secret


# ── Хешування паролів ─────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Хешує пароль PBKDF2-HMAC-SHA256 зі свіжою випадковою сіллю на кожен
    виклик (тому той самий пароль двічі дає РІЗНИЙ рядок хеша)."""
    salt = os.urandom(16)     # 16 випадкових байт - унікальні для кожного виклику, унеможливлює rainbow-table атаки
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)   # derived key (сам хеш)
    return "{}${}${}${}".format(
        _PBKDF2_ALGO,                                    # назва алгоритму - для сумісності при майбутній зміні схеми
        _PBKDF2_ITERATIONS,                               # зберігаємо к-сть ітерацій РАЗОМ із хешем
        base64.b64encode(salt).decode("ascii"),           # сіль у текстовому вигляді для зберігання в одному рядку
        base64.b64encode(dk).decode("ascii"),             # сам хеш так само в base64
    )


def verify_password(password: str, stored: str) -> bool:
    """Перевіряє пароль проти збереженого хеша (формат з docstring модуля).

    iterations читається З САМОГО хеша (не з константи _PBKDF2_ITERATIONS) -
    дозволяє в майбутньому підняти кількість ітерацій для нових паролів,
    лишаючи старі хеші перевірюваними зі "своєю" кількістю ітерацій.
    """
    try:
        algo, iterations, b64_salt, b64_hash = stored.split("$")   # розбираємо формат, зібраний у hash_password()
        if algo != _PBKDF2_ALGO:            # раптом інший алгоритм (майбутня міграція схеми) - не наш формат
            return False
        salt = base64.b64decode(b64_salt)         # та сама сіль, що використовувалась при хешуванні
        expected = base64.b64decode(b64_hash)     # очікуваний (збережений) хеш
        candidate = hashlib.pbkdf2_hmac(          # рахуємо хеш ВВЕДЕНОГО пароля з ТІЄЮ Ж сіллю й тими ж ітераціями
            "sha256", password.encode("utf-8"), salt, int(iterations)
        )
        # compare_digest замість `==` - захист від timing-атаки, яка могла б
        # вгадати хеш по тому, скільки байтів співпало до першої розбіжності.
        return hmac.compare_digest(candidate, expected)
    except (ValueError, TypeError):
        # Пошкоджений/чужого формату рядок стored - трактуємо як "не підійшло",
        # а не як 500-ту помилку.
        return False


# ── JWT ───────────────────────────────────────────────────────────────────────

def create_token(*, user_id: int, username: str) -> str:
    """Видає JWT на TOKEN_EXPIRE_HOURS (24) годин. `uid` у payload дозволяє
    get_current_user перевіряти акаунт по id (стабільний), не лише по
    username (може змінитись/видалитись) - логін лишається просто зручним
    полем sub для сумісності зі стандартним JWT claim."""
    payload = {
        "sub": username,      # стандартний JWT claim "subject" - людський логін
        "uid": user_id,       # наш власний claim - стабільний id для перевірки в get_current_user
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS),   # час протермінування (UTC!)
    }
    return jwt.encode(payload, get_secret_key(), algorithm=ALGORITHM)   # підписуємо HS256-секретом з .env


@dataclass
class CurrentUser:
    id: int | None
    username: str


_bearer = HTTPBearer()


def decode_token(token: str) -> dict:
    """Декодує й перевіряє підпис/термін дії JWT; кидає HTTPException(401)
    одразу замість пропускання винятку далі - виклики нижче можуть покладатись,
    що успішне повернення = валідний токен."""
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

    payload = decode_token(credentials.credentials)   # кине HTTPException(401) сам, якщо токен невалідний/протермінований
    username = payload.get("sub")
    if not username:                # теоретично неможливо для токена, виданого create_token, але захищаємось
        raise HTTPException(status_code=401, detail="Недійсний токен")

    user_id = payload.get("uid")    # None лише для СТАРИХ токенів, виданих до появи цього claim

    async with AsyncDatabasePool.get_connection() as conn:
        if user_id is None:                                          # старий токен без uid - резолвимо по логіну
            row = await UserRepository.get_by_username(conn, username)
            if row is None or not row["is_active"]:
                raise HTTPException(status_code=401, detail="Користувача не знайдено")
            user_id = row["id"]
            await UserRepository.touch_last_seen(conn, int(user_id))
        else:                                                          # звичайний шлях - є uid, перевіряємо одним запитом
            is_active = await UserRepository.touch_and_get_active(conn, int(user_id))
            if is_active is None or not is_active:      # None - акаунт видалений; False - деактивований
                raise HTTPException(status_code=401, detail="Акаунт неактивний або видалений")

    return CurrentUser(id=int(user_id), username=username)
