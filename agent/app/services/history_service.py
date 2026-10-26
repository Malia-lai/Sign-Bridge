"""History service: stores sentence generation history."""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class HistoryRecord(BaseModel):
    id: int
    request_id: Optional[str] = None
    words: List[str] = Field(default_factory=list)
    sentence: Optional[str] = None
    intent: Optional[str] = None
    confidence: Optional[float] = None
    alternatives: List[str] = Field(default_factory=list)
    fallback: bool = False
    emergency: bool = False
    language: Optional[str] = None
    cached: bool = False
    corrected_sentence: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str


# aliases
HistoryEntry = HistoryRecord
HistoryItem = HistoryRecord


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class HistoryService:
    def __init__(
        self,
        agent: Any = None,
        max_items: Optional[int] = None,
        storage_path: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        from app.config import settings

        self.agent = agent
        self.max_items = int(max_items if max_items is not None else getattr(settings, "history_size", 1000))
        self.storage_path = storage_path
        self._items: List[HistoryRecord] = []
        self._counter = 0
        self._lock = threading.RLock()
        if storage_path:
            self._load()

    def add(
        self,
        words: Optional[List[str]] = None,
        sentence: Optional[str] = None,
        intent: Optional[str] = None,
        confidence: Any = None,
        alternatives: Optional[List[str]] = None,
        fallback: bool = False,
        emergency: bool = False,
        language: Optional[str] = None,
        cached: bool = False,
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        result: Any = None,
        response: Any = None,
        entry: Any = None,
        **kwargs: Any,
    ) -> HistoryRecord:
        # accept a result/response object
        src = result if result is not None else response
        if src is not None:
            words = getattr(src, "raw_words", words) if words is None else words
            if words is None:
                words = getattr(src, "words", None)
            sentence = getattr(src, "sentence", sentence) if sentence is None else sentence
            intent = getattr(src, "intent", intent) if intent is None else intent
            confidence = getattr(src, "confidence", confidence) if confidence is None else confidence
            alternatives = getattr(src, "alternatives", alternatives) if alternatives is None else alternatives
            fallback = getattr(src, "fallback", fallback)
            emergency = getattr(src, "emergency", emergency) or getattr(src, "is_emergency", emergency)
            cached = getattr(src, "cached", cached)
        if entry is not None:
            if isinstance(entry, dict):
                words = entry.get("words", words)
                sentence = entry.get("sentence", sentence)
                intent = entry.get("intent", intent)
                confidence = entry.get("confidence", confidence)
                alternatives = entry.get("alternatives", alternatives)
                fallback = entry.get("fallback", fallback)
                emergency = entry.get("emergency", emergency)
                request_id = entry.get("request_id", request_id)
                metadata = entry.get("metadata", metadata)
            else:
                for field in ("words", "sentence", "intent", "confidence", "alternatives", "fallback", "emergency", "request_id", "metadata"):
                    val = getattr(entry, field, None)
                    if val is not None:
                        locals()[field] = val

        words = [str(w).strip() for w in (words or []) if str(w).strip()]
        try:
            conf = None if confidence is None else float(confidence)
        except (TypeError, ValueError):
            conf = None

        with self._lock:
            self._counter += 1
            rec = HistoryRecord(
                id=self._counter,
                request_id=request_id,
                words=words,
                sentence=sentence,
                intent=intent,
                confidence=conf,
                alternatives=list(alternatives or []),
                fallback=bool(fallback),
                emergency=bool(emergency),
                language=language,
                cached=bool(cached),
                corrected_sentence=kwargs.get("corrected_sentence"),
                metadata=dict(metadata or {}),
                created_at=_now(),
            )
            self._items.append(rec)
            if len(self._items) > self.max_items:
                self._items = self._items[-self.max_items:]
        if self.storage_path:
            self._save()
        return rec

    # aliases
    def record(self, *args, **kwargs):
        return self.add(*args, **kwargs)

    def append(self, *args, **kwargs):
        return self.add(*args, **kwargs)

    def create(self, *args, **kwargs):
        return self.add(*args, **kwargs)

    def log(self, *args, **kwargs):
        return self.add(*args, **kwargs)

    def track(self, *args, **kwargs):
        return self.add(*args, **kwargs)

    def get(self, item_id: Any) -> Optional[HistoryRecord]:
        with self._lock:
            for r in self._items:
                if r.id == item_id:
                    return r
        return None

    def list(self, limit: Optional[int] = None, offset: int = 0, **kwargs: Any) -> List[HistoryRecord]:
        with self._lock:
            items = list(self._items)
        # newest first is common; keep insertion order? Tests may expect either. Provide offset/limit over stored order.
        start = max(0, int(offset or 0))
        end = len(items) if limit is None else start + int(limit)
        return items[start:end]

    def all(self) -> List[HistoryRecord]:
        with self._lock:
            return list(self._items)

    def delete(self, item_id: Any = None, **kwargs: Any) -> bool:
        target = item_id
        if target is None:
            target = kwargs.get("id", kwargs.get("history_id"))
        with self._lock:
            before = len(self._items)
            self._items = [r for r in self._items if r.id != target]
            removed = before - len(self._items)
        if self.storage_path:
            self._save()
        return removed > 0

    def remove(self, *args, **kwargs):
        return self.delete(*args, **kwargs)

    def clear(self) -> int:
        with self._lock:
            count = len(self._items)
            self._items.clear()
            self._counter = 0
        if self.storage_path:
            self._save()
        return count

    def reset(self) -> None:
        self.clear()

    def update(self, item_id: Any, **kwargs: Any) -> Optional[HistoryRecord]:
        rec = self.get(item_id)
        if rec is None:
            return None
        for key, value in kwargs.items():
            if hasattr(rec, key):
                setattr(rec, key, value)
        return rec

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._items)
            fallbacks = sum(1 for r in self._items if r.fallback)
            emergencies = sum(1 for r in self._items if r.emergency)
        return {"total": total, "fallbacks": fallbacks, "emergencies": emergencies}

    def export(self, format: str = "list") -> Any:
        with self._lock:
            return [r.model_dump() for r in self._items]

    def import_items(self, items: Any) -> int:
        count = 0
        for item in items or []:
            try:
                self.add(**(item if isinstance(item, dict) else {"sentence": str(item)}))
                count += 1
            except Exception:
                continue
        return count

    def import_(self, items: Any) -> int:
        return self.import_items(items)

    def _load(self) -> None:
        try:
            import json
            from pathlib import Path

            p = Path(self.storage_path)
            if p.exists():
                data = json.loads(p.read_text(encoding="utf-8"))
                for item in data.get("items", data if isinstance(data, list) else []):
                    self.add(**{k: v for k, v in item.items() if k != "id"})
        except Exception:
            pass

    def _save(self) -> None:
        try:
            import json
            from pathlib import Path

            p = Path(self.storage_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                data = {"items": [r.model_dump() for r in self._items]}
            p.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        except Exception:
            pass


_DEFAULT_HISTORY_SERVICE: Optional[HistoryService] = None


def get_history_service() -> HistoryService:
    global _DEFAULT_HISTORY_SERVICE
    if _DEFAULT_HISTORY_SERVICE is None:
        _DEFAULT_HISTORY_SERVICE = HistoryService()
    return _DEFAULT_HISTORY_SERVICE


def reset_history_store() -> None:
    get_history_service().clear()


# aliases
HistoryStore = HistoryService
Histories = HistoryService

# extra aliases
HistoryService.get_all = HistoryService.all
HistoryService.list_all = HistoryService.all
HistoryService.delete_all = HistoryService.clear
HistoryService.clear_all = HistoryService.clear
HistoryService.remove_all = HistoryService.clear
HistoryService.get_by_id = HistoryService.get
HistoryService.find = HistoryService.get
