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
    Groq      gpt-oss-120b               200K токенів/добу, 1K запитів/добу
    Gemini    gemini-3.1-flash-lite      500 запитів/добу free tier (RPD б'є; 2.5-flash лише 20)
    Mistral   mistral-small-latest       1 млрд ток/МІСЯЦЬ (Experiment, 1 req/s)
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
    """Статичний опис одного LLM-провайдера каскаду (не залежить від .env-ключа)."""

    name: str                # ключ у _SPECS/DEFAULT_ORDER, теж людський лейбл у логах
    base_url: str            # OpenAI-сумісний ендпоінт провайдера
    api_key_env: str         # ім'я змінної оточення з ключем (наявність = провайдер активний)
    model_env: str           # опційне перевизначення моделі через .env
    default_model: str       # модель, якщо model_env не задано
    tpd_limit: int           # денний ліміт токенів (для request-bound провайдерів — завищений)
    rpd_limit: int           # денний ліміт запитів (для token-bound провайдерів — завищений)
    rate_per_second: float   # пейсинг під RPM провайдера (із запасом, щоб не ловити 429)
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
        # llama-4-scout вивели з експлуатації (404 model_not_found);
        # gpt-oss-120b — та сама модель, що й у Cerebras → консистентний вихід.
        default_model="openai/gpt-oss-120b",
        tpd_limit=200_000,        # реальна стеля free-tier для gpt-oss-120b
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
        tpd_limit=50_000_000,     # non-binding (gemini ріже по запитах, не по токенах)
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

# Порядок каскаду за замовчуванням: від найщедрішого безкоштовного ліміту (Cerebras)
# до найскромнішого (Mistral) — так найбільше запитів обробляється найдешевшим шляхом.
DEFAULT_ORDER = ["cerebras", "groq", "gemini", "mistral"]


class LLMProvider:
    """Один провайдер каскаду: клієнт + модель + власний rate-limiter і бюджет."""

    def __init__(self, spec: _ProviderSpec, api_key: str, model: str):
        self.name = spec.name    # людський ключ провайдера ("cerebras" тощо), для логів/summary
        self.model = model       # фактична модель (з .env або default_model зі spec)
        self.client = AsyncOpenAI(api_key=api_key, base_url=spec.base_url)  # один клієнт на весь процес
        # burst=1: жодного сплеску на старті — перший запит теж чекає на токен,
        # так каскад одразу поводиться передбачувано під реальний RPM провайдера.
        self.rate_limiter = TokenBucketRateLimiter(
            rate_per_second=spec.rate_per_second, burst=1
        )
        self.budget = DailyBudget(spec.name, spec.tpd_limit, spec.rpd_limit)
        self.extra_body = dict(spec.extra_body)
        # Спільний на процес «холодильник»: після 429 провайдер пропускається
        # всіма паралельними задачами до цього моменту (monotonic time).
        self.cooldown_until = 0.0
        # Постійне вимкнення до кінця процесу: модель не існує (404) чи
        # невалідний ключ — повторні спроби безглузді, лише палять час каскаду.
        self.disabled = False

    def cooldown_left(self) -> float:
        """Скільки секунд лишилось до кінця кулдауну (0, якщо кулдауну нема)."""
        return max(0.0, self.cooldown_until - time.monotonic())

    def trip_cooldown(self, seconds: float) -> None:
        """Вмикає кулдаун на `seconds` секунд від поточного моменту (monotonic)."""
        self.cooldown_until = time.monotonic() + seconds


def _build_providers() -> list[LLMProvider]:
    """Збирає каскад із .env: порядок з LLM_PROVIDER_ORDER або DEFAULT_ORDER,
    активує лише провайдерів із заданим API-ключем."""
    order_env = os.getenv("LLM_PROVIDER_ORDER", "")   # напр. "cerebras,groq,gemini,mistral" з .env
    # розбиваємо по комі, обрізаємо пробіли, у нижній регістр; порожній рядок → DEFAULT_ORDER
    order = [p.strip().lower() for p in order_env.split(",") if p.strip()] or DEFAULT_ORDER

    providers: list[LLMProvider] = []   # сюди складаємо готові до роботи об'єкти LLMProvider
    for key in order:                   # проходимо ключі в ЗАДАНОМУ порядку пріоритету
        spec = _SPECS.get(key)          # статичний опис цього провайдера (URL/ліміти/модель)
        if spec is None:
            # невідома назва в LLM_PROVIDER_ORDER — тихо пропускаємо, а не падаємо,
            # щоб одруківка в .env не заблокувала весь пайплайн
            continue
        api_key = os.getenv(spec.api_key_env)   # читаємо реальний ключ із оточення за іменем змінної
        if not api_key:
            # немає ключа — провайдер просто не бере участі в каскаді цього запуску
            continue
        model = os.getenv(spec.model_env) or spec.default_model  # перевизначення моделі, якщо задане
        providers.append(LLMProvider(spec, api_key, model))       # створюємо робочий екземпляр і додаємо в список
    return providers


# Будується один раз при імпорті модуля — спільний список на весь процес,
# тому rate_limiter/budget/cooldown кожного провайдера справді спільні
# для всіх паралельних задач (nlp_vacancies + nlp_resumes рахують в один бюджет).
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
    """Чи є хоч один увімкнений провайдер із невичерпаним денним бюджетом.

    Не враховує кулдаун (той тимчасовий і мине сам) — лише "постійні" причини
    (disabled) і денний бюджет. Викликається на початку кожного батчу/запису,
    щоб не ганяти цикл повторів даремно, коли реально нічого не лишилось.
    """
    return any(
        not p.disabled and not p.budget.is_exhausted(estimated_tokens)
        for p in PROVIDERS
    )


def budget_summary() -> str:
    """Людський рядок для логів: стан токен/запитового бюджету кожного провайдера."""
    if not PROVIDERS:
        return "немає активних LLM-провайдерів"
    return " | ".join(p.budget.summary for p in PROVIDERS)


def provider_names() -> list[str]:
    """Імена активних провайдерів каскаду (для діагностики/метрик адмінки)."""
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
    if not PROVIDERS:                 # список зібраний один раз на імпорті - якщо порожній, ключів нема взагалі
        raise RuntimeError(
            "Не налаштовано жодного LLM-провайдера: задай хоча б один API-ключ "
            "(CEREBRAS_API_KEY / GROQ_API_KEY / GEMINI_API_KEY / MISTRAL_API_KEY) у .env"
        )

    if response_format is None:                       # викликач може передати свій формат
        response_format = {"type": "json_object"}     # дефолт - строгий JSON-режим OpenAI API

    last_error: Exception | None = None   # запам'ятовуємо ОСТАННЮ помилку, щоб повідомити її, якщо всі впадуть
    saw_budget = False        # хоч один провайдер ще має денний бюджет
    cooldowns: list[float] = []  # залишки кулдаунів провайдерів із бюджетом

    for p in PROVIDERS:   # ідемо по каскаду СУВОРО за пріоритетом (порядок зі списку PROVIDERS)
        # Постійно вимкнений (404/401) чи денний бюджет вичерпаний — пропускаємо
        # без жодних побічних ефектів, одразу до наступного провайдера каскаду.
        if p.disabled or p.budget.is_exhausted():
            continue
        saw_budget = True   # цей провайдер теоретично міг би обробити запит - бюджет ще є

        left = p.cooldown_left()   # скільки секунд лишилось цьому провайдеру "охолоджуватись" після 429
        if left > 0:                          # провайдер холоне після 429 — пропускаємо
            cooldowns.append(left)            # запам'ятовуємо залишок, знадобиться для retry_after у виключенні
            continue

        # acquire() може чекати (rate limit) — за час очікування інша паралельна
        # задача могла вичерпати бюджет чи спровокувати кулдаун цього ж провайдера,
        # тому перевіряємо обидва прапорці ЩЕ РАЗ одразу після пробудження.
        await p.rate_limiter.acquire()
        if p.budget.is_exhausted() or p.cooldown_left() > 0:
            continue

        try:
            completion = await p.client.chat.completions.create(
                messages=messages,             # діалог (system+user) від викликача
                model=p.model,                 # конкретна модель ЦЬОГО провайдера
                temperature=temperature,        # 0 за замовчуванням - максимально детермінований вивід
                response_format=response_format,  # {"type":"json_object"} - вимагаємо валідний JSON
                extra_body=p.extra_body,        # провайдер-специфічні поля (напр. reasoning_effort)
            )
        except Exception as e:
            last_error = e            # запам'ятовуємо для повідомлення, якщо весь каскад впаде
            msg = str(e)               # текст помилки як рядок - для пошуку підрядків нижче
            low = msg.lower()          # регістронезалежна версія для порівнянь
            if "429" in msg or "rate_limit" in low:   # ознаки rate-limit помилки в тексті винятку
                wait = _parse_retry_after(e)  # намагаємось витягти точний час очікування з тексту помилки
                p.trip_cooldown(wait)         # позначаємо для ВСІХ паралельних задач
                cooldowns.append(wait)
                print(f"   ↪️ {p.name}: rate-limit, кулдаун {wait:.0f}s")
            elif (
                "model_not_found" in low
                or "does not exist" in low
                or getattr(e, "status_code", None) in (401, 404)
            ):
                # Модель знята з експлуатації чи ключ невалідний: до кінця
                # запуску нічого не зміниться — вимикаємо, каскад іде далі.
                p.disabled = True
                print(f"   ⛔ {p.name} вимкнено до кінця запуску: {msg[:100]}")
            else:
                # Невідома тимчасова помилка (мережа, 5xx тощо) — короткий
                # кулдаун замість негайного повторного удару по тому самому провайдеру.
                p.trip_cooldown(15.0)
                cooldowns.append(15.0)
                print(f"   ↪️ {p.name} відмовив ({msg[:80]}), кулдаун 15s")
            continue

        # Успіх — рахуємо реальне споживання токенів у денний бюджет провайдера
        # (а не оцінку estimated_tokens, яка використовується лише для передчасної перевірки).
        await p.budget.record(completion.usage.total_tokens if completion.usage else 850)

        text = completion.choices[0].message.content   # перший (єдиний очікуваний) варіант відповіді моделі
        if not text:
            # Порожня відповідь — не помилка HTTP, але й не валідний результат;
            # пробуємо наступного провайдера каскаду замість негайного падіння.
            last_error = ValueError(f"{p.name}: порожня відповідь")
            continue
        return text, p.name, p.model

    # Жоден провайдер не дав результату — розрізняємо дві принципово різні причини,
    # бо викликач (run_llm_record) реагує на них по-різному (пропустити назавжди
    # проти зачекати й повторити).
    if not saw_budget:                                  # НІ ОДИН провайдер навіть не мав бюджету спробувати
        raise AllProvidersExhausted(budget_summary())
    # бюджет є, але всі провайдери холонуть → чекаємо до найближчого відновлення
    retry_after = min(cooldowns) if cooldowns else (    # чекаємо стільки, скільки НАЙШВИДШИЙ провайдер розхолодиться
        _parse_retry_after(last_error) if last_error else 10.0   # фолбек, якщо чомусь список кулдаунів порожній
    )
    raise AllProvidersBusy(retry_after, last_error)
