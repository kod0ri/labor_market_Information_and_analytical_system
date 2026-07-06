"""Тести MarketDataFacade (src/client/facade.py) з фейковими репозиторіями.

Перевіряємо контракт із репозиторієм після оптимізації: find_many повертає
(items, total); окремий count() викликається ЛИШЕ коли total is None
(порожня сторінка), а не на кожен пошук.
"""

from src.client.facade import MarketDataFacade


class _FakeRepo:
    def __init__(self, items, total):
        self._items, self._total = items, total
        self.count_calls = 0

    async def find_many(self, conn, filters, limit, offset):
        return self._items, self._total

    async def count(self, conn, filters):
        self.count_calls += 1
        return 42


async def test_uses_window_total_without_extra_count():
    repo = _FakeRepo(items=[{"id": 1}], total=7)
    facade = MarketDataFacade(vacancy_repo=repo, resume_repo=repo)
    result = await facade.search_vacancies(conn=None, page=1, page_size=20)
    assert result["total"] == 7
    assert result["pages"] == 1
    assert repo.count_calls == 0  # окремий count не потрібен


async def test_falls_back_to_count_on_empty_page():
    repo = _FakeRepo(items=[], total=None)
    facade = MarketDataFacade(vacancy_repo=repo, resume_repo=repo)
    result = await facade.search_vacancies(conn=None, page=99, page_size=20)
    assert result["total"] == 42        # добрано лічильником
    assert repo.count_calls == 1


async def test_pages_rounding():
    repo = _FakeRepo(items=[{"id": 1}], total=45)
    facade = MarketDataFacade(vacancy_repo=repo, resume_repo=repo)
    result = await facade.search_resumes(conn=None, page=1, page_size=20)
    assert result["pages"] == 3         # ceil(45/20)


async def test_pages_never_below_one():
    repo = _FakeRepo(items=[], total=0)
    facade = MarketDataFacade(vacancy_repo=repo, resume_repo=repo)
    result = await facade.search_vacancies(conn=None, page=1, page_size=20)
    assert result["pages"] == 1
