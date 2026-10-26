import asyncio

import pytest

from app.llm.base_provider import classify_error
from app.llm.mistral_provider import MistralAPIError, MistralProvider


def test_mistral_success(monkeypatch):
    provider = MistralProvider(api_key="k", model="m", max_retries=0)

    async def fake_complete(*a, **k):
        return type("Resp", (), {
            "choices": [type("C", (), {"message": type("M", (), {"content": '{"sentence":"hi","intent":"greeting","confidence":0.9,"alternatives":[]}'})()})()],
            "usage": type("U", (), {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3})(),
        })()

    monkeypatch.setattr(provider.client.chat, "complete_async", fake_complete)
    out = asyncio.run(provider.generate("sys", "user"))
    assert "hi" in out
    assert provider.last_usage["total_tokens"] == 3


def test_mistral_rate_limit(monkeypatch):
    provider = MistralProvider(api_key="k", model="m", max_retries=0)

    async def fake_complete(*a, **k):
        exc = Exception("rate")
        exc.status_code = 429
        raise exc

    monkeypatch.setattr(provider.client.chat, "complete_async", fake_complete)
    with pytest.raises(Exception) as ei:
        asyncio.run(provider.generate("sys", "user"))
    assert getattr(ei.value, "status_code", None) == 429
    assert classify_error(ei.value) == "rate_limit"


def test_mistral_auth_error(monkeypatch):
    provider = MistralProvider(api_key="k", model="m", max_retries=0)

    async def fake_complete(*a, **k):
        raise MistralAPIError(401, "auth")

    monkeypatch.setattr(provider.client.chat, "complete_async", fake_complete)
    with pytest.raises(MistralAPIError) as ei:
        asyncio.run(provider.generate("sys", "user"))
    assert ei.value.status_code == 401
    assert classify_error(ei.value) == "auth_error"


def test_mistral_timeout(monkeypatch):
    provider = MistralProvider(api_key="k", model="m", max_retries=0)

    async def fake_complete(*a, **k):
        raise asyncio.TimeoutError()

    monkeypatch.setattr(provider.client.chat, "complete_async", fake_complete)
    with pytest.raises(Exception) as ei:
        asyncio.run(provider.generate("sys", "user"))
    assert classify_error(ei.value) == "timeout"


def test_mistral_sync_success(monkeypatch):
    provider = MistralProvider(api_key="k", model="m", max_retries=0)

    def fake_complete(*a, **k):
        return type("Resp", (), {
            "choices": [type("C", (), {"message": type("M", (), {"content": "ok"})()})()],
            "usage": None,
        })()

    monkeypatch.setattr(provider.client.chat, "complete", fake_complete)
    assert provider.generate_sync("sys", "user") == "ok"


def test_mistral_missing_key():
    provider = MistralProvider(api_key="", model="m", max_retries=0)
    with pytest.raises(MistralAPIError) as ei:
        asyncio.run(provider.generate("sys", "user"))
    assert ei.value.status_code == 401


def test_mistral_empty_candidates(monkeypatch):
    provider = MistralProvider(api_key="k", model="m", max_retries=0)

    async def fake_complete(*a, **k):
        return type("Resp", (), {"choices": [], "usage": None})()

    monkeypatch.setattr(provider.client.chat, "complete_async", fake_complete)
    with pytest.raises(ValueError):
        asyncio.run(provider.generate("sys", "user"))


def test_mistral_model_validation():
    with pytest.raises(ValueError):
        MistralProvider(api_key="k", model="", max_retries=0)


def test_mistral_health_check():
    provider = MistralProvider(api_key="k", model="m", max_retries=0)
    assert asyncio.run(provider.health_check()) is True