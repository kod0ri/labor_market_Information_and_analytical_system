"""
Адміністративна підсистема — FastAPI маршрути.

DIP: маршрути залежать від AdminFacade (абстракція), а не від конкретних
сервісів — зміна реалізації сервісу не потребує зміни маршрутів.
"""

from fastapi import APIRouter, Depends, HTTPException, Query

from src.auth.security import get_current_user
from src.db.database import AsyncDatabasePool
from src.admin.facade import get_admin_facade

# Усі акаунти — адміністратори; достатньо бути автентифікованим.
router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/stats", summary="Загальна статистика системи")
async def get_system_stats() -> dict:
    """
    Повертає агреговану статистику: кількість вакансій, резюме,
    навичок, компаній, а також розмір черги необроблених записів.
    """
    facade = get_admin_facade()
    async with AsyncDatabasePool.get_connection() as conn:
        return await facade.get_stats(conn)


@router.get("/system", summary="Метрики сервера та користувачів")
async def get_system_metrics() -> dict:
    """
    Зведення для адміністратора: кількість акаунтів та хто онлайн,
    зайнятість диска, память, навантаження, розмір БД і uptime застосунку.
    """
    facade = get_admin_facade()
    async with AsyncDatabasePool.get_connection() as conn:
        return await facade.get_system_metrics(conn)


@router.get("/pipeline/status", summary="Стан пайплайну обробки даних")
async def get_pipeline_status() -> dict:
    """
    Показує чергу необроблених записів, кількість помилок за типами
    та час останнього успішного запису у core-таблиці.
    """
    facade = get_admin_facade()
    async with AsyncDatabasePool.get_connection() as conn:
        return await facade.get_pipeline_status(conn)


@router.get("/failures", summary="Список нерозв'язаних помилок пайплайну")
async def list_failures(
    limit: int = Query(default=50, ge=1, le=200, description="Максимальна кількість записів"),
) -> list[dict]:
    """
    Повертає список записів, які не вдалось обробити під час NLP-пайплайну.
    Поле `error_type`: validation | rate_limit | unknown.
    """
    facade = get_admin_facade()
    async with AsyncDatabasePool.get_connection() as conn:
        return await facade.get_failures(conn, limit)


@router.patch(
    "/failures/{failure_id}/resolve",
    summary="Позначити помилку як вирішену",
)
async def resolve_failure(failure_id: int) -> dict:
    """
    Вручну позначає запис про помилку як is_resolved=true.
    Корисно після ручного виправлення або повторного запуску пайплайну.
    """
    facade = get_admin_facade()
    async with AsyncDatabasePool.get_connection() as conn:
        resolved = await facade.resolve_failure(conn, failure_id)
    if not resolved:
        raise HTTPException(
            status_code=404,
            detail=f"Помилка з id={failure_id} не знайдена або вже вирішена.",
        )
    return {"success": True, "failure_id": failure_id}
