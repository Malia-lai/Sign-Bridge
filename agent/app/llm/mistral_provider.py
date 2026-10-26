import asyncio
import time

from mistralai.client import Mistral

from app.config import settings

from .base_provider import BaseLLMProvider, classify_error


class MistralProvider(BaseLLMProvider):
    def __init__(self, api_key=None, model=None, timeout=None, max_retries=None, temperature=None):
        self.api_key = api_key if api_key is not None else settings.mistral_api_key
        self.model = model or settings.model_name
        self.timeout = timeout if timeout is not None else settings.timeout
        self.max_retries = settings.max_retries if max_retries is None else int(max_retries)
        self.temperature = settings.temperature if temperature is None else float(temperature)
        self.client = Mistral(api_key=self.api_key) if self.api_key else Mistral(api_key="")
        self.last_retry_count = 0
        self._async_client = None
        self._sync_client = None

    def close(self):
        # Mistral SDK client has no persistent httpx client to close in this version;
        # keep method for parity with GeminiProvider.
        return None

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
        return await self.client.chat.complete_async(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=self.temperature,
            timeout_ms=int(self.timeout * 1000),
        )

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        last = None
        self.last_retry_count = 0
        for attempt in range(self.max_retries + 1):
            try:
                resp = await asyncio.wait_for(self._once(system_prompt, user_prompt), timeout=self.timeout)
                self.last_retry_count = attempt
                return resp.choices[0].message.content
            except Exception as exc:
                last = exc
                self.last_retry_count = attempt
                if attempt < self.max_retries and self._is_retryable(exc):
                    await asyncio.sleep(self._retry_delay(exc, attempt))
                    continue
                raise
        raise last

    def generate_sync(self, system_prompt: str, user_prompt: str) -> str:
        last = None
        self.last_retry_count = 0
        for attempt in range(self.max_retries + 1):
            try:
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
                self.last_retry_count = attempt
                return resp.choices[0].message.content
            except Exception as exc:
                last = exc
                self.last_retry_count = attempt
                if attempt < self.max_retries and self._is_retryable(exc):
                    time.sleep(self._retry_delay(exc, attempt))
                    continue
                raise
        raise last