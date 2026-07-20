"""
Rate limiting по IP клієнта (sliding window, in-memory).

Розраховано на один процес uvicorn (поточна конфігурація). За кількох воркерів
чи реплік ліміт став би локальним для кожного — тоді потрібен спільний стор
(напр. Redis). Стан тримається в памʼяті, перевірка синхронна й виконується
в event-loop без await між читанням і записом, тож блокування не потрібні.

Визначення IP за реверс-проксі:
    X-Forwarded-For — це список, до якого КОЖЕН проксі дописує IP свого
    безпосереднього клієнта СПРАВА. Тому довіряти можна лише хвостовим
    елементам, які додали НАШІ проксі; усе, що зліва, підконтрольне клієнту.
    TRUSTED_PROXY_HOPS = скільки проксі стоять перед застосунком (Caddy+nginx=2).
    Справжній IP клієнта = елемент на позиції -TRUSTED_PROXY_HOPS.

    cf-connecting-ip НЕ використовується за замовчуванням: якщо перед нами не
    справжній Cloudflare (який перезаписує цей заголовок), його може підробити
    будь-який клієнт і повністю контролювати ключ лімітера. Увімкнути можна лише
    свідомо через TRUST_CF_CONNECTING_IP=1 (коли трафік реально йде через CF).
"""

import os
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

# Якщо унікальних IP стало більше — примусово підчищаємо застарілі ключі,
# щоб памʼять не росла безмежно під розподіленим навантаженням.
_SWEEP_KEYS_THRESHOLD = 10_000

# Скільки довірених проксі стоять перед застосунком. Кожен дописує один IP
# у хвіст X-Forwarded-For. За замовчуванням 1 (лише локальний nginx); за схеми
# Caddy → nginx постав 2. Значення 0 — ігнорувати XFF (брати peer-адресу).
_TRUSTED_PROXY_HOPS = int(os.getenv("TRUSTED_PROXY_HOPS", "1"))
_TRUST_CF_HEADER = os.getenv("TRUST_CF_CONNECTING_IP", "").strip().lower() in ("1", "true", "yes")


def get_client_ip(request: Request) -> str:
    """Резолвить справжню IP-адресу клієнта з урахуванням довірених проксі
    (див. докладний розбір загрози підробки XFF/CF-заголовків у docstring модуля)."""
    if _TRUST_CF_HEADER:                                    # свідомо увімкнено ЛИШЕ якщо трафік реально йде через CF
        cf = request.headers.get("cf-connecting-ip")
        if cf:
            return cf.strip()

    if _TRUSTED_PROXY_HOPS > 0:
        xff = request.headers.get("x-forwarded-for")
        if xff:
            parts = [p.strip() for p in xff.split(",") if p.strip()]   # "ip1, ip2, ip3" → ["ip1","ip2","ip3"]
            # Беремо IP, доданий найдальшим ДОВІРЕНИМ проксі (рахунок справа).
            # Клієнт може дописати сміття зліва — воно не впливає на цю позицію.
            if len(parts) >= _TRUSTED_PROXY_HOPS:
                return parts[-_TRUSTED_PROXY_HOPS]    # напр. hops=2 → передостанній елемент списку

    return request.client.host if request.client else "unknown"   # фолбек - пряме TCP-з'єднання без проксі


class SlidingWindowRateLimiter:
    """Sliding-window лічильник запитів на ключ (зазвичай - IP клієнта).

    Кожен ключ тримає deque монотонних часових міток своїх запитів; вікно
    "ковзає" - застарілі мітки зліва відкидаються при кожній перевірці,
    тому немає фіксованих "reset" моментів на кшталт fixed-window лічильника.
    """

    def __init__(self, limit: int, window_seconds: float) -> None:
        self.limit = limit                 # макс. дозволена кількість запитів у вікні
        self.window = window_seconds       # довжина ковзного вікна в секундах
        self._hits: dict[str, deque[float]] = defaultdict(deque)   # ключ (IP) → черга часових міток його запитів
        self._last_sweep = time.monotonic()  # коли востаннє чистили застарілі ключі (для троттлінгу _sweep)

    def _sweep(self, now: float) -> None:
        """Прибирає ключі, чий останній хіт уже застарів - без цього словник
        `_hits` ріс би необмежено під потоком запитів від різних IP."""
        cutoff = now - self.window                    # усе старіше цього моменту вважаємо неактивним
        stale = [k for k, dq in self._hits.items() if not dq or dq[-1] <= cutoff]  # ключі без свіжих запитів
        for k in stale:
            del self._hits[k]
        self._last_sweep = now

    def check(self, key: str) -> tuple[bool, int]:
        """Повертає (дозволено, retry_after_seconds)."""
        now = time.monotonic()
        dq = self._hits[key]           # черга міток цього конкретного ключа (створюється автоматично, defaultdict)
        cutoff = now - self.window
        while dq and dq[0] <= cutoff:   # прибираємо із ЛІВОГО краю всі мітки, що вже випали з вікна
            dq.popleft()

        if len(dq) >= self.limit:                                     # ліміт вичерпано в поточному вікні
            retry_after = max(1, int(dq[0] + self.window - now) + 1)  # скільки чекати, поки НАЙСТАРІША мітка випаде з вікна
            return False, retry_after

        dq.append(now)     # реєструємо цей запит як новий хіт
        if now - self._last_sweep > self.window or len(self._hits) > _SWEEP_KEYS_THRESHOLD:
            self._sweep(now)     # періодичне прибирання: не на кожен виклик, а раз на вікно або при рості словника
        return True, 0


def rate_limiter(limit: int, window_seconds: float = 60.0):
    """
    Створює FastAPI-залежність, що обмежує запити по IP до `limit` за вікно.
    Лімітер створюється один раз (на декоруванні роуту) і спільний для всіх
    запитів цього ендпоінта.
    """
    limiter = SlidingWindowRateLimiter(limit, window_seconds)   # створюється РАЗ при імпорті роуту, не на кожен запит

    async def dependency(request: Request) -> None:
        allowed, retry_after = limiter.check(get_client_ip(request))   # IP клієнта - ключ лічильника
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail="Забагато запитів. Спробуйте пізніше.",
                headers={"Retry-After": str(retry_after)},
            )

    return dependency
