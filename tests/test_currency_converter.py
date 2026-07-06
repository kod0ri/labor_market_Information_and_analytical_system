"""Тести отримання курсів НБУ (src/processor/currency_converter.py).

Ключовий інваріант: при збої/неповній відповіді НБУ курс НЕ фабрикується —
повертається None (або валюта відсутня у словнику), щоб записи лишились на
наступний прогін, а не законсервувалися з вигаданим курсом.
"""

import src.processor.currency_converter as cc


class _Resp:
    def __init__(self, data, raise_exc=None):
        self._data, self._raise = data, raise_exc

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def raise_for_status(self):
        if self._raise:
            raise self._raise

    async def json(self):
        return self._data


class _Session:
    def __init__(self, data, raise_exc=None):
        self._data, self._raise = data, raise_exc

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def get(self, url, timeout=None):
        return _Resp(self._data, self._raise)


class _FakeAiohttp:
    def __init__(self, data, raise_exc=None):
        self._data, self._raise = data, raise_exc

    def ClientSession(self):
        return _Session(self._data, self._raise)

    def ClientTimeout(self, **kwargs):
        return None


def _patch(monkeypatch, data, raise_exc=None):
    monkeypatch.setattr(cc, "aiohttp", _FakeAiohttp(data, raise_exc))


async def test_success_usd_and_eur(monkeypatch):
    _patch(monkeypatch, [{"cc": "USD", "rate": 40.0}, {"cc": "EUR", "rate": 44.0}])
    rates = await cc.get_conversion_rates()
    assert rates["USD"] == 1.0
    assert rates["UAH"] == 1.0 / 40.0
    assert rates["EUR"] == 44.0 / 40.0


async def test_missing_eur_omits_eur_key(monkeypatch):
    # USD є, EUR немає → конвертуємо USD/UAH, EUR-записи відкладаємо (нема ключа).
    _patch(monkeypatch, [{"cc": "USD", "rate": 40.0}])
    rates = await cc.get_conversion_rates()
    assert "EUR" not in rates
    assert rates["USD"] == 1.0 and rates["UAH"] == 1.0 / 40.0


async def test_missing_usd_returns_none(monkeypatch):
    _patch(monkeypatch, [{"cc": "EUR", "rate": 44.0}])
    assert await cc.get_conversion_rates() is None


async def test_network_error_returns_none(monkeypatch):
    _patch(monkeypatch, [], raise_exc=RuntimeError("boom"))
    assert await cc.get_conversion_rates() is None


async def test_run_conversion_skips_when_no_rates(monkeypatch):
    # Якщо курсів немає — конвертація не має чіпати БД узагалі.
    async def _no_rates():
        return None

    monkeypatch.setattr(cc, "get_conversion_rates", _no_rates)

    def _boom(*a, **k):
        raise AssertionError("get_connection не має викликатися без курсів")

    monkeypatch.setattr(cc.AsyncDatabasePool, "get_connection", _boom)
    await cc.run_conversion()  # не кидає, нічого не пише
