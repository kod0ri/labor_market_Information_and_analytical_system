"""
Спільний довідник категорій збору для скраперів (work.ua, robota.ua).

Система аналізує ВЕСЬ ринок праці, тому збір не обмежується IT-рубриками.
label — канонічна мітка категорії: вона пишеться у staging.search_category
і далі потрапляє в analytics.daily_market_snapshots.category, тож має бути
однаковою для всіх джерел.

Slug'и work.ua та id рубрик robota.ua звірені з живими сайтами 20.07.2026:
- https://www.work.ua/<workua_slug>/ — сторінка рубрики вакансій
  (резюме — той самий slug із заміною jobs- → resumes-);
- https://api.rabota.ua/dictionary/rubric — офіційний словник рубрик robota.ua.

SCRAPE_CATEGORIES="IT,Продажі" (мітки через кому) обмежує прогін підмножиною —
корисно для швидких тестових запусків.
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Category:
    label: str             # канонічна мітка → staging.search_category
    workua_slug: str       # рубрика вакансій work.ua (jobs-*)
    robota_rubric_id: str  # rubrics.id у GraphQL dracula.robota.ua

    @property
    def workua_resumes_slug(self) -> str:
        return self.workua_slug.replace("jobs-", "resumes-", 1)


CATEGORIES: tuple[Category, ...] = (
    Category("IT", "jobs-it", "1"),
    Category("Продажі", "jobs-sales", "17"),
    Category("Медицина", "jobs-healthcare", "9"),
    Category("Освіта та наука", "jobs-education-scientific", "10"),
    Category("Фінанси", "jobs-banking-finance", "18"),
    Category("Маркетинг", "jobs-marketing-advertising-pr", "24"),
    Category("Виробництво", "jobs-production-engineering", "32"),
    Category("Будівництво", "jobs-construction-architecture", "27"),
    Category("Торгівля", "jobs-retail", "16"),
    Category("Транспорт та логістика", "jobs-auto-transport", "5"),
    Category("Готелі та туризм", "jobs-hotel-restaurant-tourism", "8"),
    Category("Агро", "jobs-agriculture", "26"),
    Category("Охорона", "jobs-security", "4"),
    Category("Краса та спорт", "jobs-beauty-sports", "7"),
)


def active_categories() -> tuple[Category, ...]:
    """Категорії поточного прогону: всі, або підмножина зі SCRAPE_CATEGORIES."""
    raw = os.getenv("SCRAPE_CATEGORIES", "").strip()   # напр. "IT,Продажі" або порожньо
    if not raw:                                          # змінна не задана - працюємо по всьому ринку
        return CATEGORIES
    wanted = {part.strip().casefold() for part in raw.split(",") if part.strip()}  # набір міток у нижньому регістрі
    picked = tuple(c for c in CATEGORIES if c.label.casefold() in wanted)          # лишаємо тільки запитані категорії
    if not picked:                     # жодна мітка не збіглася (одруківка тощо) - не гальмуємо прогін тихо
        print(f"   ⚠️ SCRAPE_CATEGORIES='{raw}' не збіглося з жодною міткою — беремо всі.")
        return CATEGORIES
    return picked
