"""
Клієнтська підсистема — Factory Method (Фабричний метод).

Factory Method (GoF Creational): делегує логіку створення об'єктів
фабричному класу. Маршрути FastAPI і Facade не знають, які конкретні
стратегії існують — вони лише викликають фабрику з параметрами запиту.

Переваги:
- додавання нової стратегії потребує змін лише тут (OCP)
- маршрути не залежать від конкретних класів стратегій (DIP)
"""

from typing import Any

from src.client.filters import (
    IFilterStrategy,
    SalaryFilterStrategy,
    ExperienceFilterStrategy,
    LocationFilterStrategy,
    SkillFilterStrategy,
    EnglishLevelFilterStrategy,
    SourceFilterStrategy,
    CompositeFilterStrategy,
)


class FilterStrategyFactory:
    """
    Фабрика стратегій фільтрації.

    create_vacancy_filters / create_resume_filters — два варіанти
    Фабричного методу, адаптованих під різні endpoint-и.
    """

    @staticmethod
    def create_vacancy_filters(
        min_salary_usd: int | None = None,
        experience_max: int | None = None,
        location: str | None = None,
        skill: str | None = None,
        english_level: str | None = None,
        source: str | None = None,
    ) -> CompositeFilterStrategy:
        strategies: list[IFilterStrategy] = []

        if min_salary_usd is not None:
            strategies.append(SalaryFilterStrategy(min_salary_usd=min_salary_usd))
        if experience_max is not None:
            strategies.append(ExperienceFilterStrategy(max_years=experience_max))
        if location:
            strategies.append(LocationFilterStrategy(city=location))
        if skill:
            strategies.append(SkillFilterStrategy(skill_name=skill))
        if english_level:
            strategies.append(EnglishLevelFilterStrategy(level=english_level))
        if source:
            strategies.append(SourceFilterStrategy(source=source))

        return CompositeFilterStrategy(strategies)

    @staticmethod
    def create_resume_filters(
        min_salary_usd: int | None = None,
        experience_min: int | None = None,
        location: str | None = None,
        skill: str | None = None,
        english_level: str | None = None,
        source: str | None = None,
    ) -> CompositeFilterStrategy:
        strategies: list[IFilterStrategy] = []

        if min_salary_usd is not None:
            strategies.append(SalaryFilterStrategy(min_salary_usd=min_salary_usd))
        if experience_min is not None:
            # Той самий клас ExperienceFilterStrategy, що й для вакансій (де
            # max_years = "не більше N років"), тут навмисно переюзаний з
            # протилежною семантикою - repository.py трактує поле filters
            # по-різному залежно від типу запиту (build_vacancy_query vs
            # build_resume_query), тож сама стратегія лишається однією й тією ж.
            strategies.append(ExperienceFilterStrategy(max_years=experience_min))
        if location:
            strategies.append(LocationFilterStrategy(city=location))
        if skill:
            strategies.append(SkillFilterStrategy(skill_name=skill))
        if english_level:
            strategies.append(EnglishLevelFilterStrategy(level=english_level))
        if source:
            strategies.append(SourceFilterStrategy(source=source))

        return CompositeFilterStrategy(strategies)
