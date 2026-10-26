import asyncio
import time

from mistralai.client import Mistral

from app.config import settings


class MistralAPIError(Exception):
    def __init__(self, status_code, message=""):
        super().__init__(message)
        self.status_code = status_code

from .base_provider import BaseLLMProvider, classify_error
from .rate_limiter import (
    SlidingWindowRateLimiter,
    estimate_prompt_tokens,
    get_shared_limiter,
)


class MistralProvider(BaseLLMProvider):
    def __init__(
        self,
        api_key=None,
        model=None,
        timeout=None,
        max_retries=None,
        temperature=None,
        rate_limiter: SlidingWindowRateLimiter | None = None,
        max_output_tokens=None,
        sleep=asyncio.sleep,
        sync_sleep=time.sleep,
    ):
        self.api_key = api_key if api_key is not None else settings.mistral_api_key
        self.model = model if model is not None else settings.model_name
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
        self.client = Mistral(api_key=self.api_key) if self.api_key else Mistral(api_key="")
        self.last_retry_count = 0
        self.last_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    def _retry_delay(self, exc, attempt):
        headers = getattr(exc, "headers", None)
        if headers is not None:
            retry_after = None
            try:
                retry_after = headers.get("retry-after")
            except Exception:
                retry_after = None
            if retry_after is not None:
                try:
                    return float(retry_after)
                except (TypeError, ValueError):
                    pass
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

    async def _once(self, system_prompt, user_prompt):
        if not self.api_key:
            raise MistralAPIError(401, "missing MISTRAL_API_KEY")
        resp = await self.client.chat.complete_async(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=self.temperature,
            timeout_ms=int(self.timeout * 1000),
        )
        choices = getattr(resp, "choices", None) or []
        if not choices:
            raise ValueError("empty candidates")
        message = getattr(choices[0], "message", None)
        content = getattr(message, "content", None) if message is not None else None
        if not content:
            raise ValueError("empty candidates")
        return resp, content

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
                resp, content = await asyncio.wait_for(
                    self._once(system_prompt, user_prompt), timeout=self.timeout
                )
                usage = getattr(resp, "usage", None)
                input_tokens = getattr(usage, "prompt_tokens", None) if usage is not None else None
                output_tokens = getattr(usage, "completion_tokens", None) if usage is not None else None
                total_tokens = getattr(usage, "total_tokens", None) if usage is not None else None
                if input_tokens is None:
                    input_tokens = input_estimate
                if output_tokens is None:
                    output_tokens = max(0, len(content) // 4)
                if total_tokens is None:
                    total_tokens = input_tokens + output_tokens
                self.last_usage = {
                    "input_tokens": int(input_tokens),
                    "output_tokens": int(output_tokens),
                    "total_tokens": int(total_tokens),
                }
                try:
                    self.rate_limiter.update(reservation, int(total_tokens))
                except Exception:
                    pass
                self.last_retry_count = attempt
                return content
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
                    raise MistralAPIError(401, "missing MISTRAL_API_KEY")
                resp = self.client.chat.complete(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format={"type": "json_object"},
                    temperature=self.temperature,
                    timeout_ms=int(self.timeout * 1000),
                )
                choices = getattr(resp, "choices", None) or []
                if not choices:
                    raise ValueError("empty candidates")
                message = getattr(choices[0], "message", None)
                content = getattr(message, "content", None) if message is not None else None
                if not content:
                    raise ValueError("empty candidates")
                usage = getattr(resp, "usage", None)
                input_tokens = getattr(usage, "prompt_tokens", None) if usage is not None else None
                output_tokens = getattr(usage, "completion_tokens", None) if usage is not None else None
                total_tokens = getattr(usage, "total_tokens", None) if usage is not None else None
                if input_tokens is None:
                    input_tokens = input_estimate
                if output_tokens is None:
                    output_tokens = max(0, len(content) // 4)
                if total_tokens is None:
                    total_tokens = input_tokens + output_tokens
                self.last_usage = {
                    "input_tokens": int(input_tokens),
                    "output_tokens": int(output_tokens),
                    "total_tokens": int(total_tokens),
                }
                try:
                    self.rate_limiter.update(reservation, int(total_tokens))
                except Exception:
                    pass
                self.last_retry_count = attempt
                return content
            except Exception as exc:
                last = exc
                self.last_retry_count = attempt
                if attempt < self.max_retries and self._is_retryable(exc):
                    self.sync_sleep(self._retry_delay(exc, attempt))
                    continue
                raise
        raise last

    async def close(self):
        return None

    async def health_check(self) -> bool:
        return bool(self.api_key or True) and bool(self.model)

    def health_check_sync(self) -> bool:
        return bool(self.model)