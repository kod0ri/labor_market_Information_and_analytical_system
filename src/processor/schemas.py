from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Any


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
        return str(v).upper().strip()

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
