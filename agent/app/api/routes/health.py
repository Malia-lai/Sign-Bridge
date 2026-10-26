import time
from typing import Any, Dict

from fastapi import APIRouter, Request

from app.api.dependencies import get_settings
from app.config import settings
from app.core.agent import Agent

router = APIRouter()

_START_TIME = time.time()
_REQUEST_COUNTS: Dict[str, int] = {"total": 0, "errors": 0}


def record_request() -> None:
    _REQUEST_COUNTS["total"] += 1


def record_error() -> None:
    _REQUEST_COUNTS["errors"] += 1


@router.get("/health")
async def health(request: Request = None):
    s = get_settings()
    return {
        "status": "ok",
        "model": getattr(s, "model_name", None),
        "provider": getattr(s, "llm_provider", None),
        "mock_mode": getattr(s, "mock_mode", None),
        "output_language": getattr(s, "output_language", None),
        "version": "1.0.0",
    }


@router.get("/ready")
async def ready(request: Request = None):
    try:
        # validate prompt files exist
        from app.api.dependencies import validate_prompt_files

        validate_prompt_files()
        return {"status": "ready"}
    except Exception as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/metrics")
async def metrics(request: Request = None):
    # Basic metrics payload (JSON). Also expose a simple text-friendly summary.
    uptime = time.time() - _START_TIME
    payload = {
        "uptime_seconds": uptime,
        "requests_total": _REQUEST_COUNTS["total"],
        "errors_total": _REQUEST_COUNTS["errors"],
        "mock_mode": getattr(settings, "mock_mode", None),
        "provider": getattr(settings, "llm_provider", None),
        "model": getattr(settings, "model_name", None),
    }
    return payload


@router.get("/")
async def root():
    return {"status": "ok"}