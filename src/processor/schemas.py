from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Any


_CURRENCY_ALIASES: dict[str, str] = {
    "ГРН": "UAH", "ГРИВНЯ": "UAH", "ГРИВЕНЬ": "UAH", "HRYVNIA": "UAH",
    "ЄВРО": "EUR", "EURO": "EUR",
    "ДОЛАР": "USD", "DOLLAR": "USD", "DOLLARS": "USD", "ДОЛАРІВ": "USD",
}

_ENGLISH_LEVEL_MAP: dict[str, str] = {
    "A1": "Beginner", "A2": "Elementary",
    "B1": "Pre-Intermediate", "B2": "Upper-Intermediate",
    "C1": "Advanced", "C2": "Fluent",
    "BEGINNER": "Beginner",
    "ELEMENTARY": "Elementary",
    "PRE-INTERMEDIATE": "Pre-Intermediate", "PRE INTERMEDIATE": "Pre-Intermediate",
    "INTERMEDIATE": "Intermediate",
    "UPPER-INTERMEDIATE": "Upper-Intermediate", "UPPER INTERMEDIATE": "Upper-Intermediate",
    "ADVANCED": "Advanced",
    "FLUENT": "Fluent",
    "NATIVE": "Native",
    "ПОЧАТКОВИЙ": "Beginner",
    "ЕЛЕМЕНТАРНИЙ": "Elementary", "БАЗОВИЙ": "Elementary",
    "СЕРЕДНІЙ": "Intermediate", "СЕРЕДНЄ": "Intermediate",
    "ВИЩЕ СЕРЕДНЬОГО": "Upper-Intermediate",
    "ВІЛЬНО": "Advanced", "ВІЛЬНА": "Advanced", "ВІЛЬНЕ": "Advanced",
    "ДОСКОНАЛО": "Fluent", "ДОСКОНАЛЕ": "Fluent",
}


class SkillSchema(BaseModel):
    name: str
    category: str = "Hard"


class _BaseJobSchema(BaseModel):
    """Спільні поля і validators для VacancySchema та ResumeSchema."""
    location_name: Optional[str] = None
    region: Optional[str] = None
    min_salary: Optional[int] = None
    max_salary: Optional[int] = None
    currency: Optional[str] = None
    experience_years: Optional[int] = None
    english_level: Optional[str] = None
    skills: List[SkillSchema] = Field(default_factory=list)

    @field_validator("currency", mode="before")
    @classmethod
    def fix_currency(cls, v: Any) -> str | None:
        if v in (None, "null", "NULL", "", "Null"):
            return None
        normalized = str(v).upper().strip()
        return _CURRENCY_ALIASES.get(normalized, normalized)

    @field_validator("english_level", mode="before")
    @classmethod
    def fix_english_level(cls, v: Any) -> str | None:
        if not v or str(v).strip().lower() in ("null", "none", ""):
            return None
        return _ENGLISH_LEVEL_MAP.get(str(v).strip().upper())

    @field_validator("skills", mode="before")
    @classmethod
    def fix_skills(cls, v: Any) -> Any:
        if not isinstance(v, list):
            return []
        fixed = []
        for item in v:
            if isinstance(item, str) and item.strip():
                fixed.append({"name": item, "category": "Hard"})
            elif isinstance(item, dict) and item.get("name"):
                fixed.append({
                    "name": item["name"],
                    "category": item.get("category", "Hard"),
                })
        return fixed


class VacancySchema(_BaseJobSchema):
    company_name: Optional[str] = None
    company_industry: Optional[str] = None
    website_url: Optional[str] = None


class ResumeSchema(_BaseJobSchema):
    title: str = "Не вказано"
    # LLM повертає expected_salary — маппимо в min/max через model_post_init.
    expected_salary: Optional[int] = Field(default=None, exclude=True)

    def model_post_init(self, __context: Any) -> None:  # pyright: ignore[reportUnusedParameter]
        if self.expected_salary is not None:
            if self.min_salary is None:
                self.min_salary = self.expected_salary
            if self.max_salary is None:
                self.max_salary = self.expected_salary

    @field_validator("title", mode="before")
    @classmethod
    def fix_title(cls, v: Any) -> str:
        return str(v) if v else "Не вказано"
