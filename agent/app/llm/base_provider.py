from abc import ABC, abstractmethod
from typing import Any, Dict, List


class BaseLLMProvider(ABC):
    """Swappable LLM provider interface."""

    @abstractmethod
    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        raise NotImplementedError

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

    def generate_sync(self, system_prompt: str, user_prompt: str) -> str:
        raise NotImplementedError

    def complete_sync(self, messages: List[Dict[str, str]]) -> str:
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
        return self.generate_sync(system_prompt, user_prompt)


# aliases
LLMProvider = BaseLLMProvider
BaseProvider = BaseLLMProvider


def classify_error(exc: Exception) -> str:
    status = getattr(exc, "status_code", None)
    if status == 429:
        return "rate_limit"
    if status in (401, 403):
        return "auth_error"
    name = type(exc).__name__.lower()
    text = str(exc).lower()
    if isinstance(exc, (TimeoutError,)) or "timeout" in name or "timeout" in text:
        return "timeout"
    if "json" in name or "expecting value" in text or "jsondecodeerror" in name:
        return "invalid_json"
    return "other"