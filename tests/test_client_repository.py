"""Тести побудови WHERE у клієнтських репозиторіях (src/client/repository.py).

_build_where — чиста функція (без БД): будує список умов і позиційні параметри.
Перевіряємо параметризацію (жодної інтерполяції значень у SQL) і семантику.
"""

from src.client.repository import ResumeRepository, VacancyRepository


def test_empty_filters():
    clauses, params = VacancyRepository()._build_where({})
    assert clauses == [] and params == []


def test_all_values_are_parameterized():
    filters = {
        "skill": "Python",
        "location": "Київ",
        "min_salary_usd": 1000,
        "experience_max": 3,
        "english_level": "Intermediate",
        "source": "work.ua",
    }
    clauses, params = VacancyRepository()._build_where(filters)
    # Кожна умова додає рівно один параметр; значення не потрапляють у SQL-текст.
    assert len(params) == len(clauses) == 6
    sql = " ".join(clauses)
    assert "Python" not in sql and "Київ" not in sql
    assert "$1" in sql and "$6" in sql


def test_skill_lowercased_for_match():
    _, params = VacancyRepository()._build_where({"skill": "PyThOn"})
    assert params == ["python"]


def test_location_wrapped_for_like():
    _, params = VacancyRepository()._build_where({"location": "Львів"})
    assert params == ["%Львів%"]


def test_placeholder_numbering_is_sequential():
    filters = {"min_salary_usd": 500, "english_level": "Advanced"}
    clauses, params = VacancyRepository()._build_where(filters)
    joined = " ".join(clauses)
    assert "$1" in joined and "$2" in joined
    assert params == [500, "Advanced"]


def test_vacancy_experience_is_upper_bound():
    clauses, _ = VacancyRepository()._build_where({"experience_max": 5})
    assert any("experience_years <=" in c for c in clauses)


def test_resume_experience_is_lower_bound():
    # Для резюме той самий ключ означає МІНІМАЛЬНИЙ досвід (>=).
    clauses, _ = ResumeRepository()._build_where({"experience_max": 5})
    assert any("experience_years >=" in c for c in clauses)
