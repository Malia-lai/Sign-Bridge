import os

os.environ.setdefault("MOCK_MODE", "true")

from app.core.confidence import below_threshold, clamp_confidence, ensure_alternatives
from app.schemas.response import SentenceResponse


def test_clamp():
    assert clamp_confidence(1.5) == 1.0
    assert clamp_confidence(-0.2) == 0.0


def test_below_threshold():
    assert below_threshold(0.5, 0.7) is True
    assert below_threshold(0.9, 0.7) is False


def test_ensure_alternatives():
    resp = SentenceResponse(sentence="hi", intent="statement", confidence=0.2, alternatives=[])
    out = ensure_alternatives(resp, threshold=0.7, raw_words=["hi"])
    assert len(out.alternatives) >= 2
    assert len(out.alternatives) <= 3
