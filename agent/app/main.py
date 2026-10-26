import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.dependencies import get_settings, validate_prompt_files
from app.api.middleware import RequestIDMiddleware
from app.api.routes import health, sentence
from app.core.agent import Agent
from app.llm.client import LLMClient


def _parse_origins(value: str):
    parts = [p.strip() for p in (value or "").split(",")]
    return [p for p in parts if p]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup validation (fail fast)
    validate_prompt_files()
    settings = get_settings()
    app.state.settings = settings
    app.state.llm_client = LLMClient()
    app.state.agent = Agent(mock_mode=settings.mock_mode, llm_client=app.state.llm_client)
    yield
    # graceful shutdown
    client = getattr(app.state, "llm_client", None)
    if client is not None:
        for provider in (getattr(client, "provider", None), getattr(client, "fallback_provider", None)):
            if provider is None:
                continue
            close = getattr(provider, "close", None)
            if close is not None:
                try:
                    result = close()
                    if asyncio.iscoroutine(result):
                        await result
                except Exception:
                    pass
    # DB connections (none yet, but hook reserved)


settings = get_settings()
origins = _parse_origins(getattr(settings, "cors_origins", "*"))
if not origins:
    origins = ["*"]

app = FastAPI(title="Sign Bridge Agent", lifespan=lifespan)

app.add_middleware(RequestIDMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials="*" not in origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(sentence.router)
app.include_router(health.router, prefix="/api")
app.include_router(sentence.router, prefix="/api")

# convenience aliases for tests/tooling
validate_prompt_files = validate_prompt_files
get_settings = get_settings