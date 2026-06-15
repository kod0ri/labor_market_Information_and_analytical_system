import time

from src.processor.rate_limiter import DailyBudget, TokenBucketRateLimiter


async def test_daily_budget_token_threshold():
    b = DailyBudget("x", tpd_limit=100_000, rpd_limit=1_000_000)  # stop @ 96_000 ток
    assert not b.is_exhausted()
    await b.record(95_000)
    assert not b.is_exhausted()          # 95_000 + 850 < 96_000
    await b.record(1_000)
    assert b.is_exhausted()              # 96_000 + 850 >= 96_000


async def test_daily_budget_request_threshold():
    b = DailyBudget("x", tpd_limit=10_000_000, rpd_limit=10)  # stop @ 9 запитів
    for _ in range(8):
        await b.record(1)
    assert not b.is_exhausted()
    await b.record(1)                    # 9-й запит
    assert b.is_exhausted()


async def test_daily_budget_summary_format():
    b = DailyBudget("groq", tpd_limit=500_000, rpd_limit=1_000)
    await b.record(100)
    s = b.summary
    assert "groq" in s
    assert "500,000" in s and "1,000" in s
    assert "100" in s


async def test_token_bucket_throttles_after_burst():
    rl = TokenBucketRateLimiter(rate_per_second=100, burst=1)  # ~10ms/токен
    t0 = time.monotonic()
    await rl.acquire()                   # burst-токен — миттєво
    await rl.acquire()                   # має зачекати ~10ms
    assert time.monotonic() - t0 >= 0.005
