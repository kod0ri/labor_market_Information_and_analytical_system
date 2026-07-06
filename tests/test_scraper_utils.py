"""Тести спільного парсера карток work.ua (src/scrapers/utils.py)."""

from src.scrapers.utils import parse_card_links

_HTML = """
<html><body>
  <div class="card-hover"><a href="/jobs/111/">Вакансія A</a></div>
  <div class="card-hover"><a href="/jobs/222/foo">Вакансія B</a></div>
  <div class="card-hover"><a href="/resumes/999/">Резюме</a></div>
  <div class="card-hover"><span>без посилання</span></div>
  <div class="other"><a href="/jobs/333/">не картка</a></div>
</body></html>
"""


def test_extracts_only_matching_prefix():
    jobs = parse_card_links(_HTML, "/jobs/")
    assert jobs == {
        "111": "https://www.work.ua/jobs/111/",
        "222": "https://www.work.ua/jobs/222/foo",
    }


def test_resume_prefix_isolated():
    resumes = parse_card_links(_HTML, "/resumes/")
    assert resumes == {"999": "https://www.work.ua/resumes/999/"}


def test_empty_html():
    assert parse_card_links("<html></html>", "/jobs/") == {}
