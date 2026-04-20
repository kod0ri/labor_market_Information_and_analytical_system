from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Any


class SkillSchema(BaseModel):
    name: str
    category: str = "Hard"
    years_of_experience: Optional[int] = None


class VacancySchema(BaseModel):
    skills: List[SkillSchema] = Field(default_factory=list)
    experience_years: Optional[int] = None
    english_level: Optional[str] = None
    min_salary: Optional[int] = None
    max_salary: Optional[int] = None
    currency: Optional[str] = None
    company_industry: Optional[str] = None
    website_url: Optional[str] = None
    region: Optional[str] = None

    @field_validator("skills", mode="before")
    @classmethod
    def fix_skills(cls, v: Any) -> Any:
        """Перетворює список рядків від лінивої LLM на список об'єктів"""
        if not isinstance(v, list):
            return []

        fixed_skills = []
        for item in v:
            if isinstance(item, str):
                fixed_skills.append({"name": item, "category": "Hard"})
            elif isinstance(item, dict):
                # Якщо модель забула передати name, пропускаємо
                if "name" not in item:
                    continue
                if "category" not in item:
                    item["category"] = "Hard"
                fixed_skills.append(item)
        return fixed_skills


class ResumeSchema(BaseModel):
    title: str = "Не вказано"
    location_name: Optional[str] = None
    region: Optional[str] = None
    expected_salary: Optional[int] = None
    currency: Optional[str] = None
    experience_years: Optional[int] = None
    english_level: Optional[str] = None
    skills: List[SkillSchema] = Field(default_factory=list)

    @field_validator("title", mode="before")
    @classmethod
    def fix_title(cls, v: Any) -> str:
        """Якщо LLM не знайшла посаду і повернула null"""
        if not v:
            return "Не вказано"
        return str(v)

    @field_validator("skills", mode="before")
    @classmethod
    def fix_skills(cls, v: Any) -> Any:
        """Перетворює список рядків від лінивої LLM на список об'єктів"""
        if not isinstance(v, list):
            return []

        fixed_skills = []
        for item in v:
            if isinstance(item, str):
                fixed_skills.append({"name": item, "category": "Hard"})
            elif isinstance(item, dict):
                if "name" not in item:
                    continue
                if "category" not in item:
                    item["category"] = "Hard"
                fixed_skills.append(item)
        return fixed_skills
