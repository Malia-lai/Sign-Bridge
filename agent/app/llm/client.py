import json
import re
from typing import Any, Dict, List, Optional

from app.config import settings

from .base_provider import BaseLLMProvider, classify_error
from .gemini_provider import GeminiProvider
from .mistral_provider import MistralProvider


def _extract_json(text: str) -> Dict[str, Any]:
    text = (text or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


def _make_provider(name: str) -> BaseLLMProvider:
    name = (name or "").lower()
    if name == "gemini":
        return GeminiProvider()
    return MistralProvider()


class LLMClient:
    def __init__(self, provider: Optional[BaseLLMProvider] = None):
        primary_name = settings.llm_provider
        self.provider = provider if provider is not None else _make_provider(primary_name)
        self.provider_name = primary_name if provider is None else type(provider).__name__.replace("Provider", "").lower()
        fallback_name = settings.fallback_provider
        self.fallback_provider = _make_provider(fallback_name) if fallback_name else None
        self.fallback_provider_name = fallback_name if fallback_name else None
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

    async def _generate_with_fallback(self, system_prompt, user_prompt, sync=False):
        try:
            if sync:
                out = self.provider.generate_sync(system_prompt, user_prompt)
            else:
                out = await self.provider.generate(system_prompt, user_prompt)
            self.last_provider_used = self.provider_name
            self.last_retry_count = getattr(self.provider, "last_retry_count", 0)
            self.last_usage = getattr(self.provider, "last_usage", self.last_usage)
            return out
        except Exception as exc:
            self.last_usage = getattr(self.provider, "last_usage", self.last_usage)
            reason = classify_error(exc)
            if self.fallback_provider is not None and reason in {"rate_limit", "timeout"}:
                try:
                    if sync:
                        out = self.fallback_provider.generate_sync(system_prompt, user_prompt)
                    else:
                        out = await self.fallback_provider.generate(system_prompt, user_prompt)
                    self.last_provider_used = self.fallback_provider_name
                    self.last_usage = getattr(self.fallback_provider, "last_usage", self.last_usage)
                    self.last_retry_count = getattr(self.provider, "last_retry_count", 0) + 1 + getattr(self.fallback_provider, "last_retry_count", 0)
                    return out
                except Exception:
                    raise
            raise

    def _generate_with_fallback_sync(self, system_prompt, user_prompt):
        try:
            out = self.provider.generate_sync(system_prompt, user_prompt)
            self.last_provider_used = self.provider_name
            return out
        except Exception as exc:
            reason = classify_error(exc)
            if self.fallback_provider is not None and reason in {"rate_limit", "timeout"}:
                out = self.fallback_provider.generate_sync(system_prompt, user_prompt)
                self.last_provider_used = self.fallback_provider_name
                self.last_retry_count = getattr(self.provider, "last_retry_count", 0) + 1 + getattr(self.fallback_provider, "last_retry_count", 0)
                return out
            raise


def get_llm_client(provider=None) -> LLMClient:
    if provider is not None:
        return LLMClient(provider=provider)
    return LLMClient()


def create_provider() -> BaseLLMProvider:
    return _make_provider(settings.llm_provider)
