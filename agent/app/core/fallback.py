from typing import Any, List, Optional

from app.schemas.response import SentenceResponse
from app.core.confidence import clamp_confidence


def detect_emergency(words: List[str], vocabulary: Any) -> bool:
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
    reasons = list(fallback_reasons) if fallback_reasons else ([fallback_reason] if fallback_reason else [])
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
    return build_fallback(words, unknown_words=unknown_words, **{k: v for k, v in kwargs.items() if k in {"confidence", "intent", "fallback", "fallback_reason"}})