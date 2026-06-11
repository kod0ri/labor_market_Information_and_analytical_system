import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from src.db.database import AsyncDatabasePool

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health")
async def health_check() -> JSONResponse:
    try:
        async with AsyncDatabasePool.get_connection() as conn:
            await conn.fetchval("SELECT 1")
        return JSONResponse({"status": "ok", "database": "connected"})
    except Exception:
        # Деталі — лише в лог, назовні не зливаємо (info disclosure)
        logger.exception("Health check: помилка підключення до БД")
        return JSONResponse(
            status_code=503,
            content={"status": "error", "database": "unavailable"},
        )
