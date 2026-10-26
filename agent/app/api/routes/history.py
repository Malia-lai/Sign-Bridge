"""History endpoints."""

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Request

from app.services.history_service import get_history_service, reset_history_store

router = APIRouter(tags=["history"])


def _service(request: Optional[Request] = None):
    if request is not None:
        svc = getattr(getattr(request, "app", None), "state", None)
        if svc is not None:
            h = getattr(svc, "history_service", None)
            if h is not None:
                return h
    return get_history_service()


@router.get("/history")
async def list_history(
    request: Request,
    limit: Optional[int] = Query(default=None),
    offset: int = Query(default=0),
):
    svc = _service(request)
    items = svc.list(limit=limit, offset=offset)
    return [r.model_dump() if hasattr(r, "model_dump") else r for r in items]


@router.get("/history/{item_id}")
async def get_history(item_id: int, request: Request):
    svc = _service(request)
    rec = svc.get(item_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="history item not found")
    return rec.model_dump() if hasattr(rec, "model_dump") else rec


@router.delete("/history/{item_id}")
async def delete_history(item_id: int, request: Request):
    svc = _service(request)
    ok = svc.delete(item_id)
    if not ok:
        raise HTTPException(status_code=404, detail="history item not found")
    return {"status": "ok", "deleted": item_id}


@router.delete("/history")
async def clear_history(request: Request):
    svc = _service(request)
    count = svc.clear() if hasattr(svc, "clear") else svc.reset()
    return {"status": "ok", "deleted": count}