"""
Клієнтська підсистема — Facade (Фасад).

Facade (GoF Structural): надає простий уніфікований інтерфейс до складної
підсистеми пошуку даних, яка включає:
  - FilterStrategyFactory (Фабричний метод)
  - CompositeFilterStrategy (Composite Strategy)
  - VacancyRepository / ResumeRepository (Repository)

Маршрути FastAPI взаємодіють лише з MarketDataFacade і не знають про
внутрішні деталі побудови запитів, стратегій та репозиторіїв.

Singleton (GoF Creational): єдиний глобальний екземпляр через
get_market_facade().
"""

from typing import Any

from src.client.factory import FilterStrategyFactory
from src.client.repository import (
    IVacancyRepository,
    IResumeRepository,
    VacancyRepository,
    ResumeRepository,
)


class MarketDataFacade:
    def __init__(
        self,
        vacancy_repo: IVacancyRepository | None = None,
        resume_repo: IResumeRepository | None = None,
    ) -> None:
        self._vacancies: IVacancyRepository = vacancy_repo or VacancyRepository()
        self._resumes: IResumeRepository = resume_repo or ResumeRepository()

    async def search_vacancies(
        self,
        conn: Any,
        *,
        min_salary_usd: int | None = None,
        experience_max: int | None = None,
        location: str | None = None,
        skill: str | None = None,
        english_level: str | None = None,
        source: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        strategy = FilterStrategyFactory.create_vacancy_filters(
            min_salary_usd=min_salary_usd,
            experience_max=experience_max,
            location=location,
            skill=skill,
            english_level=english_level,
            source=source,
        )
        filters = strategy.apply({})
        offset = (page - 1) * page_size

        items = await self._vacancies.find_many(conn, filters, page_size, offset)
        total = await self._vacancies.count(conn, filters)

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": max(1, (total + page_size - 1) // page_size),
        }

    async def search_resumes(
        self,
        conn: Any,
        *,
        min_salary_usd: int | None = None,
        experience_min: int | None = None,
        location: str | None = None,
        skill: str | None = None,
        english_level: str | None = None,
        source: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        strategy = FilterStrategyFactory.create_resume_filters(
            min_salary_usd=min_salary_usd,
            experience_min=experience_min,
            location=location,
            skill=skill,
            english_level=english_level,
            source=source,
        )
        filters = strategy.apply({})
        offset = (page - 1) * page_size

        items = await self._resumes.find_many(conn, filters, page_size, offset)
        total = await self._resumes.count(conn, filters)

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": max(1, (total + page_size - 1) // page_size),
        }


_market_facade = MarketDataFacade()


def get_market_facade() -> MarketDataFacade:
    """Повертає єдиний екземпляр MarketDataFacade для всього застосунку."""
    return _market_facade
