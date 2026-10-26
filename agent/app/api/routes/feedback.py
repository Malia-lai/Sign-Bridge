"""Feedback endpoints."""

import threading
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request

from app.schemas.feedback import FeedbackCreate, FeedbackRecord, FeedbackResponse, FeedbackStats

router = APIRouter(tags=["feedback"])

_STORE: List[FeedbackRecord] = []
_LOCK = threading.Lock()
_COUNTER = {"n": 0}


def reset_feedback_store() -> None:
    with _LOCK:
        _STORE.clear()
        _COUNTER["n"] = 0


def get_feedback_store() -> List[FeedbackRecord]:
    with _LOCK:
        return list(_STORE)


def _to_number(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


@router.post("/feedback", response_model=FeedbackResponse, tags=["feedback"])
async def submit_feedback(payload: FeedbackCreate, request: Request = None) -> FeedbackResponse:
    with _LOCK:
        _COUNTER["n"] += 1
        fid = _COUNTER["n"]
        record = FeedbackRecord(
            id=fid,
            request_id=payload.request_id,
            words=list(payload.words or []),
            original_sentence=payload.original_sentence,
            corrected_sentence=payload.corrected_sentence,
            rating=payload.rating,
            comment=payload.comment,
            metadata=dict(payload.metadata or {}),
            created_at=datetime_now(),
        )
        _STORE.append(record)
    # Feed corrections back into the agent (learning loop)
    try:
        app = getattr(request, "app", None) if request is not None else None
        state = getattr(app, "state", None) if app is not None else None
        correction_service = getattr(state, "correction_service", None) if state is not None else None
        if correction_service is None:
            from app.services.correction_service import get_correction_service

            correction_service = get_correction_service()
        agent = getattr(state, "agent", None) if state is not None else None
        history_service = getattr(state, "history_service", None) if state is not None else None
        if history_service is None:
            from app.services.history_service import get_history_service

            history_service = get_history_service()
        st = getattr(request.app, "state", None)
        from app.main import app as global_app
        if payload.corrected_sentence:
            correction_service.record(
                request_id=payload.request_id,
                words=list(payload.words or []),
                original_sentence=payload.original_sentence,
                corrected_sentence=payload.corrected_sentence,
                rating=payload.rating,
                comment=payload.comment,
                metadata=dict(payload.metadata or {}),
                agent=agent,
            )
            if history_service is not None:
                matched = False
                if payload.request_id:
                    for h in history_service.all():
                        if h.request_id == payload.request_id:
                            h.corrected_sentence = payload.corrected_sentence
                            matched = True
                if not matched:
                    candidates = [
                        h for h in history_service.all()
                        if (not payload.words) or (h.words == [str(w).strip() for w in payload.words if str(w).strip()])
                    ]
                    if candidates:
                        candidates[-1].corrected_sentence = payload.corrected_sentence
    except Exception as e:
        pass
    return FeedbackResponse(status="ok", id=fid, created_at=record.created_at)


@router.get("/feedback/stats", response_model=FeedbackStats, tags=["feedback"])
async def feedback_stats() -> FeedbackStats:
    with _LOCK:
        records = list(_STORE)
    total = len(records)
    nums = []
    ratings: Dict[str, int] = {}
    with_correction = 0
    for r in records:
        v = _to_number(r.rating)
        if v is not None:
            nums.append(v)
        key = str(r.rating) if r.rating is not None else "none"
        ratings[key] = ratings.get(key, 0) + 1
        if r.corrected_sentence:
            with_correction += 1
    avg = (sum(nums) / len(nums)) if nums else None
    return FeedbackStats(
        total=total,
        average_rating=avg,
        ratings=ratings,
        with_correction=with_correction,
    )


def datetime_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
