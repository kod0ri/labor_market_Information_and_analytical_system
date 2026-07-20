"""
Pydantic-схеми очікуваного JSON-виводу LLM для вакансій і резюме.

Кожен `field_validator(mode="before")` тут - не проста типізація, а захист від
конкретних, реально спостережених "галюцинацій"/неохайності LLM-виводу:
альтернативні написання валюти кирилицею, CEFR-коди замість слів, навички
рядком замість об'єкта, назва компанії, що насправді є плейсхолдером сайту.
Якщо валідатор не впорався - Pydantic кине ValidationError, і виклик
піде на retry в run_llm_record (nlp_pipeline.py), а не запишеться в БД сміттям.
"""

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
    # Рубрика «IT» на джерелах містить і суміжні посади (SMM, продажі тощо).
    # Дефолт True: якщо LLM поле пропустила, запис не викидаємо з аналітики.
    it_related: bool = True
    skills: List[SkillSchema] = Field(default_factory=list)

    @field_validator("it_related", mode="before")
    @classmethod
    def fix_it_related(cls, v: Any) -> bool:
        if v is None or v == "":              # поле пропущене LLM - беремо безпечний дефолт True
            return True
        if isinstance(v, str):                 # LLM іноді пише "true"/"false" рядком, а не bool
            return v.strip().lower() not in ("false", "no", "ні", "0")   # усе, крім явного "заперечення" → True
        return bool(v)                          # уже bool/число - звичайне приведення типу

    @field_validator("currency", mode="before")
    @classmethod
    def fix_currency(cls, v: Any) -> str | None:
        if v in (None, "null", "NULL", "", "Null"):   # LLM могла повернути ці рядки замість справжнього null
            return None
        normalized = str(v).upper().strip()            # приводимо регістр і прибираємо пробіли перед пошуком
        return _CURRENCY_ALIASES.get(normalized, normalized)  # мапимо кириличний варіант, якщо є; інакше лишаємо як є

    @field_validator("english_level", mode="before")
    @classmethod
    def fix_english_level(cls, v: Any) -> str | None:
        if not v or str(v).strip().lower() in ("null", "none", ""):  # порожньо чи текстовий "null"
            return None
        return _ENGLISH_LEVEL_MAP.get(str(v).strip().upper())   # шукаємо в словнику; немає збігу → None (а не помилка)

    @field_validator("skills", mode="before")
    @classmethod
    def fix_skills(cls, v: Any) -> Any:
        if not isinstance(v, list):     # LLM могла повернути не-масив (напр. рядок) - трактуємо як "немає навичок"
            return []
        fixed = []                       # тут накопичуємо нормалізовані {name, category} записи
        for item in v:
            if isinstance(item, str) and item.strip():   # навичка прийшла просто рядком, без category
                fixed.append({"name": item, "category": "Hard"})   # дефолтна категорія Hard
            elif isinstance(item, dict) and item.get("name"):       # очікувана форма {name, category}
                fixed.append({
                    "name": item["name"],
                    "category": item.get("category", "Hard"),        # category теж міг бути відсутнім
                })
            # інакше (порожній dict, число тощо) - тихо пропускаємо цей елемент
        return fixed


# Бейджі/заглушки джерел, які LLM приймає за назву роботодавця:
# «Є гроші» — позначка work.ua «зарплата вказана», решта — плейсхолдери.
_COMPANY_GARBAGE: set[str] = {
    "є гроші", "не вказано", "не вказана", "компанія", "компанія прихована",
    "unknown", "n/a", "none", "null", "-", "—",
}


class VacancySchema(_BaseJobSchema):
    company_name: Optional[str] = None
    company_industry: Optional[str] = None
    website_url: Optional[str] = None

    @field_validator("company_name", mode="before")
    @classmethod
    def fix_company_name(cls, v: Any) -> str | None:
        if not v:                     # LLM не знайшла назву компанії
            return None
        name = str(v).strip()
        if len(name) < 2 or name.casefold() in _COMPANY_GARBAGE:   # 1-символьне сміття або відомий плейсхолдер
            return None
        return name


class ResumeSchema(_BaseJobSchema):
    title: str = "Не вказано"
    # LLM повертає expected_salary — маппимо в min/max через model_post_init.
    expected_salary: Optional[int] = Field(default=None, exclude=True)

    def model_post_init(self, __context: Any) -> None:  # pyright: ignore[reportUnusedParameter]
        # Резюме має ОДНЕ бажане число ЗП (expected_salary), а не діапазон
        # (min/max) як вакансія - дублюємо його в обидва поля БД, щоб таблиця
        # core.resumes мала ту саму пару колонок, що й core.vacancies, і
        # аналітика "розподіл зарплат" могла рахувати вакансії й резюме однаково.
        if self.expected_salary is not None:      # LLM таки повернула бажану ЗП
            if self.min_salary is None:            # не перезаписуємо, якщо LLM ЧОМУСЬ уже заповнила min_salary
                self.min_salary = self.expected_salary
            if self.max_salary is None:            # так само для max_salary
                self.max_salary = self.expected_salary

    @field_validator("title", mode="before")
    @classmethod
    def fix_title(cls, v: Any) -> str:
        return str(v) if v else "Не вказано"
