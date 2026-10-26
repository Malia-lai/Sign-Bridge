"""Vocabulary management endpoints."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.services.vocabulary_service import get_vocabulary_service

router = APIRouter(tags=["vocabulary"])


class VocabAddRequest(BaseModel):
    word: Optional[str] = None
    words: List[Any] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class VocabImportRequest(BaseModel):
    vocabulary: Any = None
    words: List[Any] = Field(default_factory=list)
    data: Any = None
    replace: bool = False


def _service(request: Optional[Request] = None):
    if request is not None:
        svc = getattr(getattr(request, "app", None), "state", None)
        if svc is not None:
            v = getattr(svc, "vocabulary_service", None)
            if v is not None:
                return v
    return get_vocabulary_service()


def _agent(request: Optional[Request] = None):
    if request is not None:
        svc = getattr(getattr(request, "app", None), "state", None)
        if svc is not None:
            return getattr(svc, "agent", None)
    return None


@router.get("/vocabulary")
async def list_vocabulary(request: Request):
    svc = _service(request)
    return {
        "words": svc.words(),
        "vocabulary": svc.get_vocabulary(),
        "total": len(svc.words()),
    }


@router.get("/vocab")
async def list_vocab_alias(request: Request):
    return await list_vocabulary(request)


@router.post("/vocabulary")
async def add_vocabulary(payload: VocabAddRequest, request: Request):
    svc = _service(request)
    agent = _agent(request)
    if agent is not None and getattr(svc, "agent", None) is None:
        svc.agent = agent
    if payload.word is None and not payload.words:
        raise HTTPException(status_code=422, detail="word or words required")
    added = svc.add(
        word=payload.word, words=payload.words, tags=payload.tags, metadata=payload.metadata
    )
    if agent is not None:
        try:
            for w in added if isinstance(added, list) else [added]:
                agent.add_vocabulary_word(w, tags=payload.tags, metadata=payload.metadata)
        except Exception:
            pass
    return {"status": "ok", "added": added, "words": svc.words()}


@router.delete("/vocabulary/{word}")
async def remove_vocabulary(word: str, request: Request):
    svc = _service(request)
    agent = _agent(request)
    if agent is not None and getattr(svc, "agent", None) is None:
        svc.agent = agent
    ok = svc.remove(word=word)
    if agent is not None:
        try:
            agent.remove_vocabulary_word(word)
        except Exception:
            pass
    if not ok:
        raise HTTPException(status_code=404, detail="word not found")
    return {"status": "ok", "removed": word, "words": svc.words()}


@router.post("/vocabulary/remove")
async def remove_vocabulary_post(payload: VocabAddRequest, request: Request):
    svc = _service(request)
    agent = _agent(request)
    targets = ([payload.word] if payload.word else []) + list(payload.words or [])
    removed = []
    for w in targets:
        if svc.remove(word=w):
            removed.append(w)
            if agent is not None:
                try:
                    agent.remove_vocabulary_word(w)
                except Exception:
                    pass
    return {"status": "ok", "removed": removed, "words": svc.words()}


@router.post("/vocabulary/import")
async def import_vocabulary(payload: VocabImportRequest, request: Request):
    svc = _service(request)
    agent = _agent(request)
    if agent is not None and getattr(svc, "agent", None) is None:
        svc.agent = agent
    data = payload.vocabulary if payload.vocabulary is not None else payload.data
    if data is None and payload.words:
        data = payload.words
    count = svc.import_vocabulary(data, replace=payload.replace)
    if agent is not None:
        try:
            agent.set_vocabulary(svc.get_vocabulary())
        except Exception:
            pass
    return {"status": "ok", "imported": count, "words": svc.words()}


@router.get("/vocabulary/export")
async def export_vocabulary(request: Request, format: str = Query(default="json")):
    svc = _service(request)
    return {"format": format, "data": svc.export(format=format), "words": svc.words()}
