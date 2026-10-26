"""Feedback endpoints."""

import threading
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from app.schemas.feedback import FeedbackCreate, FeedbackRecord, FeedbackResponse, FeedbackStats
from app.services.feedback_service import get_feedback_service

router = APIRouter(tags=["feedback"])

# Shared store (kept in sync with the feedback service)
_FEEDBACK_SERVICE = get_feedback_service()
_STORE: List[FeedbackRecord] = _FEEDBACK_SERVICE._items
_LOCK = threading.Lock()
_COUNTER = {"n": 0}


def _service(request: Optional[Request] = None) -> Any:
    if request is not None:
        state = getattr(getattr(request, "app", None), "state", None)
        if state is not None:
            svc = getattr(state, "feedback_service", None)
            if svc is not None:
                return svc
    return get_feedback_service()


def reset_feedback_store() -> None:
    svc = get_feedback_service()
    svc.clear()
    with _LOCK:
        _COUNTER["n"] = 0


def get_feedback_store() -> List[FeedbackRecord]:
    return list(_STORE)


@router.post("/feedback", response_model=FeedbackResponse, tags=["feedback"])
async def submit_feedback(payload: FeedbackCreate, request: Request = None) -> FeedbackResponse:
    svc = _service(request)
    agent = None
    if request is not None:
        state = getattr(getattr(request, "app", None), "state", None)
        if state is not None:
            agent = getattr(state, "agent", None)
    record = svc.record(payload, agent=agent)
    return FeedbackResponse(status="ok", id=record.id, created_at=record.created_at)


@router.get("/feedback", tags=["feedback"])
async def list_feedback(
    request: Request = None,
    limit: Optional[int] = Query(default=None),
    offset: int = Query(default=0),
):
    svc = _service(request)
    items = svc.list(limit=limit, offset=offset)
    return [r.model_dump() if hasattr(r, "model_dump") else r for r in items]


@router.get("/feedback/stats", response_model=FeedbackStats, tags=["feedback"])
async def feedback_stats(request: Request = None) -> FeedbackStats:
    svc = _service(request)
    return svc.stats()


@router.get("/feedback/metrics", tags=["feedback"])
async def feedback_metrics(request: Request = None):
    svc = _service(request)
    return svc.accuracy_metrics()


@router.get("/feedback/aggregate", tags=["feedback"])
async def feedback_aggregate(request: Request = None):
    svc = _service(request)
    return svc.aggregate()


@router.get("/feedback/export", tags=["feedback"])
async def feedback_export(request: Request = None, format: str = Query(default="json")):
    svc = _service(request)
    data = svc.export(format=format)
    if format in {"jsonl", "ndjson", "csv"}:
        return PlainTextResponse(str(data))
    if format in {"dataset", "training"}:
        return data
    return data


@router.post("/feedback/apply", tags=["feedback"])
async def feedback_apply(request: Request = None):
    svc = _service(request)
    agent = None
    if request is not None:
        state = getattr(getattr(request, "app", None), "state", None)
        if state is not None:
            agent = getattr(state, "agent", None)
    count = svc.apply_feedback_to_prompt(agent=agent)
    return {"status": "ok", "applied": count}


@router.post("/feedback/suggest", tags=["feedback"])
async def feedback_suggest(payload: Dict[str, Any], request: Request = None):
    svc = _service(request)
    agent = None
    if request is not None:
        state = getattr(getattr(request, "app", None), "state", None)
        if state is not None:
            agent = getattr(state, "agent", None)
    word = payload.get("word") or payload.get("text")
    vocabulary = payload.get("vocabulary")
    if vocabulary is None and agent is not None:
        vocabulary = getattr(agent, "vocabulary", None)
    suggestions = svc.suggest(word, vocabulary=vocabulary, n=payload.get("n", 3))
    return {"word": word, "suggestions": suggestions}


@router.get("/feedback/{item_id}", tags=["feedback"])
async def get_feedback(item_id: int, request: Request = None):
    svc = _service(request)
    rec = svc.get(item_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="feedback not found")
    return rec.model_dump() if hasattr(rec, "model_dump") else rec


@router.delete("/feedback/{item_id}", tags=["feedback"])
async def delete_feedback(item_id: int, request: Request = None):
    svc = _service(request)
    ok = svc.delete(item_id)
    if not ok:
        raise HTTPException(status_code=404, detail="feedback not found")
    return {"status": "ok", "deleted": item_id}
