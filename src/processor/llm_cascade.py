"""
LLM-каскад: послідовний fallback по безкоштовних OpenAI-сумісних провайдерах.

Пріоритет за замовчуванням: Cerebras → Groq → Gemini → Mistral.
На кожен запит береться перший провайдер, чий денний бюджет ще не вичерпано;
при rate-limit / помилці падаємо на наступного. Денна стеля кожного провайдера —
окремий DailyBudget, тож сумарна добова продуктивність = сума їхніх квот.

Усі провайдери викликаються через openai.AsyncOpenAI з різним base_url —
форма виклику (chat.completions + response_format=json_object) однакова.
Активуються лише ті провайдери, для яких у .env заданий API-ключ.

Безкоштовні денні ліміти (станом на 2026, орієнтовно — звіряти з доками):
    Cerebras  gpt-oss-120b               1M ток/добу, 5 RPM / 150 RPH / 2400 RPD, без картки
    Groq      llama-4-scout-17b          500K токенів/добу, 1K запитів/добу
    Gemini    gemini-3.1-flash-lite      500 запитів/добу free tier (RPD б'є; 2.5-flash лише 20)
    Mistral   mistral-small-latest       1 млрд токенів/МІСЯЦЬ (Experiment, 1 req/s)
"""

import os
import time
from dataclasses import dataclass, field

from dotenv import load_dotenv
from openai import AsyncOpenAI

from src.processor.llm_utils import _parse_retry_after
from src.processor.rate_limiter import TokenBucketRateLimiter, DailyBudget

# PROVIDERS будується на імпорті — .env треба підхопити ДО цього. У Docker
# ключі вже в оточенні (env_file), тут load_dotenv() стає безпечним no-op.
load_dotenv()


@dataclass(frozen=True)
class _ProviderSpec:
    name: str
    base_url: str
    api_key_env: str
    model_env: str
    default_model: str
    tpd_limit: int          # денний ліміт токенів (для request-bound — завищений)
    rpd_limit: int          # денний ліміт запитів (для token-bound — завищений)
    rate_per_second: float  # пейсинг під RPM провайдера (із запасом)
    # провайдер-специфічні поля тіла запиту (напр. reasoning_effort для gpt-oss)
    extra_body: dict = field(default_factory=dict)


# Завищені (non-binding) ліміти ставимо в те поле, яке у провайдера НЕ є вузьким
# місцем, щоб гейтив саме реальний cap. Числа консервативні — краще недобрати.
_SPECS: dict[str, _ProviderSpec] = {
    "cerebras": _ProviderSpec(
        name="cerebras",
        base_url="https://api.cerebras.ai/v1",
        api_key_env="CEREBRAS_API_KEY",
        model_env="CEREBRAS_MODEL",
        default_model="gpt-oss-120b",   # єдина production-модель на free public endpoint
        tpd_limit=1_000_000,      # реальна стеля (TPD б'є раніше за RPD)
        rpd_limit=2_400,          # реальний RPD (не б'є — TPD/~980 ≈ 1020 раніше)
        rate_per_second=0.08,     # 5 RPM — жорсткий хвилинний ліміт Cerebras (інакше 429)
        # gpt-oss — reasoning-модель; "low" ріже output ~2-3× (1640→~1000 ток/запис)
        extra_body={"reasoning_effort": "low"},
    ),
    "groq": _ProviderSpec(
        name="groq",
        base_url="https://api.groq.com/openai/v1",
        api_key_env="GROQ_API_KEY",
        model_env="GROQ_MODEL",
        default_model="meta-llama/llama-4-scout-17b-16e-instruct",
        tpd_limit=500_000,        # реальна стеля (TPD б'є раніше за RPD)
        rpd_limit=1_000,
        rate_per_second=0.12,     # ~7 req/min — під реальний TPM free-tier (інакше 429-шторм)
    ),
    "gemini": _ProviderSpec(
        name="gemini",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        api_key_env="GEMINI_API_KEY",
        model_env="GEMINI_MODEL",
        # free tier (RPD): flash-lite 3.1 = 500, а 2.5-flash/3.5-flash лише 20 RPD.
        default_model="gemini-3.1-flash-lite",
        tpd_limit=50_000_000,     # non-binding (gemini ріже по запитах)
        rpd_limit=500,            # реальна стеля free-tier для flash-lite 3.1
        rate_per_second=0.2,      # ~12 req/min, під 15 RPM
    ),
    "mistral": _ProviderSpec(
        name="mistral",
        base_url="https://api.mistral.ai/v1",
        api_key_env="MISTRAL_API_KEY",
        model_env="MISTRAL_MODEL",
        default_model="mistral-small-latest",
        tpd_limit=30_000_000,     # ~1 млрд/міс ÷ 30; місячний cap тут не трекаємо
        rpd_limit=50_000,
        rate_per_second=0.5,      # free Experiment: 1 req/s
    ),
}

DEFAULT_ORDER = ["cerebras", "groq", "gemini", "mistral"]


