import os

os.environ.setdefault("MOCK_MODE", "true")

from app.services.feedback_service import (
    get_feedback_service,
    reset_feedback_service,
)


def test_feedback_record_and_list():
    reset_feedback_service()
    svc = get_feedback_service()
    rec = svc.record(words=["me", "water"], rating=5, corrected_sentence="I want water.")
    assert rec.id >= 1
    assert svc.get(rec.id) is not None
    assert len(svc.list()) == 1
    assert len(svc.all()) == 1


def test_feedback_stats():
    reset_feedback_service()
    svc = get_feedback_service()
    svc.record(words=["a"], rating=5)
    svc.record(words=["b"], rating=1)
    st = svc.stats()
    assert st.total == 2
    assert st.average_rating is not None
    assert st.with_correction == 0


def test_feedback_aggregate_and_metrics():
    reset_feedback_service()
    svc = get_feedback_service()
    svc.record(words=["me", "water"], rating=4, corrected_sentence="x", original_sentence="y")
    agg = svc.aggregate()
    assert agg["total"] == 1
    assert "by_words" in agg
    m = svc.accuracy_metrics()
    assert m["total_feedback"] == 1
    assert m["corrected_count"] == 1


def test_feedback_export_formats():
    reset_feedback_service()
    svc = get_feedback_service()
    svc.record(words=["me"], rating=3)
    assert isinstance(svc.export("json"), list)
    assert isinstance(svc.export("jsonl"), str)
    assert isinstance(svc.export("csv"), str)
    out = svc.export("dataset")
    assert "data" in out and "metadata" in out


def test_feedback_delete_clear():
    reset_feedback_service()
    svc = get_feedback_service()
    rec = svc.record(words=["x"], rating=2)
    assert svc.delete(rec.id) is True
    assert svc.delete(rec.id) is False
    svc.record(words=["y"], rating=2)
    assert svc.clear() == 1
    assert svc.list() == []


def test_feedback_calibrate_and_suggest():
    reset_feedback_service()
    svc = get_feedback_service()
    svc.record(words=["water"], rating=5)
    cal = svc.calibrate_confidence(0.5, words=["water"])
    assert 0.0 <= cal <= 1.0
    # suggest uses agent correction service; without agent returns difflib matches
    s = svc.suggest("watre", vocabulary={"words": ["water"]})
    assert isinstance(s, list)


def test_feedback_apply_to_prompt(agent):
    reset_feedback_service()
    svc = get_feedback_service()
    svc.agent = agent
    svc.record(words=["me", "water"], corrected_sentence="I need water.")
    count = svc.apply_feedback_to_prompt(agent=agent)
    assert count >= 1


def test_feedback_import():
    reset_feedback_service()
    svc = get_feedback_service()
    n = svc.import_feedback([{"words": ["a"], "rating": 1}])
    assert n == 1
    assert svc.list()[0].words == ["a"]
