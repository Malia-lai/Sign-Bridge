import asyncio
import json

import httpx
import pytest

from app.llm.gemini_provider import GeminiProvider
from app.llm.rate_limiter import SlidingWindowRateLimiter
from app.config import Settings


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def time(self):
        return self.now

    async def sleep(self, seconds):
        self.now += seconds


def test_sliding_window_enforces_token_budget_with_fake_clock():
    clock = FakeClock()
    limiter = SlidingWindowRateLimiter(
        5, 10, clock=clock.time, sleep=clock.sleep
    )

    async def run():
        await limiter.acquire(6)
        await limiter.acquire(4)
        await limiter.acquire(1)

    asyncio.run(run())
    assert clock.now == 60


def test_token_budget_default_is_14000(monkeypatch):
    monkeypatch.delenv("TOKENS_PER_MINUTE", raising=False)
    monkeypatch.delenv("REQUESTS_PER_MINUTE", raising=False)
    assert Settings().tokens_per_minute == 14000
    assert Settings().requests_per_minute == 30


def test_sliding_window_enforces_request_budget_with_fake_clock():
    clock = FakeClock()
    limiter = SlidingWindowRateLimiter(
        1, 100, clock=clock.time, sleep=clock.sleep
    )

    async def run():
        await limiter.acquire(5)
        await limiter.acquire(5)

    asyncio.run(run())
    assert clock.now == 60


def test_actual_usage_replaces_estimated_token_reservation():
    clock = FakeClock()
    limiter = SlidingWindowRateLimiter(
        5, 10, clock=clock.time, sleep=clock.sleep
    )

    async def run():
        reservation = await limiter.acquire(8)
        limiter.update(reservation, 2)
        await limiter.acquire(8)

    asyncio.run(run())
    assert clock.now == 0


@pytest.mark.parametrize(
    ("requests_per_minute", "tokens_per_minute"),
    [(1, 20), (3, 3)],
    ids=["request-budget", "token-budget"],
)
def test_retry_waits_for_both_sliding_budgets(requests_per_minute, tokens_per_minute):
    clock = FakeClock()
    limiter = SlidingWindowRateLimiter(
        requests_per_minute,
        tokens_per_minute,
        clock=clock.time,
        sleep=clock.sleep,
    )
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, text="rate limit")
        return httpx.Response(200, json={
            "candidates": [{"content": {"parts": [{"text": json.dumps({
                "sentence": "hello", "intent": "greeting", "confidence": 0.9,
                "alternatives": [],
            })}]}}],
            "usageMetadata": {
                "promptTokenCount": 2,
                "candidatesTokenCount": 1,
                "totalTokenCount": 3,
            },
        })

    provider = GeminiProvider(
        api_key="fake",
        model="fake-model",
        max_retries=1,
        max_output_tokens=2,
        transport=httpx.MockTransport(handler),
        rate_limiter=limiter,
        sleep=clock.sleep,
    )
    output = asyncio.run(provider.generate("s", "u"))

    assert json.loads(output)["sentence"] == "hello"
    assert calls == 2
    assert clock.now == 60
    assert provider.last_usage == {
        "input_tokens": 2,
        "output_tokens": 1,
        "total_tokens": 3,
    }
    assert limiter._events[-1].tokens == 3
