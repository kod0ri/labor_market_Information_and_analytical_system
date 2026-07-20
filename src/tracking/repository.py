"""
Репозиторій анонімного трекінгу відвідувачів.

Рахуємо ВСІХ відвідувачів сайту (включно з незареєстрованими) за випадковим
visitor_id, який браузер зберігає в localStorage. Жодного IP чи PII — лише
ідентифікатор браузера та шлях сторінки.

Метрики:
  online        — унікальних відвідувачів за останні ONLINE_WINDOW_MINUTES хв
  last_24h      — унікальних за 24 години
  last_7d       — унікальних за 7 днів
  avg_online_24h — середня кількість одночасних відвідувачів у 5-хв вікні
                   (за активними вікнами останньої доби)
  peak_online_24h — максимум одночасних у 5-хв вікні за добу
"""

from typing import Any
from uuid import UUID

ONLINE_WINDOW_MINUTES = 5
RETENTION_DAYS = 30
_BUCKET_SECONDS = 300  # 5 хв — крок для середнього/пікового онлайну


class VisitRepository:
    @staticmethod
    async def record(conn: Any, visitor_id: UUID, path: str | None) -> None:
        await conn.execute(
            "INSERT INTO analytics.visits (visitor_id, path) VALUES ($1, $2)",
            visitor_id,
            path,
        )

    @staticmethod
    async def metrics(conn: Any) -> dict[str, Any]:
        # Прибираємо застарілі записи (lazy-cleanup на читанні метрик адміном).
        await conn.execute(   # видаляється лише при запиті метрик адміном - немає окремого cron/задачі для цього
            f"DELETE FROM analytics.visits WHERE seen_at < now() - interval '{RETENTION_DAYS} days'"
        )

        online = await conn.fetchval(   # унікальних visitor_id за останні ONLINE_WINDOW_MINUTES хвилин
            f"""
            SELECT COUNT(DISTINCT visitor_id) FROM analytics.visits
            WHERE seen_at > now() - interval '{ONLINE_WINDOW_MINUTES} minutes'
            """
        )
        last_24h = await conn.fetchval(
            "SELECT COUNT(DISTINCT visitor_id) FROM analytics.visits "
            "WHERE seen_at > now() - interval '24 hours'"
        )
        last_7d = await conn.fetchval(
            "SELECT COUNT(DISTINCT visitor_id) FROM analytics.visits "
            "WHERE seen_at > now() - interval '7 days'"
        )
        agg = await conn.fetchrow(
            f"""
            WITH buckets AS (
                SELECT floor(extract(epoch FROM seen_at) / {_BUCKET_SECONDS}) AS bucket,   -- номер 5-хв інтервалу
                       COUNT(DISTINCT visitor_id) AS online                                  -- унікальних у цьому інтервалі
                FROM analytics.visits
                WHERE seen_at > now() - interval '24 hours'
                GROUP BY bucket
            )
            SELECT COALESCE(ROUND(AVG(online), 1), 0) AS avg_online,   -- середнє по всіх 5-хв інтервалах доби
                   COALESCE(MAX(online), 0)           AS peak_online   -- максимальний інтервал (пікове навантаження)
            FROM buckets
            """
        )
        return {
            "online": online or 0,
            "last_24h": last_24h or 0,
            "last_7d": last_7d or 0,
            "avg_online_24h": float(agg["avg_online"]),
            "peak_online_24h": agg["peak_online"],
        }
