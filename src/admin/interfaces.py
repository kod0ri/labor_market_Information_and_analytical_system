"""
Адміністративна підсистема — інтерфейси (Протоколи).

ISP (Interface Segregation Principle): три окремих протоколи замість одного
«жирного» інтерфейсу. Кожен клієнт залежить лише від тих методів,
які йому потрібні.

DIP (Dependency Inversion Principle): маршрути FastAPI та Facade залежать
від цих абстракцій, а не від конкретних класів.
"""

from typing import Protocol, Any, runtime_checkable


@runtime_checkable
class IStatsService(Protocol):
    """SRP: лише збір статистики системи."""

    async def get_system_stats(self, conn: Any) -> dict[str, Any]: ...


@runtime_checkable
class IFailureService(Protocol):
    """SRP: лише управління записами про помилки пайплайну."""

    async def get_failures(self, conn: Any, limit: int) -> list[dict[str, Any]]: ...
    async def resolve_failure(self, conn: Any, failure_id: int) -> bool: ...


@runtime_checkable
class IPipelineService(Protocol):
    """SRP: лише моніторинг стану пайплайну обробки даних."""

    async def get_pipeline_status(self, conn: Any) -> dict[str, Any]: ...
