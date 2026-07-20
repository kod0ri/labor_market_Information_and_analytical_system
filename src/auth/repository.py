"""
Репозиторій користувачів — увесь доступ до auth.users в одному місці.

Repository (GoF/PoEAA): ізолює SQL від бізнес-логіки роутів і сервісів.
Усі методи — статичні: стану немає, з'єднання передається ззовні (DIP).

«Онлайн» визначається порогом ONLINE_WINDOW: користувач вважається в мережі,
якщо його last_seen_at оновлювався протягом останніх кількох хвилин.
Поле оновлюється у get_current_user на кожному автентифікованому запиті.
"""

from typing import Any

# Користувач «онлайн», якщо активність була в межах цього вікна (хвилин).
ONLINE_WINDOW_MINUTES = 5
# Не оновлювати last_seen_at частіше, ніж раз на стільки секунд (throttle).
_TOUCH_THROTTLE_SECONDS = 60


class UserRepository:
    @staticmethod
    async def get_by_username(conn: Any, username: str) -> Any | None:
        """lower(username) - логін нечутливий до регістру при пошуку, хоча
        зберігається у введеному вигляді (унікальність теж по lower(), див.
        idx_users_username_lower у bootstrap.py)."""
        return await conn.fetchrow(
            """
            SELECT id, username, password_hash, is_active, created_at, last_seen_at
            FROM auth.users
            WHERE lower(username) = lower($1)
            """,
            username,
        )

    @staticmethod
    async def exists(conn: Any, username: str) -> bool:
        return await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM auth.users WHERE lower(username) = lower($1))",
            username,
        )

    @staticmethod
    async def create(conn: Any, username: str, password_hash: str) -> Any:
        return await conn.fetchrow(
            """
            INSERT INTO auth.users (username, password_hash)
            VALUES ($1, $2)
            RETURNING id, username, created_at
            """,
            username,
            password_hash,
        )

    @staticmethod
    async def touch_last_seen(conn: Any, user_id: int) -> None:
        """Оновлює мітку активності (з throttle, щоб не писати на кожен запит)."""
        await conn.execute(
            f"""
            UPDATE auth.users
            SET last_seen_at = now()
            WHERE id = $1
              AND (last_seen_at IS NULL
                   OR last_seen_at < now() - interval '{_TOUCH_THROTTLE_SECONDS} seconds')
            """,   # WHERE-умова throttle: якщо оновлювали менше хвилини тому - UPDATE нічого не змінить (0 рядків)
            user_id,
        )

    @staticmethod
    async def touch_and_get_active(conn: Any, user_id: int) -> bool | None:
        """
        За один round-trip: перевіряє існування/активність користувача і
        throttle-оновлює last_seen_at. Повертає is_active, або None якщо
        користувача більше немає (видалений). Використовується на кожному
        автентифікованому запиті, щоб токен деактивованого акаунта переставав
        працювати одразу, а не аж по закінченні терміну дії.
        """
        return await conn.fetchval(
            f"""
            UPDATE auth.users
            SET last_seen_at = CASE
                    WHEN last_seen_at IS NULL
                         OR last_seen_at < now() - interval '{_TOUCH_THROTTLE_SECONDS} seconds'
                    THEN now()
                    ELSE last_seen_at
                END
            WHERE id = $1
            RETURNING is_active
            """,
            user_id,
        )

    @staticmethod
    async def list_all(conn: Any) -> list[dict[str, Any]]:
        rows = await conn.fetch(
            f"""
            SELECT id, username, is_active, created_at, last_seen_at,
                   (last_seen_at IS NOT NULL
                    AND last_seen_at > now() - interval '{ONLINE_WINDOW_MINUTES} minutes') AS is_online
            FROM auth.users
            ORDER BY is_online DESC, last_seen_at DESC NULLS LAST, created_at ASC
            """
        )
        return [
            {
                "id": r["id"],
                "username": r["username"],
                "is_active": r["is_active"],
                "is_online": r["is_online"],       # обчислено просто у SQL (BETWEEN/AND-вираз вище), не в Python
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,     # datetime → ISO-рядок для JSON
                "last_seen_at": r["last_seen_at"].isoformat() if r["last_seen_at"] else None,
            }
            for r in rows
        ]

    @staticmethod
    async def counts(conn: Any) -> dict[str, int]:
        row = await conn.fetchrow(
            f"""
            SELECT
                COUNT(*)                                                   AS total,
                COUNT(*) FILTER (WHERE is_active)                          AS active,
                COUNT(*) FILTER (
                    WHERE last_seen_at IS NOT NULL
                      AND last_seen_at > now() - interval '{ONLINE_WINDOW_MINUTES} minutes'
                )                                                          AS online,
                COUNT(*) FILTER (WHERE created_at > now() - interval '7 days') AS new_7d
            FROM auth.users
            """
        )
        return {
            "total": row["total"],
            "active": row["active"],
            "online": row["online"],
            "new_7d": row["new_7d"],
        }
