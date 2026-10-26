"""Prompt template service: loadable templates with optional A/B testing."""

from __future__ import annotations

import hashlib
import json
import random
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PromptTemplate(BaseModel):
    name: str
    template: str
    version: Optional[str] = None
    variant: Optional[str] = None
    weight: float = 1.0
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# aliases
Prompt = PromptTemplate
Template = PromptTemplate


class PromptService:
    def __init__(
        self,
        agent: Any = None,
        template: Optional[str] = None,
        path: Optional[str] = None,
        templates_dir: Optional[str] = None,
        ab_enabled: Optional[bool] = None,
        variants: Any = None,
        **kwargs: Any,
    ) -> None:
        from app.config import settings

        self.agent = agent
        self.templates: Dict[str, PromptTemplate] = {}
        self.active_name = "default"
        self.ab_enabled = bool(
            getattr(settings, "prompt_ab_enabled", False) if ab_enabled is None else ab_enabled
        )
        variants_raw = variants if variants is not None else getattr(settings, "prompt_variants", "A,B")
        if isinstance(variants_raw, str):
            self.variants = [v.strip() for v in variants_raw.split(",") if v.strip()]
        else:
            self.variants = list(variants_raw or [])
        self.weights: Dict[str, float] = {v: 1.0 for v in self.variants}
        self._lock = threading.RLock()

        # initial template
        initial = template
        if initial is None and path:
            try:
                initial = Path(path).read_text(encoding="utf-8")
            except Exception:
                initial = None
        if initial is None:
            p = path or getattr(settings, "prompt_template_path", "")
            if p:
                try:
                    initial = Path(p).read_text(encoding="utf-8")
                except Exception:
                    initial = None
        if initial is None:
            try:
                from app.core.agent import load_system_prompt, PROMPTS_DIR

                initial = load_system_prompt()
            except Exception:
                initial = ""
        self.add_template("default", initial or "", version="default", variant=self.variants[0] if self.variants else None)

        # load additional templates from directory
        d = templates_dir or getattr(settings, "prompt_templates_dir", "")
        if d:
            self.load_dir(d)

    # ------------------------------------------------------------------ #
    # Template CRUD
    # ------------------------------------------------------------------ #
    def add_template(self, name: str, template: str, version: Optional[str] = None, variant: Optional[str] = None, weight: float = 1.0, metadata: Optional[Dict[str, Any]] = None, **kwargs: Any) -> PromptTemplate:
        with self._lock:
            pt = PromptTemplate(
                name=name,
                template=template,
                version=version,
                variant=variant,
                weight=float(weight or 1.0),
                metadata=dict(metadata or {}),
            )
            self.templates[name] = pt
            return pt

    def set_template(self, *args, **kwargs):
        # set_template(name, template) or set_template(template=..., name=...)
        name = kwargs.get("name", kwargs.get("key"))
        template = kwargs.get("template", kwargs.get("content", kwargs.get("text")))
        if name is None and len(args) >= 1 and isinstance(args[0], str) and (len(args) == 1 or not isinstance(args[1], str)):
            # could be set_template(template) for default
            if len(args) == 1:
                name = self.active_name
                template = args[0]
            else:
                name = args[0]
                template = args[1] if len(args) > 1 else template
        if len(args) >= 2 and isinstance(args[0], str) and isinstance(args[1], str):
            name = args[0]
            template = args[1]
        if name is None:
            name = self.active_name
        if template is None:
            template = ""
        return self.add_template(name, template, version=kwargs.get("version"), variant=kwargs.get("variant"), weight=kwargs.get("weight", 1.0), metadata=kwargs.get("metadata"))

    def get_template(self, name: Optional[str] = None, variant: Optional[str] = None) -> Optional[PromptTemplate]:
        with self._lock:
            if name is None:
                name = self.active_name
            pt = self.templates.get(name)
            if pt is None and name in self.templates:
                pt = self.templates[name]
            # variant handling: if variant specified, look for template named "{name}:{variant}" or with matching variant
            if variant is not None:
                for key, t in self.templates.items():
                    if t.variant == variant and (name is None or key.startswith(str(name))):
                        return t
                if f"{name}:{variant}" in self.templates:
                    return self.templates[f"{name}:{variant}"]
            return pt

    def get(self, *args, **kwargs):
        name = kwargs.get("name", kwargs.get("key"))
        variant = kwargs.get("variant")
        if name is None and args:
            name = args[0]
        if variant is None and len(args) > 1:
            variant = args[1]
        return self.get_template(name=name, variant=variant)

    def list_templates(self) -> List[PromptTemplate]:
        with self._lock:
            return list(self.templates.values())

    def list(self) -> List[PromptTemplate]:
        return self.list_templates()

    def all(self) -> List[PromptTemplate]:
        return self.list_templates()

    def delete(self, name: str) -> bool:
        with self._lock:
            if name in self.templates and name != "default":
                del self.templates[name]
                return True
        return False

    def remove(self, name: str) -> bool:
        return self.delete(name)

    def activate(self, name: str) -> bool:
        with self._lock:
            if name in self.templates:
                self.active_name = name
                return True
        return False

    def active(self) -> Optional[PromptTemplate]:
        return self.get_template(self.active_name)

    # ------------------------------------------------------------------ #
    # Loading
    # ------------------------------------------------------------------ #
    def load_file(self, path: str, name: Optional[str] = None) -> Optional[PromptTemplate]:
        try:
            template = Path(path).read_text(encoding="utf-8")
        except Exception:
            return None
        name = name or Path(path).stem
        return self.add_template(name, template, version=path)

    def load_path(self, path: str, name: Optional[str] = None):
        return self.load_file(path, name=name)

    def load_dir(self, directory: str) -> int:
        count = 0
        try:
            for p in Path(directory).glob("*"):
                if p.is_file() and p.suffix in {".txt", ".md", ".prompt", ".jinja", ".j2"}:
                    if self.load_file(str(p)) is not None:
                        count += 1
        except Exception:
            pass
        return count

    def load_from_config(self) -> None:
        from app.config import settings

        p = getattr(settings, "prompt_template_path", "")
        if p:
            self.load_file(p, name="config")
        d = getattr(settings, "prompt_templates_dir", "")
        if d:
            self.load_dir(d)

    def load_from_db(self, db: Any = None) -> None:
        # placeholder for Phase 6 DB integration
        return None

    # ------------------------------------------------------------------ #
    # A/B testing
    # ------------------------------------------------------------------ #
    def set_weights(self, weights: Dict[str, float]) -> None:
        with self._lock:
            for k, v in (weights or {}).items():
                self.weights[k] = float(v)

    def select_variant(self, key: Any = None, context: Any = None, **kwargs: Any) -> str:
        if not self.ab_enabled or not self.variants:
            return self.variants[0] if self.variants else "default"
        # deterministic selection by key if provided
        if key is not None:
            try:
                idx = int(hashlib.md5(str(key).encode()).hexdigest(), 16) % len(self.variants)
                return self.variants[idx]
            except Exception:
                pass
        # weighted random
        try:
            population = []
            for v in self.variants:
                population.extend([v] * max(1, int(self.weights.get(v, 1.0) * 100)))
            return random.choice(population) if population else self.variants[0]
        except Exception:
            return random.choice(self.variants)

    def ab_variant(self, *args, **kwargs):
        return self.select_variant(*args, **kwargs)

    # ------------------------------------------------------------------ #
    # Rendering helpers
    # ------------------------------------------------------------------ #
    def render(self, name: Optional[str] = None, language: Optional[str] = None, vocabulary: Any = None, examples: Any = None, **kwargs: Any) -> str:
        pt = self.get_template(name)
        template = pt.template if pt else ""
        # simple placeholder replacement
        text = template
        if language is not None:
            text = text.replace("{output_language}", str(language))
        return text

    def get_text(self, name: Optional[str] = None, variant: Optional[str] = None, **kwargs: Any) -> str:
        pt = self.get_template(name, variant=variant)
        return pt.template if pt else ""

    # ------------------------------------------------------------------ #
    # Import / export
    # ------------------------------------------------------------------ #
    def export(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [t.model_dump() for t in self.templates.values()]

    def import_templates(self, items: Any) -> int:
        count = 0
        for item in items or []:
            try:
                if isinstance(item, dict):
                    self.add_template(
                        item.get("name", f"imported_{count}"),
                        item.get("template", item.get("content", "")),
                        version=item.get("version"),
                        variant=item.get("variant"),
                        weight=item.get("weight", 1.0),
                        metadata=item.get("metadata", {}),
                    )
                else:
                    self.add_template(f"imported_{count}", str(item))
                count += 1
            except Exception:
                continue
        return count


_DEFAULT_PROMPT_SERVICE: Optional[PromptService] = None


def get_prompt_service() -> PromptService:
    global _DEFAULT_PROMPT_SERVICE
    if _DEFAULT_PROMPT_SERVICE is None:
        _DEFAULT_PROMPT_SERVICE = PromptService()
    return _DEFAULT_PROMPT_SERVICE


def reset_prompt_store() -> None:
    svc = get_prompt_service()
    svc.templates.clear()
    svc.add_template("default", "")


PromptStore = PromptService
PromptManager = PromptService

# extra aliases
PromptService.get_all = PromptService.list_templates
PromptService.list_all = PromptService.list_templates
PromptService.create = PromptService.add_template
PromptService.add = PromptService.add_template
PromptService.get_by_name = PromptService.get_template
PromptService.find = PromptService.get_template
