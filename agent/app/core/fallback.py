from typing import Any, List, Optional

from app.config import settings
from app.core.confidence import clamp_confidence
from app.schemas.response import SentenceResponse


def _extra_emergency_keywords(extra: Any = None) -> set:
    words = set()
    # settings
    raw = getattr(settings, "emergency_keywords", "") or ""
    for part in str(raw).split(","):
        part = part.strip().lower()
        if part:
            words.add(part)
    # extra arg
    if extra is None:
        return words
    if isinstance(extra, str):
        for part in extra.split(","):
            part = part.strip().lower()
            if part:
                words.add(part)
    elif isinstance(extra, (list, tuple, set)):
        for item in extra:
            if isinstance(item, str):
                for part in item.split(","):
                    part = part.strip().lower()
                    if part:
                        words.add(part)
            else:
                words.add(str(item).lower())
    return words


def detect_emergency(
    words: List[str],
    vocabulary: Any = None,
    emergency_keywords: Any = None,
    keywords: Any = None,
    extra: Any = None,
    **kwargs: Any,
) -> bool:
    # accept various kw names
    if emergency_keywords is None:
        emergency_keywords = kwargs.get("emergency_keywords", kwargs.get("keywords", keywords))
    if emergency_keywords is None:
        emergency_keywords = extra
    emergency_words = set()
    if isinstance(vocabulary, dict):
        if "words" in vocabulary and isinstance(vocabulary["words"], (list, tuple, set)):
            for item in vocabulary["words"]:
                if isinstance(item, dict):
                    w = item.get("word") or item.get("text")
                    tags = item.get("tags") or []
                    if w and "emergency" in [str(t).lower() for t in tags]:
                        emergency_words.add(str(w).lower())
        else:
            for key, value in vocabulary.items():
                tags = []
                if isinstance(value, dict):
                    tags = value.get("tags") or []
                if "emergency" in [str(t).lower() for t in tags]:
                    emergency_words.add(str(key).lower())
    elif isinstance(vocabulary, (list, tuple, set)):
        for item in vocabulary:
            if isinstance(item, dict):
                w = item.get("word") or item.get("text")
                tags = item.get("tags") or []
                if w and "emergency" in [str(t).lower() for t in tags]:
                    emergency_words.add(str(w).lower())
    emergency_words = emergency_words | _extra_emergency_keywords(emergency_keywords)
    return any(str(w).lower() in emergency_words for w in (words or []))


def build_fallback(
    words: List[str],
    unknown_words: Optional[List[str]] = None,
    confidence: float = 0.1,
    intent: str = "statement",
    fallback: bool = True,
    fallback_reason: Optional[str] = None,
    emergency: bool = False,
    fallback_reasons: Optional[List[str]] = None,
) -> SentenceResponse:
    sentence = " ".join(w for w in (words or []) if str(w).strip()).strip()
    reasons = (
        list(fallback_reasons)
        if fallback_reasons
        else ([fallback_reason] if fallback_reason else [])
    )
    if emergency and "emergency" not in reasons:
        reasons = reasons + ["emergency"]
    return SentenceResponse(
        sentence=sentence,
        intent=intent,
        confidence=clamp_confidence(confidence),
        alternatives=[],
        fallback=fallback,
        fallback_reason=fallback_reason,
        unknown_words=list(unknown_words or []),
        raw_words=list(words or []),
        emergency=emergency,
        emergency_fallback=emergency,
        is_emergency=emergency,
        emergency_flag=emergency,
        fallback_reasons=reasons,
    )


def fallback_response(words, unknown_words=None, **kwargs):
    return build_fallback(
        words,
        unknown_words=unknown_words,
        **{
            k: v
            for k, v in kwargs.items()
            if k in {"confidence", "intent", "fallback", "fallback_reason"}
        },
    )
