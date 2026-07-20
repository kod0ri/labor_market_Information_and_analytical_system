"""
Публічний ендпоінт анонімного трекінгу відвідувачів.

Фронтенд шле beacon при заході/переході сторінками. Без автентифікації —
рахуємо всіх відвідувачів, не лише адмінів. Зберігаємо тільки visitor_id
(випадковий ідентифікатор браузера) і шлях; query-рядок і IP не зберігаються.
"""

import os
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, field_validator

from src.api.ratelimit import rate_limiter
from src.db.database import AsyncDatabasePool
from src.tracking.repository import VisitRepository

router = APIRouter()

# Легітимний клієнт шле beacon при заході/переході + раз на хвилину — кілька
# запитів за хвилину. 30/хв на IP лишає величезний запас і відсікає спам.
_TRACK_RATE_LIMIT = int(os.getenv("TRACK_RATE_LIMIT", "30"))


class TrackRequest(BaseModel):
    visitor_id: UUID
    path: str | None = None

    @field_validator("path")
    @classmethod
    def _clean_path(cls, v: str | None) -> str | None:
        if not v:                          # шлях не передано взагалі
            return None
        v = v.split("?")[0][:200]  # відкидаємо query, обмежуємо довжину
        return v if v.startswith("/") else None   # приймаємо лише валідні відносні шляхи (захист від сміття)


@router.post(
    "/track",
    status_code=204,
    summary="Зафіксувати візит (анонімно)",
    dependencies=[Depends(rate_limiter(_TRACK_RATE_LIMIT, 60))],
)
async def track(body: TrackRequest) -> Response:
    async with AsyncDatabasePool.get_connection() as conn:
        await VisitRepository.record(conn, body.visitor_id, body.path)
    return Response(status_code=204)
