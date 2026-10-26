"""Feedback service: storage, aggregation, metrics, and learning loop."""

from __future__ import annotations

import csv
import io
import json
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.schemas.feedback import FeedbackCreate, FeedbackRecord, FeedbackResponse, FeedbackStats
from app.utils.timing import *  # noqa: F401,F403


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def _normalize_rating(value: Any) -> Optional[float]:
    v = _to_number(value)
    if v is None:
        return None
    # normalize 1-5 ratings to 0-1 when needed
    if v > 1.0:
        v = v / 5.0
    return max(0.0, min(1.0, v))


class FeedbackService:
    def __init__(
        self,
        agent: Any = None,
        repository: Any = None,
        max_items: int = 100000,
        storage_path: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        self.agent = agent
        self.repository = repository
        self.max_items = int(max_items or 100000)
        self.storage_path = storage_path
        self._items: List[FeedbackRecord] = []
        self._counter = 0
        self._lock = threading.RLock()

    # ------------------------------------------------------------------ #
    # Storage
    # ------------------------------------------------------------------ #
    def record(self, payload: Any = None, **kwargs: Any) -> FeedbackRecord:
        if payload is not None and not isinstance(payload, dict):
            # pydantic model or object
            try:
                kwargs = {**payload.model_dump(), **kwargs}
                payload = None
            except Exception:
                try:
                    kwargs = {**payload.dict(), **kwargs}
                    payload = None
                except Exception:
                    pass
        if payload is not None and isinstance(payload, dict):
            kwargs = {**payload, **kwargs}

        request_id = kwargs.get("request_id")
        words = kwargs.get("words", [])
        words = [str(w).strip() for w in (words or []) if str(w).strip()]
        original_sentence = kwargs.get("original_sentence")
        corrected_sentence = kwargs.get("corrected_sentence")
        rating = kwargs.get("rating")
        comment = kwargs.get("comment")
        metadata = kwargs.get("metadata", {})

        with self._lock:
            self._counter += 1
            fid = self._counter
            record = FeedbackRecord(
                id=fid,
                request_id=request_id,
                words=words,
                original_sentence=original_sentence,
                corrected_sentence=corrected_sentence,
                rating=rating,
                comment=comment,
                metadata=dict(metadata or {}),
                created_at=_now(),
            )
            self._items.append(record)
            if len(self._items) > self.max_items:
                self._items = self._items[-self.max_items:]

        # learning loop
        self._apply_learning(record)
        return record

    # aliases
    def submit(self, *a, **k):
        return self.record(*a, **k)

    def create(self, *a, **k):
        return self.record(*a, **k)

    def add(self, *a, **k):
        return self.record(*a, **k)

    def store(self, *a, **k):
        return self.record(*a, **k)

    def submit_feedback(self, *a, **k):
        return self.record(*a, **k)

    def get(self, item_id: Any) -> Optional[FeedbackRecord]:
        with self._lock:
            for r in self._items:
                if r.id == item_id:
                    return r
        return None

    def get_by_id(self, item_id: Any) -> Optional[FeedbackRecord]:
        return self.get(item_id)

    def list(self, limit: Optional[int] = None, offset: int = 0, **kwargs: Any) -> List[FeedbackRecord]:
        with self._lock:
            items = list(self._items)
        start = max(0, int(offset or 0))
        end = len(items) if limit is None else start + int(limit)
        return items[start:end]

    def all(self) -> List[FeedbackRecord]:
        with self._lock:
            return list(self._items)

    def delete(self, item_id: Any) -> bool:
        with self._lock:
            before = len(self._items)
            self._items[:] = [r for r in self._items if r.id != item_id]
            return len(self._items) < before

    def remove(self, *a, **k):
        return self.delete(*a, **k)

    def clear(self) -> int:
        with self._lock:
            count = len(self._items)
            self._items.clear()
            self._counter = 0
        return count

    def reset(self) -> None:
        self.clear()

    # ------------------------------------------------------------------ #
    # Stats / aggregation
    # ------------------------------------------------------------------ #
    def stats(self) -> FeedbackStats:
        with self._lock:
            records = list(self._items)
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

    def aggregate(self) -> Dict[str, Any]:
        with self._lock:
            records = list(self._items)
        by_words: Dict[str, Dict[str, Any]] = {}
        for r in records:
            key = " ".join(r.words)
            entry = by_words.setdefault(key, {"count": 0, "ratings": [], "corrections": [], "originals": []})
            entry["count"] += 1
            v = _to_number(r.rating)
            if v is not None:
                entry["ratings"].append(v)
            if r.corrected_sentence:
                entry["corrections"].append(r.corrected_sentence)
            if r.original_sentence:
                entry["originals"].append(r.original_sentence)
        for key, entry in by_words.items():
            rs = entry["ratings"]
            entry["average_rating"] = (sum(rs) / len(rs)) if rs else None
            entry["correction_count"] = len(entry["corrections"])
        top_corrections = []
        for r in records:
            if r.corrected_sentence:
                top_corrections.append(
                    {
                        "words": r.words,
                        "original": r.original_sentence,
                        "corrected": r.corrected_sentence,
                        "rating": r.rating,
                    }
                )
        return {
            "total": len(records),
            "by_words": by_words,
            "top_corrections": top_corrections,
        }

    def accuracy_metrics(self) -> Dict[str, Any]:
        with self._lock:
            records = list(self._items)
        total = len(records)
        rated = [r for r in records if _to_number(r.rating) is not None]
        corrected = [r for r in records if r.corrected_sentence]
        high = [r for r in rated if (_normalize_rating(r.rating) or 0.0) >= 0.8]
        avg_rating = None
        if rated:
            avg_rating = sum(_to_number(r.rating) for r in rated) / len(rated)
        return {
            "total_feedback": total,
            "rated_count": len(rated),
            "corrected_count": len(corrected),
            "high_rating_count": len(high),
            "average_rating": avg_rating,
            "correction_rate": (len(corrected) / total) if total else 0.0,
            "high_rating_rate": (len(high) / len(rated)) if rated else 0.0,
            "accuracy": (len(high) / len(rated)) if rated else 0.0,
        }

    # alias
    def metrics(self) -> Dict[str, Any]:
        return self.accuracy_metrics()

    def compute_accuracy(self) -> Dict[str, Any]:
        return self.accuracy_metrics()

    # ------------------------------------------------------------------ #
    # Confidence calibration
    # ------------------------------------------------------------------ #
    def calibrate_confidence(self, confidence: Any, words: Optional[List[str]] = None, ratings: Optional[List[Any]] = None) -> float:
        from app.core.confidence import clamp_confidence

        base = clamp_confidence(confidence)
        relevant_ratings = list(ratings or [])
        if not relevant_ratings:
            with self._lock:
                for r in self._items:
                    if words and r.words != [str(w).strip() for w in words if str(w).strip()]:
                        continue
                    if r.rating is not None:
                        relevant_ratings.append(r.rating)
        if not relevant_ratings:
            return base
        norm = [_normalize_rating(x) for x in relevant_ratings]
        norm = [x for x in norm if x is not None]
        if not norm:
            return base
        avg = sum(norm) / len(norm)
        # blend base confidence with feedback-derived expectation
        calibrated = (base + avg) / 2.0
        return clamp_confidence(calibrated)

    # ------------------------------------------------------------------ #
    # Prompt tuning / learning loop
    # ------------------------------------------------------------------ #
    def _apply_learning(self, record: FeedbackRecord) -> None:
        agent = self.agent
        if agent is None:
            return
        # feed corrections as examples
        if record.corrected_sentence:
            try:
                if hasattr(agent, "add_example"):
                    agent.add_example(record.words, record.corrected_sentence, intent="statement")
            except Exception:
                pass
        # update vocabulary with corrected words
        if hasattr(agent, "add_vocabulary_word"):
            for w in record.words:
                try:
                    agent.add_vocabulary_word(w)
                except Exception:
                    pass
        # delegate to correction service if present
        cs = getattr(agent, "correction_service", None)
        if cs is not None and hasattr(cs, "record"):
            try:
                cs.record(
                    request_id=record.request_id,
                    words=record.words,
                    original_sentence=record.original_sentence,
                    corrected_sentence=record.corrected_sentence,
                    rating=record.rating,
                    comment=record.comment,
                    metadata=record.metadata,
                    agent=agent,
                )
            except Exception:
                pass

    def apply_feedback_to_prompt(self, agent: Any = None, prompt_service: Any = None) -> int:
        target_agent = agent or self.agent
        ps = prompt_service or getattr(target_agent, "prompt_service", None)
        count = 0
        with self._lock:
            records = [r for r in self._items if r.corrected_sentence]
        for r in records:
            if target_agent is not None and hasattr(target_agent, "add_example"):
                try:
                    target_agent.add_example(r.words, r.corrected_sentence, intent="statement")
                    count += 1
                except Exception:
                    pass
        # store aggregate summary in prompt service metadata if available
        if ps is not None:
            try:
                ps.add_template(
                    "learned",
                    "\n".join(r.corrected_sentence for r in records if r.corrected_sentence),
                    version="feedback",
                    metadata={"source": "feedback", "count": len(records)},
                )
            except Exception:
                pass
        return count

    def apply_prompt_improvements(self, *a, **k):
        return self.apply_feedback_to_prompt(*a, **k)

    def tune_prompts(self, *a, **k):
        return self.apply_feedback_to_prompt(*a, **k)

    # ------------------------------------------------------------------ #
    # Export
    # ------------------------------------------------------------------ #
    def export(self, format: str = "json") -> Any:
        with self._lock:
            records = [r.model_dump() for r in self._items]
        if format in {"json", "list", "dict"}:
            return records
        if format in {"jsonl", "ndjson"}:
            return "\n".join(json.dumps(r, default=str) for r in records)
        if format == "csv":
            if not records:
                return ""
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=list(records[0].keys()))
            writer.writeheader()
            for r in records:
                writer.writerow({k: (json.dumps(v) if isinstance(v, (list, dict)) else v) for k, v in r.items()})
            return buf.getvalue()
        if format in {"dataset", "training"}:
            return {
                "data": records,
                "metadata": {
                    "count": len(records),
                    "exported_at": _now(),
                    "source": "feedback",
                },
            }
        return records

    def export_dataset(self, *a, **k):
        return self.export(format="dataset", *a, **k)

    def export_feedback_dataset(self, *a, **k):
        return self.export(format="dataset", *a, **k)

    # ------------------------------------------------------------------ #
    # Suggestions
    # ------------------------------------------------------------------ #
    def suggest(self, word: Any, vocabulary: Any = None, n: int = 3) -> List[str]:
        if self.agent is not None and hasattr(self.agent, "correction_service"):
            cs = self.agent.correction_service
            if cs is not None and hasattr(cs, "did_you_mean"):
                try:
                    return cs.did_you_mean(word, vocabulary=vocabulary, n=n)
                except Exception:
                    pass
        # fallback simple difflib
        import difflib

        vocab_words = []
        try:
            from app.core.confidence import vocabulary_words as _vw

            vocab_words = _vw(vocabulary)
        except Exception:
            pass
        return difflib.get_close_matches(str(word), vocab_words, n=n)

    def did_you_mean(self, *a, **k):
        return self.suggest(*a, **k)

    # ------------------------------------------------------------------ #
    # Import
    # ------------------------------------------------------------------ #
    def import_feedback(self, items: Any) -> int:
        count = 0
        for item in items or []:
            try:
                self.record(**(item if isinstance(item, dict) else {"comment": str(item)}))
                count += 1
            except Exception:
                continue
        return count

    def import_(self, *a, **k):
        return self.import_feedback(*a, **k)


# module-level helpers
_DEFAULT_FEEDBACK_SERVICE: Optional[FeedbackService] = None


def get_feedback_service() -> FeedbackService:
    global _DEFAULT_FEEDBACK_SERVICE
    if _DEFAULT_FEEDBACK_SERVICE is None:
        _DEFAULT_FEEDBACK_SERVICE = FeedbackService()
    return _DEFAULT_FEEDBACK_SERVICE


def reset_feedback_service() -> None:
    get_feedback_service().clear()


# aliases
FeedbackStore = FeedbackService
FeedbackManager = FeedbackService