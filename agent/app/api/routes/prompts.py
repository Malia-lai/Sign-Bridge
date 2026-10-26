"""Prompt template endpoints."""

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.services.prompt_service import get_prompt_service

router = APIRouter(tags=["prompts"])


class PromptCreateRequest(BaseModel):
    name: Optional[str] = None
    template: Optional[str] = None
    content: Optional[str] = None
    text: Optional[str] = None
    version: Optional[str] = None
    variant: Optional[str] = None
    weight: float = 1.0
    metadata: dict = Field(default_factory=dict)
    activate: bool = False


class PromptActivateRequest(BaseModel):
    name: str


def _service(request: Optional[Request] = None):
    if request is not None:
        svc = getattr(getattr(request, "app", None), "state", None)
        if svc is not None:
            p = getattr(svc, "prompt_service", None)
            if p is not None:
                return p
    return get_prompt_service()


def _agent(request: Optional[Request] = None):
    if request is not None:
        svc = getattr(getattr(request, "app", None), "state", None)
        if svc is not None:
            return getattr(svc, "agent", None)
    return None


@router.get("/prompts")
async def list_prompts(request: Request):
    svc = _service(request)
    items = svc.list_templates()
    return {"items": [t.model_dump() if hasattr(t, "model_dump") else t for t in items], "active": svc.active_name}


@router.get("/prompts/{name}")
async def get_prompt(name: str, request: Request, variant: Optional[str] = Query(default=None)):
    svc = _service(request)
    pt = svc.get_template(name, variant=variant)
    if pt is None:
        raise HTTPException(status_code=404, detail="prompt not found")
    return pt.model_dump() if hasattr(pt, "model_dump") else pt


@router.post("/prompts")
async def create_prompt(payload: PromptCreateRequest, request: Request):
    svc = _service(request)
    agent = _agent(request)
    name = payload.name or "default"
    template = payload.template or payload.content or payload.text or ""
    pt = svc.add_template(name, template, version=payload.version, variant=payload.variant, weight=payload.weight, metadata=payload.metadata)
    if payload.activate:
        svc.activate(name)
        if agent is not None:
            try:
                agent.set_system_prompt(template, name=name, version=payload.version, variant=payload.variant)
            except Exception:
                pass
    if agent is not None and getattr(svc, "agent", None) is None:
        svc.agent = agent
    return pt.model_dump() if hasattr(pt, "model_dump") else pt


@router.post("/prompts/activate")
async def activate_prompt(payload: PromptActivateRequest, request: Request):
    svc = _service(request)
    agent = _agent(request)
    ok = svc.activate(payload.name)
    if not ok:
        raise HTTPException(status_code=404, detail="prompt not found")
    pt = svc.get_template(payload.name)
    if agent is not None and pt is not None:
        try:
            agent.set_system_prompt(pt.template, name=payload.name, version=pt.version, variant=pt.variant)
        except Exception:
            pass
    return {"status": "ok", "active": svc.active_name}


@router.get("/prompts/export")
async def export_prompts(request: Request):
    svc = _service(request)
    return {"items": svc.export()}


@router.post("/prompts/import")
async def import_prompts(payload: dict, request: Request):
    svc = _service(request)
    items = payload.get("items", payload.get("prompts", payload))
    if not isinstance(items, list):
        items = [items]
    count = svc.import_templates(items)
    return {"status": "ok", "imported": count}