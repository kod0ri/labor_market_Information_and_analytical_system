from fastapi import APIRouter
from src.db.database import AsyncDatabasePool

router = APIRouter()


@router.get("/health")
async def health_check() -> dict:
    try:
        async with AsyncDatabasePool.get_connection() as conn:
            await conn.fetchval("SELECT 1")
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return {"status": "error", "database": str(e)}
