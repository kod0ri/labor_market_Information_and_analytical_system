"""Тести валідаторів LLM-схем (src/processor/schemas.py)."""

from src.processor.schemas import ResumeSchema, VacancySchema


def test_currency_aliases_normalized():
    assert VacancySchema(currency="грн").currency == "UAH"
    assert VacancySchema(currency="ГРИВНЯ").currency == "UAH"
    assert VacancySchema(currency="euro").currency == "EUR"
    assert VacancySchema(currency="usd").currency == "USD"


def test_currency_null_like_becomes_none():
    for junk in (None, "null", "NULL", "", "Null"):
        assert VacancySchema(currency=junk).currency is None


def test_english_level_cefr_and_words():
    assert VacancySchema(english_level="B2").english_level == "Upper-Intermediate"
    assert VacancySchema(english_level="a1").english_level == "Beginner"
    assert VacancySchema(english_level="вільна").english_level == "Advanced"
    # Невідоме значення → None (щоб не засмічувати аналітику).
    assert VacancySchema(english_level="conversational").english_level is None


def test_skills_coerced_from_strings_and_dicts():
    v = VacancySchema(skills=["Python", {"name": "SQL", "category": "Hard"}, {"no": "name"}, 123])
    names = {s.name for s in v.skills}
    assert names == {"Python", "SQL"}  # безіменні/нерядкові відкинуто
    assert all(s.category for s in v.skills)


def test_skills_non_list_becomes_empty():
    assert VacancySchema(skills="Python").skills == []


def test_resume_expected_salary_maps_to_min_max():
    r = ResumeSchema(expected_salary=2500)
    assert r.min_salary == 2500 and r.max_salary == 2500


def test_resume_expected_salary_does_not_override_explicit():
    r = ResumeSchema(expected_salary=2500, min_salary=1000)
    assert r.min_salary == 1000  # явний min не перетирається
    assert r.max_salary == 2500  # max беремо з expected


def test_resume_title_fallback():
    assert ResumeSchema(title=None).title == "Не вказано"
    assert ResumeSchema().title == "Не вказано"
