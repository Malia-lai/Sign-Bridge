from typing import Any, Dict, List, Optional

from app.config import settings
from app.schemas.response import SentenceResponse


def get_threshold(threshold: Optional[float] = None) -> float:
    return settings.confidence_threshold if threshold is None else float(threshold)


def clamp_confidence(value: Any) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        v = 0.0
    return max(0.0, min(1.0, v))


def below_threshold(confidence: Any, threshold: Optional[float] = None) -> bool:
    return clamp_confidence(confidence) < get_threshold(threshold)


def _as_response(obj: Any) -> SentenceResponse:
    if isinstance(obj, SentenceResponse):
        return obj
    if isinstance(obj, dict):
        return SentenceResponse(**obj)
    raise TypeError("expected SentenceResponse or dict")


def ensure_alternatives(
    obj: Any,
    threshold: Optional[float] = None,
    raw_words: Optional[List[str]] = None,
    min_count: int = 2,
    max_count: int = 3,
) -> Any:
    """Ensure 2-3 alternatives when confidence is below threshold."""
    thr = get_threshold(threshold)
    if isinstance(obj, dict):
        resp = _as_response(obj)
        was_dict = True
    else:
        resp = _as_response(obj)
        was_dict = False

    if below_threshold(resp.confidence, thr):
        alts = list(resp.alternatives or [])
        # pad with a raw-words fallback if needed
        fallback_sentence = " ".join(raw_words or resp.raw_words or []).strip()
        candidates = [a for a in alts if a]
        if fallback_sentence and fallback_sentence not in candidates:
            candidates.append(fallback_sentence)
        # ensure at least min_count by reusing available distinct strings
        i = 0
        pool = [fallback_sentence] if fallback_sentence else ([" ".join(resp.raw_words)] if resp.raw_words else [])
        if not pool and resp.sentence:
            pool = [resp.sentence]
        while len(candidates) < min_count and pool:
            cand = pool[i % len(pool)]
            if cand:
                candidates.append(cand)
            i += 1
            if i > 10:
                break
        # trim to max_count
        candidates = candidates[:max_count]
        resp.alternatives = candidates
    else:
        # still cap
        resp.alternatives = list(resp.alternatives or [])[:max_count]

    return resp.model_dump() if was_dict else resp


def detect_unknown(words: List[str], vocabulary: Any) -> List[str]:
    known = set()
    if isinstance(vocabulary, dict):
        if "words" in vocabulary and isinstance(vocabulary["words"], (list, tuple, set)):
            for item in vocabulary["words"]:
                if isinstance(item, str):
                    known.add(item.lower())
                elif isinstance(item, dict):
                    w = item.get("word") or item.get("text")
                    if w:
                        known.add(str(w).lower())
        else:
            known = {str(k).lower() for k in vocabulary.keys()}
    elif isinstance(vocabulary, (list, tuple, set)):
        for item in vocabulary:
            if isinstance(item, str):
                known.add(item.lower())
            elif isinstance(item, dict):
                w = item.get("word") or item.get("text")
                if w:
                    known.add(str(w).lower())
    unknown = []
    for w in words:
        if str(w).lower() not in known:
            unknown.append(w)
    return unknown


# aliases
is_below_threshold = below_threshold
check_confidence = below_threshold
normalize = clamp_confidence


def vocabulary_words(vocabulary: Any) -> List[str]:
    words = []
    if isinstance(vocabulary, dict):
        if "words" in vocabulary and isinstance(vocabulary["words"], (list, tuple, set)):
            for item in vocabulary["words"]:
                if isinstance(item, str):
                    words.append(item)
                elif isinstance(item, dict):
                    w = item.get("word") or item.get("text")
                    if w:
                        words.append(str(w))
        else:
            words.extend(str(k) for k in vocabulary.keys())
    elif isinstance(vocabulary, (list, tuple, set)):
        for item in vocabulary:
            if isinstance(item, str):
                words.append(item)
            elif isinstance(item, dict):
                w = item.get("word") or item.get("text")
                if w:
                    words.append(str(w))
    return words