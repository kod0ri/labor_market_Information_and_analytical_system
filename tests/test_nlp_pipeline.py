"""Тести спільного LLM-оркестратора (src/processor/nlp_pipeline.py).

Ганяємо каркас із фейковим complete / persist / БД — без мережі й без БД.
Перевіряємо шляхи: успіх, вичерпаний бюджет, транзієнтна зайнятість,
галюцинація (ValidationError) і загальна помилка.
"""

import asyncio
import contextlib

import pytest
from pydantic import BaseModel

import src.processor.nlp_pipeline as pipe
from src.processor.llm_cascade import AllProvidersBusy, AllProvidersExhausted


class Strict(BaseModel):
    n: int  # '{"n":5}' валідний; '{"n":"x"}' → ValidationError


class _FakeConn:
    def transaction(self):
        @contextlib.asynccontextmanager
        async def _cm():
            yield None
        return _cm()


@contextlib.asynccontextmanager
async def _fake_get_connection():
    yield _FakeConn()


@pytest.fixture
def wiring(monkeypatch):
    """Підміняє зовнішні залежності оркестратора; повертає лічильники/керування."""
    state = {"complete_calls": 0, "persist_calls": 0, "failures": []}

    async def _noop_sleep(*a, **k):
        return None

    monkeypatch.setattr(pipe.AsyncDatabasePool, "get_connection", _fake_get_connection)
    monkeypatch.setattr(pipe.asyncio, "sleep", _noop_sleep)
    monkeypatch.setattr(pipe, "any_available", lambda *a, **k: True)

    async def _record_failure(conn, rtype, sid, etype, detail, attempts):
        state["failures"].append((rtype, etype, detail))

    monkeypatch.setattr(pipe, "record_failure", _record_failure)
    return state, monkeypatch


async def _persist_ok(state):
    async def _p(conn, ai_data):
        state["persist_calls"] += 1
        return "label"
    return _p


async def test_success(wiring):
    state, mp = wiring

    async def _complete(messages):
        state["complete_calls"] += 1
        return '{"n": 5}', "groq", "llama"

    mp.setattr(pipe, "complete", _complete)

    ok = await pipe.run_llm_record(
        staging_id=1, record_type="vacancy", messages=[],
        schema_cls=Strict, db_semaphore=asyncio.Semaphore(1),
        persist=await _persist_ok(state),
    )
    assert ok is True
    assert state["complete_calls"] == 1
    assert state["persist_calls"] == 1
    assert state["failures"] == []


async def test_no_budget_skips(wiring):
    state, mp = wiring
    mp.setattr(pipe, "any_available", lambda *a, **k: False)

    async def _complete(messages):
        state["complete_calls"] += 1
        return '{"n": 5}', "g", "m"

    mp.setattr(pipe, "complete", _complete)

    ok = await pipe.run_llm_record(
        staging_id=2, record_type="vacancy", messages=[],
        schema_cls=Strict, db_semaphore=asyncio.Semaphore(1),
        persist=await _persist_ok(state),
    )
    assert ok is False
    assert state["complete_calls"] == 0  # навіть не питали LLM
    assert state["failures"] == []       # не фіксуємо провал


async def test_transient_busy_not_recorded(wiring):
    state, mp = wiring

    async def _complete(messages):
        state["complete_calls"] += 1
        raise AllProvidersBusy(retry_after=0.0)

    mp.setattr(pipe, "complete", _complete)

    ok = await pipe.run_llm_record(
        staging_id=3, record_type="resume", messages=[],
        schema_cls=Strict, db_semaphore=asyncio.Semaphore(1),
        persist=await _persist_ok(state),
    )
    assert ok is False
    assert state["complete_calls"] == 3   # усі спроби
    assert state["failures"] == []        # rate-limit не фіксуємо як провал


async def test_exhausted_budget_midway(wiring):
    state, mp = wiring

    async def _complete(messages):
        raise AllProvidersExhausted("no budget")

    mp.setattr(pipe, "complete", _complete)

    ok = await pipe.run_llm_record(
        staging_id=4, record_type="vacancy", messages=[],
        schema_cls=Strict, db_semaphore=asyncio.Semaphore(1),
        persist=await _persist_ok(state),
    )
    assert ok is False
    assert state["persist_calls"] == 0


async def test_validation_error_records_failure(wiring):
    state, mp = wiring

    async def _complete(messages):
        state["complete_calls"] += 1
        return '{"n": "not-an-int"}', "g", "m"   # завжди галюцинує

    mp.setattr(pipe, "complete", _complete)

    ok = await pipe.run_llm_record(
        staging_id=5, record_type="vacancy", messages=[],
        schema_cls=Strict, db_semaphore=asyncio.Semaphore(1),
        persist=await _persist_ok(state),
    )
    assert ok is False
    assert state["complete_calls"] == 3
    assert state["persist_calls"] == 0
    assert any(f[1] == "validation" for f in state["failures"])


async def test_generic_error_records_unknown_and_stops(wiring):
    state, mp = wiring

    async def _complete(messages):
        state["complete_calls"] += 1
        raise RuntimeError("boom")

    mp.setattr(pipe, "complete", _complete)

    ok = await pipe.run_llm_record(
        staging_id=6, record_type="resume", messages=[],
        schema_cls=Strict, db_semaphore=asyncio.Semaphore(1),
        persist=await _persist_ok(state),
    )
    assert ok is False
    assert state["complete_calls"] == 1          # без retry на невідомій помилці
    assert any(f[1] == "unknown" for f in state["failures"])
