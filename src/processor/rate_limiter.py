"""
Token Bucket Rate Limiter для Groq API.

Проблема яку вирішуємо:
    Semaphore(N) контролює лише кількість одночасних запитів,
    але не контролює темп. При N=8 і 100 задачах всі 100 стартують
    майже одночасно → масові 429.

Рішення — Token Bucket:
    Відро поповнюється зі швидкістю rate_per_second токенів/сек.
    Кожен запит бере 1 токен. Якщо токенів немає — чекаємо.
    Це гарантує рівномірний потік запитів незалежно від кількості задач.

llama-4-scout-17b: TPM=30K, RPM=30
    ~1040 tokens/запит → max 28 запитів/хв по TPM
    Безпечно: 20 запитів/хв = 1 запит кожні 3 секунди
    З буфером: rate_per_second = 0.3 (1 запит / 3.3s)
"""

import asyncio
import time


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