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


def _distinct_alternatives(candidates: List[str], max_count: int) -> List[str]:
    out: List[str] = []
    seen = set()
    for c in candidates:
        c = (c or "").strip()
        if not c:
            continue
        if c in seen:
            continue
        seen.add(c)
        out.append(c)
        if len(out) >= max_count:
            break
    return out


def ensure_alternatives(
    obj: Any,
    threshold: Optional[float] = None,
    raw_words: Optional[List[str]] = None,
    min_count: int = 2,
    max_count: int = 3,
) -> Any:
    """Ensure 2-3 distinct, meaningful alternatives when confidence is below threshold."""
    thr = get_threshold(threshold)
    if isinstance(obj, dict):
        resp = _as_response(obj)
        was_dict = True
    else:
        resp = _as_response(obj)
        was_dict = False

    words = list(raw_words or resp.raw_words or [])
    fallback_sentence = " ".join(w for w in words if str(w).strip()).strip()
    if fallback_sentence and fallback_sentence != resp.sentence:
        # capitalize nicely
        fallback_sentence = fallback_sentence[0].upper() + fallback_sentence[1:] if fallback_sentence else fallback_sentence

    if below_threshold(resp.confidence, thr):
        candidates: List[str] = []
        # LLM-provided alternatives first
        for a in (resp.alternatives or []):
            candidates.append(str(a))
        # the generated sentence itself is a meaningful option
        if resp.sentence:
            candidates.append(resp.sentence)
        # a direct words-as-sentence fallback
        if fallback_sentence:
            candidates.append(fallback_sentence)
        # meaningful variants: question/statement phrasings if not already present
        if words:
            variant = " ".join(words).strip()
            if variant and variant != fallback_sentence:
                candidates.append(variant[0].upper() + variant[1:] if variant else variant)
        # pad with distinct, non-empty placeholders only if truly needed
        i = 1
        base = resp.sentence or fallback_sentence or " ".join(words)
        while len(_distinct_alternatives(candidates, max_count)) < min_count and base:
            cand = f"{base}".strip()
            if i > 1:
                cand = f"{base} ({i})"
            candidates.append(cand)
            i += 1
            if i > 10:
                break

        candidates = _distinct_alternatives(candidates, max_count)
        resp.alternatives = candidates
    else:
        # still dedupe + cap
        resp.alternatives = _distinct_alternatives(list(resp.alternatives or []), max_count)

    return resp.model_dump() if was_dict else resp


def aggregate_confidence(confidences: Any, method: str = "mean") -> float:
    vals = []
    for c in (confidences or []):
        vals.append(clamp_confidence(c))
    if not vals:
        return 1.0
    method = (method or "mean").lower()
    if method in {"min", "minimum"}:
        return min(vals)
    if method in {"max", "maximum"}:
        return max(vals)
    if method in {"product", "prod"}:
        result = 1.0
        for v in vals:
            result *= v
        return clamp_confidence(result)
    # default mean
    return clamp_confidence(sum(vals) / len(vals))


# aliases
aggregate_word_confidence = aggregate_confidence
aggregate_word_confidences = aggregate_confidence
aggregate_confidences = aggregate_confidence
aggregate = aggregate_confidence
combine_confidences = aggregate_confidence
mean_confidence = lambda c: aggregate_confidence(c, "mean")
min_confidence = lambda c: aggregate_confidence(c, "min")
max_confidence = lambda c: aggregate_confidence(c, "max")


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