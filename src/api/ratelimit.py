"""
Rate limiting по IP клієнта (sliding window, in-memory).

Розраховано на один процес uvicorn (поточна конфігурація). За кількох воркерів
чи реплік ліміт став би локальним для кожного — тоді потрібен спільний стор
(напр. Redis). Стан тримається в памʼяті, перевірка синхронна й виконується
в event-loop без await між читанням і записом, тож блокування не потрібні.

За реверс-проксі (Cloudflare → nginx) справжній IP береться із заголовків.
Origin слухає лише локально (127.0.0.1:8000), тож ці заголовки ставить наш
проксі, а не довільний клієнт.
"""

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

# Якщо унікальних IP стало більше — примусово підчищаємо застарілі ключі,
# щоб памʼять не росла безмежно під розподіленим навантаженням.
_SWEEP_KEYS_THRESHOLD = 10_000


def get_client_ip(request: Request) -> str:
    cf = request.headers.get("cf-connecting-ip")
    if cf:
        return cf.strip()
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class SlidingWindowRateLimiter:
    def __init__(self, limit: int, window_seconds: float) -> None:
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._last_sweep = time.monotonic()

    def _sweep(self, now: float) -> None:
        cutoff = now - self.window
        stale = [k for k, dq in self._hits.items() if not dq or dq[-1] <= cutoff]
        for k in stale:
            del self._hits[k]
        self._last_sweep = now

    def check(self, key: str) -> tuple[bool, int]:
        """Повертає (дозволено, retry_after_seconds)."""
        now = time.monotonic()
        dq = self._hits[key]
        cutoff = now - self.window
        while dq and dq[0] <= cutoff:
            dq.popleft()

        if len(dq) >= self.limit:
            retry_after = max(1, int(dq[0] + self.window - now) + 1)
            return False, retry_after

        dq.append(now)
        if now - self._last_sweep > self.window or len(self._hits) > _SWEEP_KEYS_THRESHOLD:
            self._sweep(now)
        return True, 0


def rate_limiter(limit: int, window_seconds: float = 60.0):
    """
    Створює FastAPI-залежність, що обмежує запити по IP до `limit` за вікно.
    Лімітер створюється один раз (на декоруванні роуту) і спільний для всіх
    запитів цього ендпоінта.
    """
    limiter = SlidingWindowRateLimiter(limit, window_seconds)

    async def dependency(request: Request) -> None:
        allowed, retry_after = limiter.check(get_client_ip(request))
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail="Забагато запитів. Спробуйте пізніше.",
                headers={"Retry-After": str(retry_after)},
            )

    return dependency
