"""Provider registry/factory for LLM providers."""

from typing import Any, Callable, Dict, Optional, Type

from .base_provider import BaseLLMProvider
from .gemini_provider import GeminiProvider
from .mistral_provider import MistralProvider

PROVIDER_REGISTRY: Dict[str, Callable[..., BaseLLMProvider]] = {}


def register_provider(name: str, factory: Any) -> None:
    key = (name or "").lower()
    if callable(factory) and not isinstance(factory, type):
        PROVIDER_REGISTRY[key] = factory
    else:
        # treat as class
        def _factory(**kwargs):
            return factory(**kwargs)
        PROVIDER_REGISTRY[key] = _factory


def unregister_provider(name: str) -> None:
    PROVIDER_REGISTRY.pop((name or "").lower(), None)


def list_providers() -> list:
    return sorted(PROVIDER_REGISTRY.keys())


def get_provider(name: str) -> Optional[Callable[..., BaseLLMProvider]]:
    return PROVIDER_REGISTRY.get((name or "").lower())


def create_provider(name: str, **kwargs: Any) -> BaseLLMProvider:
    key = (name or "").lower()
    factory = PROVIDER_REGISTRY.get(key)
    if factory is None:
        raise ValueError(f"Unknown provider: {name}")
    return factory(**kwargs)


def make_provider(name: str, **kwargs: Any) -> BaseLLMProvider:
    return create_provider(name, **kwargs)


# default registrations
def _mistral_factory(**kwargs):
    return MistralProvider(**kwargs)

def _gemini_factory(**kwargs):
    return GeminiProvider(**kwargs)

register_provider("mistral", _mistral_factory)
register_provider("gemini", _gemini_factory)

# optional OpenAI provider (httpx-based, best-effort)
try:
    import httpx

    class OpenAIProvider(BaseLLMProvider):
        BASE_URL = "https://api.openai.com/v1/chat/completions"

        def __init__(self, api_key=None, model=None, timeout=None, transport=None, **kwargs):
            from app.config import settings

            self.api_key = api_key if api_key is not None else getattr(settings, "openai_api_key", "")
            self.model = model or getattr(settings, "openai_model", "gpt-4o-mini")
            self.timeout = timeout if timeout is not None else getattr(settings, "timeout", 30)
            self.transport = transport
            self._client = httpx.AsyncClient(transport=transport, timeout=self.timeout)
            self._sync_client = httpx.Client(transport=transport, timeout=self.timeout)
            self.last_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

        async def generate(self, system_prompt, user_prompt):
            if not self.api_key:
                raise ValueError("missing OPENAI_API_KEY")
            resp = await self._client.post(
                self.BASE_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "response_format": {"type": "json_object"},
                },
            )
            if resp.status_code >= 400:
                raise ValueError(resp.text)
            data = resp.json()
            return data["choices"][0]["message"]["content"]

        def generate_sync(self, system_prompt, user_prompt):
            if not self.api_key:
                raise ValueError("missing OPENAI_API_KEY")
            resp = self._sync_client.post(
                self.BASE_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "response_format": {"type": "json_object"},
                },
            )
            if resp.status_code >= 400:
                raise ValueError(resp.text)
            data = resp.json()
            return data["choices"][0]["message"]["content"]

        async def close(self):
            await self._client.aclose()
            self._sync_client.close()

        async def health_check(self):
            return bool(self.model)

    register_provider("openai", OpenAIProvider)
except Exception:
    pass


# aliases
ProviderRegistry = PROVIDER_REGISTRY
register = register_provider
create = create_provider
make = make_provider
get = get_provider