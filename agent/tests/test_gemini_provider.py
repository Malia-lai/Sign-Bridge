import asyncio

import httpx
import pytest

from app.llm.base_provider import classify_error
from app.llm.gemini_provider import GeminiAPIError, GeminiProvider


def _transport(handler):
    return httpx.MockTransport(handler)


def test_gemini_success():
    def handler(request):
        return httpx.Response(200, json={
            "candidates": [{"content": {"parts": [{"text": '{"sentence":"hi","intent":"greeting","confidence":0.9,"alternatives":[]}'}]}}]
        })

    p = GeminiProvider(api_key="k", model="m", transport=_transport(handler))
    out = asyncio.run(p.generate("sys", "user"))
    assert "hi" in out


def test_gemini_rate_limit():
    def handler(request):
        return httpx.Response(429, text="rate")

    p = GeminiProvider(api_key="k", model="m", transport=_transport(handler), max_retries=0)
    with pytest.raises(GeminiAPIError) as ei:
        asyncio.run(p.generate("sys", "user"))
    assert ei.value.status_code == 429
    assert classify_error(ei.value) == "rate_limit"


def test_gemini_auth_error():
    def handler(request):
        return httpx.Response(401, text="auth")

    p = GeminiProvider(api_key="k", model="m", transport=_transport(handler), max_retries=0)
    with pytest.raises(GeminiAPIError) as ei:
        asyncio.run(p.generate("sys", "user"))
    assert classify_error(ei.value) == "auth_error"


def test_gemini_timeout():
    def handler(request):
        raise httpx.TimeoutException("timed out")

    p = GeminiProvider(api_key="k", model="m", transport=_transport(handler), max_retries=0)
    with pytest.raises(Exception) as ei:
        asyncio.run(p.generate("sys", "user"))
    assert classify_error(ei.value) == "timeout"


def test_gemini_sync_success():
    def handler(request):
        return httpx.Response(200, json={
            "candidates": [{"content": {"parts": [{"text": "ok"}]}}]
        })

    p = GeminiProvider(api_key="k", model="m", transport=_transport(handler))
    assert p.generate_sync("sys", "user") == "ok"


def test_gemini_missing_key():
    p = GeminiProvider(api_key="", model="m", max_retries=0)
    with pytest.raises(GeminiAPIError) as ei:
        asyncio.run(p.generate("sys", "user"))
    assert ei.value.status_code == 401