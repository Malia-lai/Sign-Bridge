import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi import HTTPException as _HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import websocket as ws_routes
from app.api.dependencies import get_settings, validate_prompt_files
from app.api.middleware import (
    APIKeyMiddleware,
    PerIPRateLimitMiddleware,
    RequestIDMiddleware,
    RequestResponseLoggingMiddleware,
)
from app.api.routes import feedback, health, history, prompts, sentence, vocabulary
from app.core.agent import Agent
from app.llm.client import LLMClient


def _parse_origins(value: str):
    parts = [p.strip() for p in (value or "").split(",")]
    return [p for p in parts if p]


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_prompt_files()
    settings = get_settings()
    app.state.settings = settings
    # database
    from app.db.database import close_db, init_db

    app.state.db_engine = await init_db()
    app.state.db_session_factory = None
    try:
        from app.db.database import get_session_factory

        app.state.db_session_factory = get_session_factory(app.state.db_engine)
    except Exception:
        pass
    app.state.llm_client = LLMClient()

    from app.services.correction_service import get_correction_service
    from app.services.history_service import get_history_service
    from app.services.prompt_service import get_prompt_service
    from app.services.vocabulary_service import get_vocabulary_service

    app.state.history_service = get_history_service()
    app.state.correction_service = get_correction_service()
    app.state.vocabulary_service = get_vocabulary_service()
    app.state.prompt_service = get_prompt_service()
    from app.services.feedback_service import get_feedback_service

    app.state.feedback_service = get_feedback_service()

    app.state.agent = Agent(
        mock_mode=settings.mock_mode,
        llm_client=app.state.llm_client,
        history_service=app.state.history_service,
        correction_service=app.state.correction_service,
        vocabulary_service=app.state.vocabulary_service,
        prompt_service=app.state.prompt_service,
        feedback_service=app.state.feedback_service,
    )
    # sync service -> agent references
    for svc in (
        app.state.history_service,
        app.state.correction_service,
        app.state.vocabulary_service,
        app.state.prompt_service,
        app.state.feedback_service,
    ):
        try:
            svc.agent = app.state.agent
        except Exception:
            pass
    try:
        app.state.vocabulary_service.vocabulary = app.state.agent.vocabulary
    except Exception:
        pass
    yield
    # shutdown db
    try:
        await close_db()
    except Exception:
        pass
    client = getattr(app.state, "llm_client", None)
    if client is not None:
        for provider in (
            getattr(client, "provider", None),
            getattr(client, "fallback_provider", None),
        ):
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


settings = get_settings()
origins = _parse_origins(getattr(settings, "cors_origins", "*"))
if not origins:
    origins = ["*"]

OPENAPI_TAGS = [
    {"name": "health", "description": "Health and readiness endpoints"},
    {"name": "sentence", "description": "Sentence generation"},
    {"name": "feedback", "description": "Feedback collection"},
    {"name": "history", "description": "Sentence history"},
    {"name": "vocabulary", "description": "Vocabulary management"},
    {"name": "prompts", "description": "Prompt templates"},
    {"name": "websocket", "description": "WebSocket endpoints"},
]

app = FastAPI(
    title="Sign Bridge Agent",
    description="AI agent service that turns signed words into natural sentences.",
    version="1.0.0",
    contact={"name": "Sign-Bridge", "email": "support@sign-bridge.local"},
    openapi_tags=OPENAPI_TAGS,
    lifespan=lifespan,
    swagger_ui_parameters={"defaultModelsExpandDepth": -1},
)

# middleware order
app.add_middleware(RequestIDMiddleware)
app.add_middleware(RequestResponseLoggingMiddleware)
app.add_middleware(
    PerIPRateLimitMiddleware,
    limit=getattr(settings, "rate_limit_per_minute", 60),
    window=60,
)
app.add_middleware(APIKeyMiddleware, api_key=getattr(settings, "api_key", ""))
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials="*" not in origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.options("/{rest_of_path:path}")
async def preflight(rest_of_path: str, request: Request):
    # Explicit CORS preflight handling
    return JSONResponse(status_code=200, content={"status": "ok"})


# exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    try:
        errors = exc.errors()
    except Exception:
        errors = []
    # ensure JSON-serializable
    import json as _json

    try:
        errors = _json.loads(_json.dumps(errors, default=str))
    except Exception:
        errors = [str(e) for e in errors]
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Validation error",
            "errors": errors,
        },
    )


@app.exception_handler(_HTTPException)
async def http_exception_handler(request: Request, exc: _HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    settings = get_settings()
    if getattr(settings, "debug", False):
        return JSONResponse(status_code=500, content={"detail": str(exc)})
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# routers
app.include_router(health.router, tags=["health"])
app.include_router(sentence.router, tags=["sentence"])
app.include_router(feedback.router, tags=["feedback"])
app.include_router(history.router, tags=["history"])
app.include_router(vocabulary.router, tags=["vocabulary"])
app.include_router(prompts.router, tags=["prompts"])
app.include_router(ws_routes.router, tags=["websocket"])

# /api prefix (backward compat)
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(sentence.router, prefix="/api", tags=["sentence"])
app.include_router(feedback.router, prefix="/api", tags=["feedback"])
app.include_router(history.router, prefix="/api", tags=["history"])
app.include_router(vocabulary.router, prefix="/api", tags=["vocabulary"])
app.include_router(prompts.router, prefix="/api", tags=["prompts"])
app.include_router(ws_routes.router, prefix="/api", tags=["websocket"])

# /v1 versioning
app.include_router(health.router, prefix="/v1", tags=["health"])
app.include_router(sentence.router, prefix="/v1", tags=["sentence"])
app.include_router(feedback.router, prefix="/v1", tags=["feedback"])
app.include_router(history.router, prefix="/v1", tags=["history"])
app.include_router(vocabulary.router, prefix="/v1", tags=["vocabulary"])
app.include_router(prompts.router, prefix="/v1", tags=["prompts"])
app.include_router(ws_routes.router, prefix="/v1", tags=["websocket"])

# convenience aliases
validate_prompt_files = validate_prompt_files
get_settings = get_settings
