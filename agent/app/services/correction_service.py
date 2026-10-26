"""Correction service: records corrections and feeds them back into the agent."""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CorrectionRecord(BaseModel):
    id: int
    request_id: Optional[str] = None
    words: List[str] = Field(default_factory=list)
    original_sentence: Optional[str] = None
    corrected_sentence: Optional[str] = None
    rating: Optional[Any] = None
    comment: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str
    applied: bool = False

    def model_dump(self, *args, **kwargs):
        # pydantic v2/v1 compat
        if hasattr(super(), "model_dump"):
            return super().model_dump(*args, **kwargs)
        return self.dict(*args, **kwargs)


# aliases
Correction = CorrectionRecord
CorrectionEntry = CorrectionRecord


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tokens(text: Optional[str]) -> List[str]:
    if not text:
        return []
    return [t for t in str(text).replace("\n", " ").split() if t.strip()]


class CorrectionService:
    """In-memory correction store with a simple learning loop."""

    def __init__(
        self,
        agent: Any = None,
        vocabulary: Any = None,
        max_items: int = 10000,
        storage_path: Optional[str] = None,
        learning_enabled: Optional[bool] = None,
        **kwargs: Any,
    ) -> None:
        from app.config import settings

        self.agent = agent
        self.vocabulary = vocabulary
        self.max_items = int(max_items or 10000)
        self.storage_path = storage_path
        self.learning_enabled = (
            bool(getattr(settings, "correction_learning", True))
            if learning_enabled is None
            else bool(learning_enabled)
        )
        self._items: List[CorrectionRecord] = []
        self._correction_map: Dict[str, str] = {}
        self._counter = 0
        self._lock = threading.RLock()
        if storage_path:
            self._load()

    # ------------------------------------------------------------------ #
    # Recording
    # ------------------------------------------------------------------ #
    def record(
        self,
        original_sentence: Optional[str] = None,
        corrected_sentence: Optional[str] = None,
        words: Optional[List[str]] = None,
        rating: Any = None,
        comment: Optional[str] = None,
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        feedback: Any = None,
        **kwargs: Any,
    ) -> CorrectionRecord:
        # accept a feedback object/dict
        if feedback is not None:
            if isinstance(feedback, dict):
                original_sentence = feedback.get("original_sentence", original_sentence)
                corrected_sentence = feedback.get("corrected_sentence", corrected_sentence)
                words = feedback.get("words", words)
                rating = feedback.get("rating", rating)
                comment = feedback.get("comment", comment)
                request_id = feedback.get("request_id", request_id)
                metadata = feedback.get("metadata", metadata)
            else:
                original_sentence = getattr(feedback, "original_sentence", original_sentence)
                corrected_sentence = getattr(feedback, "corrected_sentence", corrected_sentence)
                words = getattr(feedback, "words", words)
                rating = getattr(feedback, "rating", rating)
                comment = getattr(feedback, "comment", comment)
                request_id = getattr(feedback, "request_id", request_id)
                metadata = getattr(feedback, "metadata", metadata)

        words = [str(w).strip() for w in (words or []) if str(w).strip()]
        if not words and original_sentence:
            words = _tokens(original_sentence)
        if not words and corrected_sentence:
            words = _tokens(corrected_sentence)

        with self._lock:
            self._counter += 1
            fid = self._counter
            record = CorrectionRecord(
                id=fid,
                request_id=request_id,
                words=words,
                original_sentence=original_sentence,
                corrected_sentence=corrected_sentence,
                rating=rating,
                comment=comment,
                metadata=dict(metadata or {}),
                created_at=_now(),
                applied=False,
            )
            self._items.append(record)
            if len(self._items) > self.max_items:
                self._items = self._items[-self.max_items :]
            if original_sentence and corrected_sentence:
                self._correction_map[str(original_sentence).strip()] = str(
                    corrected_sentence
                ).strip()

        # learning loop
        if self.learning_enabled:
            self.apply(record, agent=self.agent)

        if self.storage_path:
            self._save()
        return record

    # aliases
    def apply_correction(self, *args, **kwargs):
        # support apply_correction(original, corrected, ...) positional
        if args and isinstance(args[0], str) and len(args) >= 2 and isinstance(args[1], str):
            kwargs.setdefault("original_sentence", args[0])
            kwargs.setdefault("corrected_sentence", args[1])
            args = args[2:]
        return self.record(*args, **kwargs)

    def submit(self, *args, **kwargs):
        return self.record(*args, **kwargs)

    def add(self, *args, **kwargs):
        return self.record(*args, **kwargs)

    def create(self, *args, **kwargs):
        return self.record(*args, **kwargs)

    def add_correction(self, *args, **kwargs):
        return self.record(*args, **kwargs)

    def submit_correction(self, *args, **kwargs):
        return self.record(*args, **kwargs)

    def correct(self, text: Any = None, **kwargs: Any) -> Any:
        if isinstance(text, str):
            # apply known correction if present
            mapped = self._correction_map.get(text.strip())
            if mapped:
                return mapped
            # otherwise record as original? no; return text
            return text
        return self.record(**kwargs) if kwargs else text

    # ------------------------------------------------------------------ #
    # Application / learning loop
    # ------------------------------------------------------------------ #
    def apply(self, record: Any = None, agent: Any = None, **kwargs: Any) -> bool:
        target_agent = agent or self.agent
        rec = record
        if not isinstance(rec, CorrectionRecord):
            rec = self.record(**kwargs) if kwargs else None
        if rec is None:
            return False
        if target_agent is None:
            rec.applied = False
            return False
        try:
            sentence = rec.corrected_sentence or rec.original_sentence
            words = rec.words or _tokens(sentence)
            if sentence and hasattr(target_agent, "add_example"):
                try:
                    target_agent.add_example(words, sentence, intent="statement")
                except Exception:
                    pass
            # add corrected words to vocabulary (best-effort)
            if hasattr(target_agent, "add_vocabulary_word"):
                for w in words:
                    try:
                        target_agent.add_vocabulary_word(w)
                    except Exception:
                        pass
            # update agent vocabulary if service present
            vs = getattr(target_agent, "vocabulary_service", None)
            if vs is not None and hasattr(vs, "add"):
                for w in words:
                    try:
                        vs.add(w)
                    except Exception:
                        pass
            rec.applied = True
            return True
        except Exception:
            rec.applied = False
            return False

    def learn(self, *args, **kwargs):
        if args and not isinstance(args[0], (str, list, tuple, dict)):
            return self.apply(args[0], **kwargs)
        if kwargs.get("feedback") is not None:
            rec = self.record(feedback=kwargs.pop("feedback"))
            return self.apply(rec, **kwargs)
        return self.apply(**kwargs) if kwargs else False

    def learn_from_feedback(self, feedback: Any = None, **kwargs: Any):
        if feedback is not None:
            kwargs.setdefault("feedback", feedback)
        return self.learn(**kwargs)

    def learn_from_correction(self, correction: Any = None, **kwargs: Any):
        return self.learn(correction, **kwargs) if correction is not None else self.learn(**kwargs)

    # ------------------------------------------------------------------ #
    # Query
    # ------------------------------------------------------------------ #
    def get(self, item_id: Any) -> Optional[CorrectionRecord]:
        with self._lock:
            for r in self._items:
                if r.id == item_id:
                    return r
        return None

    def list(
        self, limit: Optional[int] = None, offset: int = 0, **kwargs: Any
    ) -> List[CorrectionRecord]:
        with self._lock:
            items = list(self._items)
        start = max(0, int(offset or 0))
        end = len(items) if limit is None else start + int(limit)
        return items[start:end]

    def all(self) -> List[CorrectionRecord]:
        with self._lock:
            return list(self._items)

    def reset(self) -> None:
        with self._lock:
            self._items.clear()
            self._correction_map.clear()
            self._counter = 0
        if self.storage_path:
            self._save()

    def clear(self) -> None:
        self.reset()

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._items)
            applied = sum(1 for r in self._items if r.applied)
            with_correction = sum(1 for r in self._items if r.corrected_sentence)
        return {"total": total, "applied": applied, "with_correction": with_correction}

    # ------------------------------------------------------------------ #
    # "Did you mean?" suggestions
    # ------------------------------------------------------------------ #
    def did_you_mean(
        self, word: Any, vocabulary: Any = None, n: int = 3, cutoff: float = 0.6, **kwargs: Any
    ) -> List[str]:
        import difflib

        vocab = vocabulary if vocabulary is not None else self.vocabulary
        words = []
        if vocab is None and self.agent is not None:
            vocab = getattr(self.agent, "vocabulary", None)
        # normalize vocabulary to word list
        try:
            from app.core.confidence import vocabulary_words as _vw

            words = _vw(vocab)
        except Exception:
            words = []
        if not words and isinstance(vocab, (list, tuple, set)):
            words = [str(x) for x in vocab]
        target = str(word).strip()
        matches = difflib.get_close_matches(
            target, words, n=int(n or 3), cutoff=float(cutoff or 0.6)
        )
        return matches

    def suggest(self, *args, **kwargs):
        # accept suggest(word) or suggest(word=...)
        word = kwargs.get("word", kwargs.get("text", kwargs.get("value")))
        if word is None and args:
            word = args[0]
        vocabulary = kwargs.get("vocabulary")
        n = kwargs.get("n", kwargs.get("limit", 3))
        return self.did_you_mean(
            word,
            vocabulary=vocabulary,
            n=n,
            **{
                k: v
                for k, v in kwargs.items()
                if k not in {"word", "text", "value", "vocabulary", "n", "limit"}
            },
        )

    def suggestions(self, *args, **kwargs):
        return self.suggest(*args, **kwargs)

    # ------------------------------------------------------------------ #
    # Import / export
    # ------------------------------------------------------------------ #
    def export(self, format: str = "list") -> Any:
        with self._lock:
            items = [r.model_dump() for r in self._items]
        if format in {"json", "dict"}:
            return items
        return items

    def import_items(self, items: Any) -> int:
        count = 0
        for item in items or []:
            try:
                self.record(
                    **(item if isinstance(item, dict) else {"corrected_sentence": str(item)})
                )
                count += 1
            except Exception:
                continue
        return count

    def import_(self, items: Any) -> int:
        return self.import_items(items)

    # ------------------------------------------------------------------ #
    # Persistence (best-effort JSON)
    # ------------------------------------------------------------------ #
    def _load(self) -> None:
        try:
            import json
            from pathlib import Path

            p = Path(self.storage_path)
            if p.exists():
                data = json.loads(p.read_text(encoding="utf-8"))
                for item in data.get("items", data if isinstance(data, list) else []):
                    self.record(**{k: v for k, v in item.items() if k != "id"})
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


# module-level singleton helpers
_DEFAULT_CORRECTION_SERVICE: Optional[CorrectionService] = None


def get_correction_service() -> CorrectionService:
    global _DEFAULT_CORRECTION_SERVICE
    if _DEFAULT_CORRECTION_SERVICE is None:
        _DEFAULT_CORRECTION_SERVICE = CorrectionService()
    return _DEFAULT_CORRECTION_SERVICE


def reset_correction_store() -> None:
    get_correction_service().reset()


# aliases
CorrectionStore = CorrectionService
Corrections = CorrectionService

# extra aliases
CorrectionService.get_all = CorrectionService.all
CorrectionService.list_all = CorrectionService.all
CorrectionService.get_corrections = CorrectionService.all
CorrectionService.get_by_id = CorrectionService.get
CorrectionService.find = CorrectionService.get
CorrectionService.delete_all = CorrectionService.clear
CorrectionService.clear_all = CorrectionService.clear
