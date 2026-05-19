"""
Token Bucket Rate Limiter + GroqBudget для Groq API.

llama-4-scout-17b (free tier): RPM=30, RPD=1K, TPM=30K, TPD=500K
    ~845 tokens/запит (685 in + 160 out) → max 35 запитів/хв по TPM
    Безпечний combined rate (2 модулі паралельно): 20 запитів/хв → 0.16 req/s кожен

GroqBudget відстежує денні ліміти (TPD, RPD) і зупиняє обробку
до того як пайплайн почне масово отримувати 429.
"""

import asyncio
import time


class GroqBudget:
    """
    Shared singleton для відстеження денних лімітів Groq API.

    llama-4-scout-17b free tier: TPD=500K токенів, RPD=1K запитів.
    Обидва nlp_vacancies і nlp_resumes імпортують один екземпляр GROQ_BUDGET.
    Зупиняє обробку при 96% від ліміту щоб уникнути 429 в кінці пайплайну.
    """
    TPD_LIMIT = 500_000
    RPD_LIMIT = 1_000
    _TPD_STOP_AT = int(TPD_LIMIT * 0.96)   # 480K
    _RPD_STOP_AT = int(RPD_LIMIT * 0.96)   # 960

    def __init__(self):
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
            self._tokens + estimated_tokens >= self._TPD_STOP_AT
            or self._requests >= self._RPD_STOP_AT
        )

    @property
    def summary(self) -> str:
        return (
            f"tokens {self._tokens:,}/{self.TPD_LIMIT:,} "
            f"| requests {self._requests}/{self.RPD_LIMIT}"
        )


GROQ_BUDGET = GroqBudget()


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