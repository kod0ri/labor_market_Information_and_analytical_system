"""Юніт-тести каскаду: вибір провайдера, fallback на 429, cooldown, бюджет."""

from types import SimpleNamespace

import pytest

from src.processor import llm_cascade as lc
from src.processor.llm_cascade import (
    LLMProvider,
    _ProviderSpec,
    complete,
    cascade_summary,
    provider_names,
    any_available,
    AllProvidersExhausted,
    AllProvidersBusy,
)


# ─── фейкові клієнти/провайдери ──────────────────────────────────────────────

def _completion(text="{}", tokens=100):
    return SimpleNamespace(
        usage=SimpleNamespace(total_tokens=tokens),
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
    )


class _FakeCompletions:
    def __init__(self, handler):
        self._handler = handler
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._handler(kwargs)     # повертає completion або кидає виняток


def make_provider(name, model="m", *, handler=None, tpd=1_000_000, rpd=1000, extra_body=None):
    spec = _ProviderSpec(
        name=name, base_url="http://x", api_key_env="X", model_env="Y",
        default_model=model, tpd_limit=tpd, rpd_limit=rpd,
        rate_per_second=1e6, extra_body=extra_body or {},  # rate великий → acquire миттєвий
    )
    p = LLMProvider(spec, "key", model)
    fake = _FakeCompletions(handler or (lambda kwargs: _completion()))
    p.client = SimpleNamespace(chat=SimpleNamespace(completions=fake))
    p._fake = fake
    return p


def _raise_429(_kwargs):
    raise RuntimeError("Error code: 429 - rate_limit_exceeded. Please try again in 7s.")


@pytest.fixture
def set_providers(monkeypatch):
    return lambda providers: monkeypatch.setattr(lc, "PROVIDERS", providers)


# ─── тести ───────────────────────────────────────────────────────────────────

async def test_uses_first_available_provider(set_providers):
    p1, p2 = make_provider("p1", "m1"), make_provider("p2", "m2")
    set_providers([p1, p2])
    text, name, model = await complete([{"role": "user", "content": "hi"}])
    assert (name, model) == ("p1", "m1")
    assert len(p1._fake.calls) == 1
    assert len(p2._fake.calls) == 0      # до другого не дійшло


async def test_falls_back_on_429_and_trips_cooldown(set_providers):
    p1 = make_provider("p1", "m1", handler=_raise_429)
    p2 = make_provider("p2", "m2")
    set_providers([p1, p2])
    _text, name, _model = await complete([{"role": "user", "content": "hi"}])
    assert name == "p2"                   # впали на наступного
    assert p1.cooldown_left() > 0         # p1 «остудили» після 429
    assert len(p2._fake.calls) == 1


async def test_extra_body_passed_through(set_providers):
    p1 = make_provider("p1", "m1", extra_body={"reasoning_effort": "low"})
    set_providers([p1])
    await complete([{"role": "user", "content": "hi"}])
    assert p1._fake.calls[0]["extra_body"] == {"reasoning_effort": "low"}


async def test_all_exhausted_raises_and_makes_no_calls(set_providers):
    p1 = make_provider("p1", tpd=100)     # is_exhausted одразу (0+850 >= 96)
    p2 = make_provider("p2", tpd=100)
    set_providers([p1, p2])
    with pytest.raises(AllProvidersExhausted):
        await complete([{"role": "user", "content": "hi"}])
    assert p1._fake.calls == [] and p2._fake.calls == []


async def test_all_in_cooldown_raises_busy(set_providers):
    p1, p2 = make_provider("p1"), make_provider("p2")
    p1.trip_cooldown(50)
    p2.trip_cooldown(30)
    set_providers([p1, p2])
    with pytest.raises(AllProvidersBusy) as ei:
        await complete([{"role": "user", "content": "hi"}])
    assert 0 < ei.value.retry_after <= 50  # найближчий кулдаун


async def test_budget_recorded_on_success(set_providers):
    p1 = make_provider("p1", "m1", handler=lambda k: _completion(tokens=123))
    set_providers([p1])
    await complete([{"role": "user", "content": "hi"}])
    assert p1.budget._tokens == 123
    assert p1.budget._requests == 1


async def test_no_providers_raises_runtime(set_providers):
    set_providers([])
    with pytest.raises(RuntimeError):
        await complete([{"role": "user", "content": "hi"}])


async def test_cascade_helpers(set_providers):
    p1, p2 = make_provider("p1", "m1"), make_provider("p2", "m2")
    set_providers([p1, p2])
    assert cascade_summary() == "p1=m1 → p2=m2"
    assert provider_names() == ["p1", "p2"]
    assert any_available() is True


async def test_empty_response_skips_provider(set_providers):
    # порожня відповідь → провайдер не дав результату, але інший підхоплює
    p1 = make_provider("p1", "m1", handler=lambda k: _completion(text="", tokens=0))
    p2 = make_provider("p2", "m2", handler=lambda k: _completion(text="{\"ok\":1}"))
    set_providers([p1, p2])
    _text, name, _model = await complete([{"role": "user", "content": "hi"}])
    assert name == "p2"
