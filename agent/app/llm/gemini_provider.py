import asyncio
import json
import math
import time

import httpx

from app.config import settings
from app.schemas.response import LLMOutput

from .base_provider import BaseLLMProvider, classify_error
from .rate_limiter import (
    SlidingWindowRateLimiter,
    estimate_call_tokens,
    estimate_prompt_tokens,
    get_shared_limiter,
)


class GeminiAPIError(Exception):
    def __init__(self, status_code, message=""):
        super().__init__(message)
        self.status_code = status_code


class GeminiProvider(BaseLLMProvider):
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(
        self,
        api_key=None,
        model=None,
        timeout=None,
        max_retries=None,
        transport=None,
        temperature=None,
        rate_limiter: SlidingWindowRateLimiter | None = None,
        max_output_tokens=None,
        sleep=asyncio.sleep,
        sync_sleep=time.sleep,
    ):
        self.api_key = api_key if api_key is not None else settings.gemini_api_key
        self.model = model if model is not None else settings.gemini_model
        if not self.model or not isinstance(self.model, str) or not self.model.strip():
            raise ValueError("model name must be a non-empty string")
        self.model = self.model.strip()
        self.timeout = timeout if timeout is not None else settings.timeout
        self.max_retries = settings.max_retries if max_retries is None else int(max_retries)
        self.temperature = settings.temperature if temperature is None else float(temperature)
        self.max_output_tokens = settings.max_output_tokens if max_output_tokens is None else int(max_output_tokens)
        self.rate_limiter = rate_limiter or get_shared_limiter(
            settings.requests_per_minute, settings.tokens_per_minute
        )
        self.sleep = sleep
        self.sync_sleep = sync_sleep
        self.transport = transport
        self._async_client = httpx.AsyncClient(transport=transport, timeout=self.timeout)
        self._sync_client = httpx.Client(transport=transport, timeout=self.timeout)
        self.last_retry_count = 0
        self.last_usage = {"input_tokens": 0, "output_tokens": 0}

    @staticmethod
    def estimate_tokens(system_prompt, user_prompt, max_output_tokens=None):
        output_tokens = settings.max_output_tokens if max_output_tokens is None else max_output_tokens
        return estimate_call_tokens(system_prompt, user_prompt, output_tokens)

    def _retry_delay(self, exc, attempt):
        return float(2 ** attempt)

    def _is_retryable(self, exc):
        status = getattr(exc, "status_code", None)
        if status == 429:
            return True
        if isinstance(exc, (TimeoutError,)):
            return True
        name = type(exc).__name__.lower()
        text = str(exc).lower()
        if "timeout" in name or "timeout" in text:
            return True
        return False

    def _url(self):
        return f"{self.BASE_URL}/{self.model}:generateContent"

    def _body(self, system_prompt, user_prompt):
        return {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": LLMOutput.model_json_schema(),
                "temperature": self.temperature,
                "maxOutputTokens": self.max_output_tokens,
            },
        }

    async def _once(self, system_prompt, user_prompt):
        if not self.api_key:
            raise GeminiAPIError(401, "missing GEMINI_API_KEY")
        try:
            resp = await self._async_client.post(
                self._url(),
                params={"key": self.api_key},
                json=self._body(system_prompt, user_prompt),
            )
        except httpx.TimeoutException as exc:
            raise GeminiAPIError(408, "timeout") from exc
        if resp.status_code >= 400:
            raise GeminiAPIError(resp.status_code, resp.text)
        data = resp.json()
        candidates = data.get("candidates") or []
        if not candidates:
            pf = data.get("promptFeedback") or {}
            block = pf.get("blockReason")
            if block:
                raise GeminiAPIError(403, f"safety block: {block}")
            raise GeminiAPIError(400, "empty candidates")
        candidate = candidates[0]
        finish_reason = candidate.get("finishReason")
        if finish_reason in {"SAFETY", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII"}:
            raise GeminiAPIError(400, f"safety block: {finish_reason}")
        content = candidate.get("content") or {}
        parts = content.get("parts") or []
        if not parts:
            raise GeminiAPIError(400, "empty candidates")
        text = parts[0].get("text")
        if text is None:
            raise GeminiAPIError(400, "empty candidates")
        metadata = data.get("usageMetadata") or {}
        input_tokens = metadata.get("promptTokenCount", metadata.get("prompt_token_count"))
        output_tokens = metadata.get("candidatesTokenCount", metadata.get("candidates_token_count"))
        input_tokens = int(input_tokens) if input_tokens is not None else estimate_prompt_tokens(system_prompt, user_prompt)
        output_tokens = int(output_tokens) if output_tokens is not None else math.ceil(len(text) / 4)
        total_tokens = metadata.get("totalTokenCount", metadata.get("total_token_count"))
        has_actual_total = total_tokens is not None or (
            metadata.get("promptTokenCount", metadata.get("prompt_token_count")) is not None
            and metadata.get("candidatesTokenCount", metadata.get("candidates_token_count")) is not None
        )
        usage = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": int(total_tokens) if total_tokens is not None else input_tokens + output_tokens,
            "reported": has_actual_total,
        }
        return text, usage

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        last = None
        self.last_retry_count = 0
        input_estimate = estimate_prompt_tokens(system_prompt, user_prompt)
        estimated_tokens = input_estimate + self.max_output_tokens
        self.last_usage = {
            "input_tokens": input_estimate,
            "output_tokens": 0,
            "total_tokens": estimated_tokens,
        }
        for attempt in range(self.max_retries + 1):
            reservation = await self.rate_limiter.acquire(estimated_tokens)
            try:
                out, usage = await asyncio.wait_for(
                    self._once(system_prompt, user_prompt), timeout=self.timeout
                )
                has_actual_usage = usage.pop("reported")
                self.last_usage = usage
                if has_actual_usage:
                    self.rate_limiter.update(reservation, usage["total_tokens"])
                self.last_retry_count = attempt
                return out
            except Exception as exc:
                last = exc
                self.last_retry_count = attempt
                if attempt < self.max_retries and self._is_retryable(exc):
                    await self.sleep(self._retry_delay(exc, attempt))
                    continue
                raise
        raise last

    def generate_sync(self, system_prompt: str, user_prompt: str) -> str:
        last = None
        self.last_retry_count = 0
        input_estimate = estimate_prompt_tokens(system_prompt, user_prompt)
        estimated_tokens = input_estimate + self.max_output_tokens
        self.last_usage = {
            "input_tokens": input_estimate,
            "output_tokens": 0,
            "total_tokens": estimated_tokens,
        }
        for attempt in range(self.max_retries + 1):
            reservation = self.rate_limiter.acquire_sync(estimated_tokens)
            try:
                if not self.api_key:
                    raise GeminiAPIError(401, "missing GEMINI_API_KEY")
                resp = self._sync_client.post(
                    self._url(),
                    params={"key": self.api_key},
                    json=self._body(system_prompt, user_prompt),
                )
                if resp.status_code >= 400:
                    raise GeminiAPIError(resp.status_code, resp.text)
                data = resp.json()
                candidates = data.get("candidates") or []
                if not candidates:
                    pf = data.get("promptFeedback") or {}
                    block = pf.get("blockReason")
                    if block:
                        raise GeminiAPIError(403, f"safety block: {block}")
                    raise GeminiAPIError(400, "empty candidates")
                candidate = candidates[0]
                finish_reason = candidate.get("finishReason")
                if finish_reason in {"SAFETY", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII"}:
                    raise GeminiAPIError(400, f"safety block: {finish_reason}")
                content = candidate.get("content") or {}
                parts = content.get("parts") or []
                if not parts:
                    raise GeminiAPIError(400, "empty candidates")
                text = parts[0].get("text")
                if text is None:
                    raise GeminiAPIError(400, "empty candidates")
                metadata = data.get("usageMetadata") or {}
                input_tokens = metadata.get("promptTokenCount", metadata.get("prompt_token_count"))
                output_tokens = metadata.get("candidatesTokenCount", metadata.get("candidates_token_count"))
                has_actual_total = metadata.get("totalTokenCount", metadata.get("total_token_count")) is not None or (
                    input_tokens is not None and output_tokens is not None
                )
                input_tokens = int(input_tokens) if input_tokens is not None else input_estimate
                output_tokens = int(output_tokens) if output_tokens is not None else math.ceil(len(text) / 4)
                total_tokens = metadata.get("totalTokenCount", metadata.get("total_token_count"))
                self.last_usage = {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": int(total_tokens) if total_tokens is not None else input_tokens + output_tokens,
                }
                if has_actual_total:
                    self.rate_limiter.update(reservation, self.last_usage["total_tokens"])
                self.last_retry_count = attempt
                return text
            except Exception as exc:
                last = exc
                self.last_retry_count = attempt
                if attempt < self.max_retries and self._is_retryable(exc):
                    self.sync_sleep(self._retry_delay(exc, attempt))
                    continue
                raise
        raise last

    async def health_check(self) -> bool:
        return bool(self.model)

    def health_check_sync(self) -> bool:
        return bool(self.model)

    async def close(self):
        await self._async_client.aclose()
        self._sync_client.close()
