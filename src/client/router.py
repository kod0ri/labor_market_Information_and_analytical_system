"""
Клієнтська підсистема — FastAPI маршрути.

Маршрути делегують всю роботу MarketDataFacade.
Вони не містять SQL, не знають про стратегії та репозиторії.
"""

from typing import Optional

from fastapi import APIRouter, Query

from src.db.database import AsyncDatabasePool
from src.client.facade import get_market_facade

router = APIRouter()


@router.get("/vacancies/search", summary="Пошук вакансій з фільтрами та пагінацією")
async def search_vacancies(
    page: int = Query(default=1, ge=1, description="Номер сторінки"),
    page_size: int = Query(default=20, ge=1, le=100, description="Розмір сторінки"),
    skill: Optional[str] = Query(default=None, description="Навичка, напр. Python"),
    location: Optional[str] = Query(default=None, description="Місто, напр. Київ"),
    min_salary_usd: Optional[int] = Query(default=None, description="Мінімальна зарплата USD"),
    experience_max: Optional[int] = Query(default=None, description="Максимальний досвід (роки)"),
    english_level: Optional[str] = Query(default=None, description="Рівень англійської, напр. Intermediate"),
    source: Optional[str] = Query(default=None, description="Джерело, напр. work.ua"),
) -> dict:
    """
    Пошук вакансій з підтримкою фільтрів за навичками, локацією,
    зарплатою, досвідом, рівнем англійської та джерелом.
    Використовує Strategy + Factory + Repository + Facade.
    """
    facade = get_market_facade()
    async with AsyncDatabasePool.get_connection() as conn:
        return await facade.search_vacancies(
            conn,
            min_salary_usd=min_salary_usd,
            experience_max=experience_max,
            location=location,
            skill=skill,
            english_level=english_level,
            source=source,
            page=page,
            page_size=page_size,
        )


@router.get("/resumes/search", summary="Пошук резюме з фільтрами та пагінацією")
async def search_resumes(
    page: int = Query(default=1, ge=1, description="Номер сторінки"),
    page_size: int = Query(default=20, ge=1, le=100, description="Розмір сторінки"),
    skill: Optional[str] = Query(default=None, description="Навичка, напр. Python"),
    location: Optional[str] = Query(default=None, description="Місто, напр. Київ"),
    min_salary_usd: Optional[int] = Query(default=None, description="Мінімальна зарплата USD"),
    experience_min: Optional[int] = Query(default=None, description="Мінімальний досвід (роки)"),
    english_level: Optional[str] = Query(default=None, description="Рівень англійської, напр. Upper-Intermediate"),
    source: Optional[str] = Query(default=None, description="Джерело, напр. work.ua"),
) -> dict:
    """
    Пошук резюме з підтримкою фільтрів.
    Використовує Strategy + Factory + Repository + Facade.
    """
    facade = get_market_facade()
    async with AsyncDatabasePool.get_connection() as conn:
        return await facade.search_resumes(
            conn,
            min_salary_usd=min_salary_usd,
            experience_min=experience_min,
            location=location,
            skill=skill,
            english_level=english_level,
            source=source,
            page=page,
            page_size=page_size,
        )
