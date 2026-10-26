import asyncio
import json
import re
from typing import Any, Dict, List, Optional

from app.config import settings

from .base_provider import BaseLLMProvider, classify_error
from .circuit_breaker import CircuitBreaker, CircuitOpenError
from .registry import create_provider as registry_create_provider


def _extract_json(text: str) -> Dict[str, Any]:
    text = (text or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


def _make_provider(name: str, **kwargs) -> BaseLLMProvider:
    name = (name or "").lower() or "mistral"
    try:
        return registry_create_provider(name, **kwargs)
    except Exception:
        # backward-compatible fallback
        if name == "gemini":
            from .gemini_provider import GeminiProvider

            return GeminiProvider(**kwargs)
        from .mistral_provider import MistralProvider

        return MistralProvider(**kwargs)


class LLMClient:
    def __init__(
        self,
        provider: Optional[BaseLLMProvider] = None,
        fallback_provider: Any = None,
        fallback_providers: Any = None,
        fallback_chain: Any = None,
        circuit_breaker: Any = None,
        **kwargs: Any,
    ):
        primary_name = settings.llm_provider
        self.provider = provider if provider is not None else _make_provider(primary_name, **kwargs)
        self.provider_name = (
            primary_name
            if provider is None
            else type(provider).__name__.replace("Provider", "").lower()
        )

        # build fallback chain
        chain_names = []
        if fallback_chain is not None:
            chain_names = (
                list(fallback_chain) if not isinstance(fallback_chain, str) else [fallback_chain]
            )
        if fallback_providers is not None:
            chain_names = (
                list(fallback_providers)
                if not isinstance(fallback_providers, str)
                else [fallback_providers]
            )
        if fallback_provider is not None:
            if isinstance(fallback_provider, str):
                chain_names = [fallback_provider] + chain_names
            else:
                # object provided; store separately
                self._fallback_objects = [fallback_provider]
            # else names
        # if no explicit fallback objects, build from names or settings
        if not hasattr(self, "_fallback_objects"):
            if not chain_names:
                fallback_name = settings.fallback_provider
                chain_names = [fallback_name] if fallback_name else []
            self._fallback_objects = []
            for name in chain_names:
                if not name:
                    continue
                if isinstance(name, BaseLLMProvider):
                    self._fallback_objects.append(name)
                elif isinstance(name, str):
                    try:
                        self._fallback_objects.append(_make_provider(name, **kwargs))
                    except Exception:
                        pass
                else:
                    self._fallback_objects.append(name)
        # backward compat single fallback_provider attribute
        self.fallback_provider = self._fallback_objects[0] if self._fallback_objects else None
        self.fallback_provider_name = getattr(self.fallback_provider, "provider_name", None) or (
            type(self.fallback_provider).__name__.replace("Provider", "").lower()
            if self.fallback_provider is not None
            else None
        )
        self.fallback_providers = list(self._fallback_objects)
        self.provider_chain = [self.provider] + list(self._fallback_objects)

        if circuit_breaker is None:
            circuit_breaker = CircuitBreaker(
                failure_threshold=0
            )  # disabled by default (0 disables)
        self.circuit_breaker = circuit_breaker

        self.last_provider_used = self.provider_name
        self.last_retry_count = 0
        self.last_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        return await self._generate_with_fallback(system_prompt, user_prompt, sync=False)

    async def complete(self, messages: List[Dict[str, str]]) -> str:
        system_prompt = ""
        user_prompt = ""
        for m in messages or []:
            role = m.get("role")
            content = m.get("content", "")
            if role == "system":
                system_prompt = content
            elif role == "user":
                user_prompt = content
            else:
                user_prompt += "\n" + content
        return await self.generate(system_prompt, user_prompt)

    async def generate_json(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        raw = await self.generate(system_prompt, user_prompt)
        return _extract_json(raw)

    def generate_sync(self, system_prompt: str, user_prompt: str) -> str:
        return self._generate_with_fallback_sync(system_prompt, user_prompt)

    def generate_json_sync(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        raw = self.generate_sync(system_prompt, user_prompt)
        return _extract_json(raw)

    async def close(self):
        for provider in (self.provider, self.fallback_provider):
            if provider is None:
                continue
            close = getattr(provider, "close", None)
            if close is None:
                continue
            result = close()
            if asyncio.iscoroutine(result):
                await result

    def close_sync(self):
        for provider in (self.provider, self.fallback_provider):
            if provider is None:
                continue
            close = getattr(provider, "close", None)
            if close is not None:
                close()

    async def _generate_with_fallback(self, system_prompt, user_prompt, sync=False):
        # circuit breaker check
        cb = getattr(self, "circuit_breaker", None)
        if cb is not None and getattr(cb, "enabled", True) and not cb.allow():
            raise CircuitOpenError("circuit breaker open")

        last_exc = None
        # try primary
        try:
            if sync:
                out = self.provider.generate_sync(system_prompt, user_prompt)
            else:
                out = await self.provider.generate(system_prompt, user_prompt)
            if cb is not None:
                cb.record_success()
            self.last_provider_used = self.provider_name
            self.last_retry_count = getattr(self.provider, "last_retry_count", 0)
            self.last_usage = getattr(self.provider, "last_usage", self.last_usage)
            return out
        except Exception as exc:
            last_exc = exc
            self.last_usage = getattr(self.provider, "last_usage", self.last_usage)
            reason = classify_error(exc)
            if cb is not None:
                cb.record_failure()

        reason = classify_error(last_exc) if last_exc is not None else "other"
        # try fallback chain only on rate_limit/timeout
        if reason in {"rate_limit", "timeout"}:
            for idx, fb in enumerate(self._fallback_objects):
                try:
                    if sync:
                        out = fb.generate_sync(system_prompt, user_prompt)
                    else:
                        out = await fb.generate(system_prompt, user_prompt)
                    if cb is not None:
                        cb.record_success()
                    self.last_provider_used = type(fb).__name__.replace("Provider", "").lower()
                    self.last_usage = getattr(fb, "last_usage", self.last_usage)
                    self.last_retry_count = (
                        getattr(self.provider, "last_retry_count", 0)
                        + 1
                        + getattr(fb, "last_retry_count", 0)
                    )
                    return out
                except Exception as exc:
                    last_exc = exc
                    if cb is not None:
                        cb.record_failure()
                    continue

        if last_exc is not None:
            raise last_exc
        raise RuntimeError("no provider available")

    def _generate_with_fallback_sync(self, system_prompt, user_prompt):
        cb = getattr(self, "circuit_breaker", None)
        if cb is not None and getattr(cb, "enabled", True) and not cb.allow():
            raise CircuitOpenError("circuit breaker open")

        last_exc = None
        try:
            out = self.provider.generate_sync(system_prompt, user_prompt)
            if cb is not None:
                cb.record_success()
            self.last_provider_used = self.provider_name
            self.last_retry_count = getattr(self.provider, "last_retry_count", 0)
            self.last_usage = getattr(self.provider, "last_usage", self.last_usage)
            return out
        except Exception as exc:
            last_exc = exc
            self.last_usage = getattr(self.provider, "last_usage", self.last_usage)
            if cb is not None:
                cb.record_failure()

        reason = classify_error(last_exc) if last_exc is not None else "other"
        if reason in {"rate_limit", "timeout"}:
            for fb in self._fallback_objects:
                try:
                    out = fb.generate_sync(system_prompt, user_prompt)
                    if cb is not None:
                        cb.record_success()
                    self.last_provider_used = type(fb).__name__.replace("Provider", "").lower()
                    self.last_usage = getattr(fb, "last_usage", self.last_usage)
                    self.last_retry_count = (
                        getattr(self.provider, "last_retry_count", 0)
                        + 1
                        + getattr(fb, "last_retry_count", 0)
                    )
                    return out
                except Exception as exc:
                    last_exc = exc
                    if cb is not None:
                        cb.record_failure()
                    continue

        if last_exc is not None:
            raise last_exc
        raise RuntimeError("no provider available")


def get_llm_client(provider=None) -> LLMClient:
    if provider is not None:
        return LLMClient(provider=provider)
    return LLMClient()


def create_provider() -> BaseLLMProvider:
    return _make_provider(settings.llm_provider)
