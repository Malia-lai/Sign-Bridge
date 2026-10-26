import asyncio
import json
from types import SimpleNamespace

from app.core.agent import Agent
from app.core.fallback import build_fallback, detect_emergency
from app.llm.base_provider import classify_error
from app.llm.mistral_provider import MistralProvider


def test_fallback_raw_words():
    fb = build_fallback(["me", "water", "want"])
    assert fb.sentence == "me water want"
    assert fb.fallback is True
    assert fb.confidence < 0.5
    assert fb.fallback_reason is None


def test_fallback_empty():
    fb = build_fallback([])
    assert fb.sentence == ""
    assert fb.fallback is True


def test_fallback_reasons(monkeypatch):

    class RateLimitError(Exception):
        status_code = 429

    class AuthError(Exception):
        status_code = 401

    cases = {
        "rate_limit": RateLimitError("rate"),
        "auth_error": AuthError("auth"),
        "timeout": asyncio.TimeoutError(),
        "invalid_json": json.JSONDecodeError("bad", "x", 0),
        "other": RuntimeError("boom"),
    }

    for expected, exc in cases.items():

        class BadClient:
            async def generate_json(self, *a, **k):
                raise exc

            async def generate(self, *a, **k):
                raise exc

        agent = Agent(mock_mode=False, llm_client=BadClient())
        result = asyncio.run(agent.process(["me", "water", "want"]))
        assert result.fallback is True
        assert result.fallback_reason == expected, (expected, result.fallback_reason)


def test_emergency_fallback():
    class BadClient:
        async def generate(self, *args, **kwargs):
            raise RuntimeError("simulated provider failure")

    agent = Agent(mock_mode=False, llm_client=BadClient())
    result = asyncio.run(agent.process(["help", "me"]))
    assert result.intent == "emergency"
    assert result.fallback is True
    assert result.emergency is True
    assert "emergency" in (result.fallback_reasons or [])
    assert detect_emergency(["help"], agent.vocabulary) is True


def test_retry_behavior(monkeypatch):
    async def _sleep(*a, **k):
        return None

    monkeypatch.setattr(asyncio, "sleep", _sleep)
    provider = MistralProvider(api_key="test", max_retries=2)
    calls = {"n": 0}

    async def fake_complete(*a, **k):
        calls["n"] += 1
        if calls["n"] < 3:
            exc = Exception("rate")
            exc.status_code = 429
            raise exc
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content='{"sentence":"hi","intent":"greeting","confidence":0.9,"alternatives":[]}'
                    )
                )
            ]
        )

    provider.client.chat.complete_async = fake_complete
    out = asyncio.run(provider.generate("sys", "user"))
    assert "hi" in out
    assert calls["n"] == 3


def test_retry_after_header():
    exc = Exception("rate")
    exc.status_code = 429
    exc.headers = {"retry-after": "2.5"}
    provider = MistralProvider(api_key="test", max_retries=1)
    assert provider._retry_delay(exc, 0) == 2.5


def test_classify_error():
    exc = Exception("x")
    exc.status_code = 429
    assert classify_error(exc) == "rate_limit"
    exc2 = Exception("timeout happened")
    assert classify_error(exc2) == "timeout"
