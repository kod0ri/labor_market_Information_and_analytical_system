"""
Клієнтська підсистема — Strategy (Стратегія).

Strategy (GoF Behavioral): визначає сімейство алгоритмів фільтрації,
інкапсулює кожен з них і робить їх взаємозамінними.
Клієнтський код (репозиторій) не знає, яка стратегія застосована —
він лише отримує готовий словник параметрів запиту.

CompositeFilterStrategy — реалізує патерн Composite (GoF Structural):
дозволяє об'єднувати кілька стратегій в одну, яку можна використовувати
так само, як і будь-яку іншу стратегію.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class IFilterStrategy(Protocol):
    """Інтерфейс стратегії фільтрації."""

    def apply(self, params: dict[str, Any]) -> dict[str, Any]: ...


@dataclass
class SalaryFilterStrategy:
    """Стратегія фільтрації за діапазоном зарплати (USD-еквівалент)."""

    min_salary_usd: int | None = None
    max_salary_usd: int | None = None

    def apply(self, params: dict[str, Any]) -> dict[str, Any]:
        result = dict(params)
        if self.min_salary_usd is not None:
            result["min_salary_usd"] = self.min_salary_usd
        if self.max_salary_usd is not None:
            result["max_salary_usd"] = self.max_salary_usd
        return result


@dataclass
class ExperienceFilterStrategy:
    """Стратегія фільтрації за максимальним досвідом (для вакансій)."""

    max_years: int | None = None

    def apply(self, params: dict[str, Any]) -> dict[str, Any]:
        result = dict(params)
        if self.max_years is not None:
            result["experience_max"] = self.max_years
        return result


@dataclass
class LocationFilterStrategy:
    """Стратегія фільтрації за назвою міста (ILIKE)."""

    city: str | None = None

    def apply(self, params: dict[str, Any]) -> dict[str, Any]:
        result = dict(params)
        if self.city and self.city.strip():
            result["location"] = self.city.strip()
        return result


@dataclass
class SkillFilterStrategy:
    """Стратегія фільтрації за наявністю навички (точний збіг, case-insensitive)."""

    skill_name: str | None = None

    def apply(self, params: dict[str, Any]) -> dict[str, Any]:
        result = dict(params)
        if self.skill_name and self.skill_name.strip():
            result["skill"] = self.skill_name.strip()
        return result


@dataclass
class EnglishLevelFilterStrategy:
    """Стратегія фільтрації за рівнем англійської мови."""

    level: str | None = None

    def apply(self, params: dict[str, Any]) -> dict[str, Any]:
        result = dict(params)
        if self.level and self.level.strip():
            result["english_level"] = self.level.strip()
        return result


class CompositeFilterStrategy:
    """
    Composite Strategy: об'єднує довільну кількість стратегій у одну.
    Кожна стратегія застосовується послідовно — результат передається
    наступній як вхідний словник.
    """

    def __init__(self, strategies: list[IFilterStrategy]) -> None:
        self._strategies = strategies

    def apply(self, params: dict[str, Any]) -> dict[str, Any]:
        result = dict(params)
        for strategy in self._strategies:
            result = strategy.apply(result)
        return result
