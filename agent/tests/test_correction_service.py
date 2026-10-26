import os

os.environ.setdefault("MOCK_MODE", "true")

from app.services.correction_service import (
    CorrectionService,
    get_correction_service,
    reset_correction_store,
)


def test_correction_record_and_list():
    reset_correction_store()
    svc = get_correction_service()
    rec = svc.record(
        words=["me", "water"], original_sentence="me water", corrected_sentence="I want water."
    )
    assert rec.id >= 1
    assert svc.get(rec.id) is not None
    assert len(svc.list()) == 1
    assert len(svc.all()) == 1


def test_correction_apply_learning(agent):
    reset_correction_store()
    svc = CorrectionService(agent=agent, learning_enabled=True)
    rec = svc.record(
        words=["me", "water"], original_sentence="me water", corrected_sentence="I want water."
    )
    assert rec.applied is True
    # example added
    assert any("I want water." in str(ex.get("sentence")) for ex in (agent.examples or []))


def test_correction_did_you_mean():
    reset_correction_store()
    svc = CorrectionService(vocabulary={"words": [{"word": "water", "tags": []}]})
    assert "water" in svc.did_you_mean("watre", n=3)


def test_correction_stats_export_import():
    reset_correction_store()
    svc = get_correction_service()
    svc.record(words=["a"], corrected_sentence="A.")
    st = svc.stats()
    assert st["total"] == 1
    data = svc.export()
    assert isinstance(data, list)
    n = svc.import_items([{"words": ["b"], "corrected_sentence": "B."}])
    assert n == 1


def test_correction_clear_reset():
    reset_correction_store()
    svc = get_correction_service()
    svc.record(words=["a"], corrected_sentence="A.")
    svc.clear()
    assert svc.list() == []
    svc.record(words=["b"], corrected_sentence="B.")
    svc.reset()
    assert svc.list() == []


def test_correction_correct_method():
    reset_correction_store()
    svc = get_correction_service()
    svc.record(original_sentence="hi", corrected_sentence="hello")
    assert svc.correct("hi") == "hello"
    assert svc.correct("unknown") == "unknown"


def test_correction_learn_feedback(agent):
    reset_correction_store()
    svc = CorrectionService(agent=agent)
    fb = {"words": ["me"], "original_sentence": "me", "corrected_sentence": "I", "rating": 5}
    assert svc.learn(feedback=fb) is True
