from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Any


class SkillSchema(BaseModel):
    name: str
    category: str = "Hard"
    # Роки досвіду для конкретної навички нам не потрібні, БД це не підтримує


class VacancySchema(BaseModel):
    skills: List[SkillSchema] = Field(default_factory=list)
    experience_years: Optional[int] = None
    english_level: Optional[str] = None
    min_salary: Optional[int] = None
    max_salary: Optional[int] = None
    currency: Optional[str] = None

    company_name: Optional[str] = None
    location_name: Optional[str] = None
    company_industry: Optional[str] = None
    website_url: Optional[str] = None
    region: Optional[str] = None
    
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
        fixed_skills = []
        for item in v:
            if isinstance(item, str) and item.strip():
                fixed_skills.append({"name": item, "category": "Hard"})
            elif isinstance(item, dict):
                if not item.get("name"):
                    continue
                fixed_skills.append(
                    {"name": item.get("name"), "category": item.get("category", "Hard")}
                )
        return fixed_skills


class ResumeSchema(BaseModel):
    title: str = "Не вказано"
    location_name: Optional[str] = None
    region: Optional[str] = None
    min_salary: Optional[int] = None  # Замість expected_salary
    max_salary: Optional[int] = None  # Додано для сумісності з БД
    currency: Optional[str] = None
    experience_years: Optional[int] = None
    english_level: Optional[str] = None
    skills: List[SkillSchema] = Field(default_factory=list)

    @field_validator("title", mode="before")
    @classmethod
    def fix_title(cls, v: Any) -> str:
        return str(v) if v else "Не вказано"
    
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
        fixed_skills = []
        for item in v:
            if isinstance(item, str) and item.strip():
                fixed_skills.append({"name": item, "category": "Hard"})
            elif isinstance(item, dict):
                if not item.get("name"):
                    continue
                fixed_skills.append(
                    {"name": item.get("name"), "category": item.get("category", "Hard")}
                )
        return fixed_skills