class LLMProvider:
    """Один провайдер каскаду: клієнт + модель + власний rate-limiter і бюджет."""

    def __init__(self, spec: _ProviderSpec, api_key: str, model: str):
        self.name = spec.name
        self.model = model
        self.client = AsyncOpenAI(api_key=api_key, base_url=spec.base_url)
        self.rate_limiter = TokenBucketRateLimiter(
            rate_per_second=spec.rate_per_second, burst=1
        )
        self.budget = DailyBudget(spec.name, spec.tpd_limit, spec.rpd_limit)
        self.extra_body = dict(spec.extra_body)
        # Спільний на процес «холодильник»: після 429 провайдер пропускається
        # всіма паралельними задачами до цього моменту (monotonic time).
        self.cooldown_until = 0.0

    def cooldown_left(self) -> float:
        return max(0.0, self.cooldown_until - time.monotonic())

    def trip_cooldown(self, seconds: float) -> None:
        self.cooldown_until = time.monotonic() + seconds


def _build_providers() -> list[LLMProvider]:
    """Збирає каскад із .env: порядок з LLM_PROVIDER_ORDER або DEFAULT_ORDER,
    активує лише провайдерів із заданим API-ключем."""
    order_env = os.getenv("LLM_PROVIDER_ORDER", "")
    order = [p.strip().lower() for p in order_env.split(",") if p.strip()] or DEFAULT_ORDER

    providers: list[LLMProvider] = []
    for key in order:
        spec = _SPECS.get(key)
        if spec is None:
            continue
        api_key = os.getenv(spec.api_key_env)
        if not api_key:
            continue
        model = os.getenv(spec.model_env) or spec.default_model
        providers.append(LLMProvider(spec, api_key, model))
    return providers


PROVIDERS: list[LLMProvider] = _build_providers()


class AllProvidersExhausted(Exception):
    """Денний бюджет усіх провайдерів вичерпано — до скидання обробляти нема чим."""


class AllProvidersBusy(Exception):
    """Усі провайдери тимчасово недоступні (429/помилка). Варто зачекати й повторити."""

    def __init__(self, retry_after: float, last_error: Exception | None = None):
        super().__init__(f"усі LLM-провайдери зайняті, повтор за {retry_after:.1f}s: {last_error}")
        self.retry_after = retry_after
        self.last_error = last_error


def any_available(estimated_tokens: int = 850) -> bool:
    """Чи є хоч один провайдер із невичерпаним денним бюджетом."""
    return any(not p.budget.is_exhausted(estimated_tokens) for p in PROVIDERS)


def budget_summary() -> str:
    if not PROVIDERS:
        return "немає активних LLM-провайдерів"
    return " | ".join(p.budget.summary for p in PROVIDERS)


def provider_names() -> list[str]:
    return [p.name for p in PROVIDERS]


def cascade_summary() -> str:
    """Каскад із моделями: 'cerebras=gpt-oss-120b → groq=meta-llama/...'."""
    if not PROVIDERS:
        return "НЕМАЄ ПРОВАЙДЕРІВ (немає API-ключів)"
    return " → ".join(f"{p.name}={p.model}" for p in PROVIDERS)


async def complete(
    messages: list[dict],
    *,
    temperature: float = 0,
    response_format: dict | None = None,
) -> tuple[str, str, str]:
    """
    Каскадний chat-completion. Повертає (text, provider_name, model).

    Кидає:
        AllProvidersExhausted — денні бюджети всіх провайдерів вичерпані;
        AllProvidersBusy      — усі тимчасово 429/помилка (з retry_after);
        RuntimeError          — не налаштовано жодного провайдера.
    """
    if not PROVIDERS:
        raise RuntimeError(
            "Не налаштовано жодного LLM-провайдера: задай хоча б один API-ключ "
            "(CEREBRAS_API_KEY / GROQ_API_KEY / GEMINI_API_KEY / MISTRAL_API_KEY) у .env"
        )

    if response_format is None:
        response_format = {"type": "json_object"}

    last_error: Exception | None = None
    saw_budget = False        # хоч один провайдер ще має денний бюджет
    cooldowns: list[float] = []  # залишки кулдаунів провайдерів із бюджетом

    for p in PROVIDERS:
        if p.budget.is_exhausted():
            continue
        saw_budget = True

        left = p.cooldown_left()
        if left > 0:                          # провайдер холоне після 429 — пропускаємо
            cooldowns.append(left)
            continue

        await p.rate_limiter.acquire()
        if p.budget.is_exhausted() or p.cooldown_left() > 0:
            continue

        try:
            completion = await p.client.chat.completions.create(
                messages=messages,
                model=p.model,
                temperature=temperature,
                response_format=response_format,
                extra_body=p.extra_body,
            )
        except Exception as e:
            last_error = e
            msg = str(e)
            if "429" in msg or "rate_limit" in msg.lower():
                wait = _parse_retry_after(e)
                p.trip_cooldown(wait)         # позначаємо для ВСІХ паралельних задач
                cooldowns.append(wait)
                print(f"   ↪️ {p.name}: rate-limit, кулдаун {wait:.0f}s")
            else:
                p.trip_cooldown(15.0)         # тимчасовий збій — короткий кулдаун
                cooldowns.append(15.0)
                print(f"   ↪️ {p.name} відмовив ({msg[:80]}), кулдаун 15s")
            continue

        await p.budget.record(completion.usage.total_tokens if completion.usage else 850)

        text = completion.choices[0].message.content
        if not text:
            last_error = ValueError(f"{p.name}: порожня відповідь")
            continue
        return text, p.name, p.model

    if not saw_budget:
        raise AllProvidersExhausted(budget_summary())
    # бюджет є, але всі провайдери холонуть → чекаємо до найближчого відновлення
    retry_after = min(cooldowns) if cooldowns else (
        _parse_retry_after(last_error) if last_error else 10.0
    )
    raise AllProvidersBusy(retry_after, last_error)
