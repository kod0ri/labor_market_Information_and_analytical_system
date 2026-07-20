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
        self.name = name              # ключ провайдера ("cerebras"/"groq"/...), лише для логів
        self.tpd_limit = tpd_limit    # заявлений денний ліміт ТОКЕНІВ (tokens per day)
        self.rpd_limit = rpd_limit    # заявлений денний ліміт ЗАПИТІВ (requests per day)
        # Заздалегідь порахований поріг зупинки — не 100% ліміту, а 96%, щоб
        # лишити запас на неточність оцінки токенів наступного запиту.
        self._tpd_stop_at = int(tpd_limit * stop_ratio)   # фактична стеля токенів для is_exhausted()
        self._rpd_stop_at = int(rpd_limit * stop_ratio)   # фактична стеля запитів для is_exhausted()
        self._tokens = 0     # скільки токенів вже витрачено за поточну добу (лічильник, не бюджет)
        self._requests = 0   # скільки запитів вже виконано за поточну добу
        # Lock лише навколо запису (record) — читання (is_exhausted) свідомо
        # без локу, див. коментар нижче.
        self._lock = asyncio.Lock()

    async def record(self, total_tokens: int) -> None:
        """Фіксує реальне споживання одного успішного запиту (токени + +1 запит)."""
        async with self._lock:            # блокуємо на час запису - лише один writer одночасно
            self._tokens += total_tokens  # додаємо реальну кількість токенів цього запиту
            self._requests += 1           # +1 до лічильника виконаних запитів

    def is_exhausted(self, estimated_tokens: int = 850) -> bool:
        """Перевіряє чи безпечно робити ще один запит (без Lock — читання stale ок).

        `estimated_tokens` — консервативна оцінка витрати ще НЕ виконаного запиту:
        рахуємо "а що як він теж витратить стільки" ще ДО виклику, щоб не
        проскочити стелю на останньому дозволеному запиті.
        """
        return (
            self._tokens + estimated_tokens >= self._tpd_stop_at   # токенів вже + оцінка нового >= стелі?
            or self._requests >= self._rpd_stop_at                 # чи вичерпано ліміт КІЛЬКОСТІ запитів?
        )

    @property
    def summary(self) -> str:
        """Короткий рядок стану для логів/адмінки: 'ім'я: токени/ліміт | запити/ліміт'."""
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
        self.rate = rate_per_second   # швидкість поповнення бачка, токенів/секунду
        self.burst = burst            # ємність бачка = макс. кількість запитів "про запас"
        # Стартуємо з повним бачком (=burst) — перший виклик(и) проходять
        # одразу, без штучного очікування на порожньому лічильнику.
        self._tokens = float(burst)          # поточна кількість токенів у бачку (дробове число)
        self._last_refill = time.monotonic()  # мітка часу останнього перерахунку (не календарний час!)
        self._lock = asyncio.Lock()           # захищає _tokens/_last_refill від одночасного читання/запису

    async def acquire(self) -> None:
        """Чекає поки є доступний токен і забирає його (блокує викликача до готовності)."""
        while True:                     # повторюємо, поки реально не заберемо токен
            async with self._lock:      # ексклюзивний доступ до стану бачка на час перерахунку
                # Поповнюємо бачок пропорційно часу, що минув відколи востаннє
                # рахували (класичний token bucket, без окремого фонового таймера).
                now = time.monotonic()             # поточний момент (монотонний, не збивається переводом часу)
                elapsed = now - self._last_refill  # скільки секунд минуло з попереднього перерахунку
                self._tokens = min(
                    self.burst,                     # не даємо бачку переповнитись понад ємність
                    self._tokens + elapsed * self.rate,  # додаємо "напоєні" за elapsed секунд токени
                )
                self._last_refill = now   # запам'ятовуємо момент цього перерахунку для наступного разу

                if self._tokens >= 1.0:   # чи є хоча б один цілий токен прямо зараз?
                    self._tokens -= 1.0   # забираємо токен собі
                    return                # і одразу віддаємо керування викликачу - можна робити запит

                # Рахуємо скільки чекати до наступного токену
                wait_time = (1.0 - self._tokens) / self.rate   # бракує (1.0-tokens) токена, ділимо на швидкість поповнення

            # Чекаємо ПОЗА локом — інші задачі можуть перевіряти й поповнювати
            # бачок паралельно, поки ця корутина спить; після пробудження цикл
            # `while True` перераховує стан заново (могли перехопити токен раніше нас).
            await asyncio.sleep(wait_time)
