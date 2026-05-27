"""
Адміністративна підсистема — Facade (Фасад).

Facade (GoF Structural): надає єдину спрощену точку входу до трьох
незалежних сервісів (Stats, Failure, Pipeline).
Приховує внутрішню складність підсистеми від FastAPI-маршрутів.

DIP: залежить від Protocol-інтерфейсів, а не від конкретних класів —
будь-який з сервісів можна замінити mock-реалізацією (напр. для тестів).
"""

from typing import Any

from src.admin.interfaces import IStatsService, IFailureService, IPipelineService
from src.admin.services import StatsService, FailureService, PipelineService


class AdminFacade:
    def __init__(
        self,
        stats: IStatsService | None = None,
        failures: IFailureService | None = None,
        pipeline: IPipelineService | None = None,
    ) -> None:
        # DIP: використовуємо переданий екземпляр або створюємо дефолтний
        self._stats: IStatsService = stats or StatsService()
        self._failures: IFailureService = failures or FailureService()
        self._pipeline: IPipelineService = pipeline or PipelineService()

    async def get_stats(self, conn: Any) -> dict[str, Any]:
        return await self._stats.get_system_stats(conn)

    async def get_failures(self, conn: Any, limit: int = 50) -> list[dict[str, Any]]:
        return await self._failures.get_failures(conn, limit)

    async def resolve_failure(self, conn: Any, failure_id: int) -> bool:
        return await self._failures.resolve_failure(conn, failure_id)

    async def get_pipeline_status(self, conn: Any) -> dict[str, Any]:
        return await self._pipeline.get_pipeline_status(conn)


# Singleton-екземпляр (Одинак / Singleton — GoF Creational)
_admin_facade = AdminFacade()


def get_admin_facade() -> AdminFacade:
    """Повертає єдиний екземпляр AdminFacade для всього застосунку."""
    return _admin_facade
