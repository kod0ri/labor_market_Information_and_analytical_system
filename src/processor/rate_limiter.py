"""
Token Bucket Rate Limiter + DailyBudget для безкоштовних LLM-провайдерів.

DailyBudget відстежує денні ліміти (TPD — tokens/day, RPD — requests/day)
конкретного провайдера й зупиняє обробку до того, як пайплайн почне масово
отримувати 429. Кожен провайдер у каскаді (див. llm_cascade.py) має власний
екземпляр DailyBudget зі своїми лімітами.
"""

import asyncio
import time


class DailyBudget:
    """
    Відстежує денні ліміти одного LLM-провайдера (TPD + RPD).

    Зупиняє обробку при `stop_ratio` (типово 96%) від ліміту, щоб уникнути
    хвилі 429 у кінці доби. Спільний екземпляр на провайдера — і nlp_vacancies,
    і nlp_resumes рахують у той самий бюджет через каскад.
    """

    def __init__(
        self,
        name: str,
        tpd_limit: int,
        rpd_limit: int,
        stop_ratio: float = 0.96,
    ):
        self.name = name
        self.tpd_limit = tpd_limit
        self.rpd_limit = rpd_limit
        self._tpd_stop_at = int(tpd_limit * stop_ratio)
        self._rpd_stop_at = int(rpd_limit * stop_ratio)
        self._tokens = 0
        self._requests = 0
        self._lock = asyncio.Lock()

    async def record(self, total_tokens: int) -> None:
        async with self._lock:
            self._tokens += total_tokens
            self._requests += 1

    def is_exhausted(self, estimated_tokens: int = 850) -> bool:
        """Перевіряє чи безпечно робити ще один запит (без Lock — читання stale ок)."""
        return (
            self._tokens + estimated_tokens >= self._tpd_stop_at
            or self._requests >= self._rpd_stop_at
        )

    @property
    def summary(self) -> str:
        return (
            f"{self.name}: {self._tokens:,}/{self.tpd_limit:,} tok "
            f"| {self._requests}/{self.rpd_limit:,} req"
        )


class TokenBucketRateLimiter:
    """
    Асинхронний Token Bucket Rate Limiter.

    Args:
        rate_per_second: Скільки запитів дозволено за секунду.
                         0.3 = 1 запит кожні ~3.3 секунди = 18 запитів/хвилину.
        burst:           Максимальна кількість токенів (burst capacity).
                         Дозволяє невеликий сплеск на початку.
    """

    def __init__(self, rate_per_second: float = 0.3, burst: int = 3):
        self.rate = rate_per_second
        self.burst = burst
        self._tokens = float(burst)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Чекає поки є доступний токен і забирає його."""
        while True:
            async with self._lock:
                now = time.monotonic()
                elapsed = now - self._last_refill
                self._tokens = min(
                    self.burst,
                    self._tokens + elapsed * self.rate
                )
                self._last_refill = now

                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return

                # Рахуємо скільки чекати до наступного токену
                wait_time = (1.0 - self._tokens) / self.rate

            # Чекаємо ПОЗА локом — інші задачі можуть перевіряти
            await asyncio.sleep(wait_time)