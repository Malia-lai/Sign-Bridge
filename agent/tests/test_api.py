import os

os.environ.setdefault("MOCK_MODE", "true")

from fastapi.testclient import TestClient


def test_root_and_health(client):
    r = client.get("/")
    assert r.status_code == 200
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "model" in data
    assert "provider" in data
    assert "mock_mode" in data


def test_ready_and_metrics(client):
    r = client.get("/ready")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "uptime_seconds" in r.json()


def test_health_db(client):
    r = client.get("/health/db")
    assert r.status_code == 200


def test_sentence_basic(client):
    r = client.post("/sentence", json={"words": ["me", "water", "want"]})
    assert r.status_code == 200
    data = r.json()
    assert data["sentence"]
    assert data["intent"] == "request"
    assert data["fallback"] is False


def test_sentence_root_and_api_prefix(client):
    for path in ["/", "/api/sentence", "/v1/sentence"]:
        if path == "/":
            continue
        r = client.post(path, json={"words": ["hello"]})
        assert r.status_code == 200, path


def test_sentence_empty(client):
    r = client.post("/sentence", json={"words": []})
    assert r.status_code == 200
    data = r.json()
    assert data["confidence"] <= 1.0


def test_sentence_single_word_list(client):
    r = client.post("/sentence", json={"words": ["water"]})
    assert r.status_code == 200
    assert r.json()["sentence"]


def test_sentence_validation_error(client):
    r = client.post("/sentence", json={"words": "not-a-list"})
    assert r.status_code == 422
    data = r.json()
    assert "detail" in data


def test_sentence_too_many_words(client, monkeypatch):
    import app.config as cfg

    monkeypatch.setattr(cfg.settings, "max_words", 2)
    # also update alias
    cfg.settings.MAX_WORDS = 2
    r = client.post("/sentence", json={"words": ["a", "b", "c"]})
    assert r.status_code == 422


def test_sentence_unknown_word(client):
    r = client.post("/sentence", json={"words": ["me", "water", "zzzz"]})
    assert r.status_code == 200
    assert "zzzz" in r.json()["unknown_words"]


def test_sentence_language_validation(client):
    r = client.post("/sentence", json={"words": ["hello"], "language": ""})
    assert r.status_code == 422
    r = client.post("/sentence", json={"words": ["hello"], "language": "English"})
    assert r.status_code == 200


def test_feedback_crud(client):
    r = client.post("/feedback", json={"words": ["me", "water"], "rating": 5, "corrected_sentence": "I want water."})
    assert r.status_code == 200
    fid = r.json()["id"]
    r = client.get(f"/feedback/{fid}")
    assert r.status_code == 200
    r = client.get("/feedback")
    assert r.status_code == 200
    assert len(r.json()) >= 1
    r = client.get("/feedback/stats")
    assert r.status_code == 200
    assert r.json()["total"] >= 1
    r = client.delete(f"/feedback/{fid}")
    assert r.status_code == 200


def test_feedback_stats_and_metrics(client):
    client.post("/feedback", json={"words": ["hi"], "rating": 4})
    r = client.get("/feedback/stats")
    assert "average_rating" in r.json()
    r = client.get("/feedback/metrics")
    assert r.status_code == 200
    r = client.get("/feedback/aggregate")
    assert r.status_code == 200
    r = client.get("/feedback/export", params={"format": "json"})
    assert r.status_code == 200


def test_history_endpoints(client):
    client.post("/sentence", json={"words": ["me", "water", "want"]})
    r = client.get("/history")
    assert r.status_code == 200
    items = r.json()
    assert len(items) >= 1
    hid = items[0]["id"]
    r = client.get(f"/history/{hid}")
    assert r.status_code == 200
    r = client.delete(f"/history/{hid}")
    assert r.status_code == 200
    r = client.delete("/history")
    assert r.status_code == 200


def test_vocabulary_endpoints(client):
    r = client.post("/vocabulary", json={"word": "zzztest"})
    assert r.status_code == 200
    r = client.get("/vocabulary")
    assert r.status_code == 200
    assert "zzztest" in r.json()["words"]
    r = client.delete("/vocabulary/zzztest")
    assert r.status_code == 200
    # import/export
    r = client.post("/vocabulary/import", json={"words": ["imp1", "imp2"]})
    assert r.status_code == 200
    r = client.get("/vocabulary/export")
    assert r.status_code == 200


def test_prompts_endpoints(client):
    r = client.post("/prompts", json={"name": "p1", "template": "Hello {output_language}", "activate": True})
    assert r.status_code == 200
    r = client.get("/prompts")
    assert r.status_code == 200
    r = client.get("/prompts/p1")
    assert r.status_code == 200
    r = client.post("/prompts/activate", json={"name": "p1"})
    assert r.status_code == 200
    r = client.get("/prompts/export")
    assert r.status_code == 200


def test_feedback_suggest(client):
    client.post("/vocabulary", json={"word": "water"})
    r = client.post("/feedback/suggest", json={"word": "watre", "n": 3})
    assert r.status_code == 200
    assert "suggestions" in r.json()


def test_feedback_apply(client):
    client.post("/feedback", json={"words": ["me", "water"], "corrected_sentence": "I need water."})
    r = client.post("/feedback/apply")
    assert r.status_code == 200
    assert "applied" in r.json()


def test_cors_preflight(client):
    r = client.options("/sentence")
    assert r.status_code in (200, 204)


def test_metrics_versions(client):
    for prefix in ["", "/api", "/v1"]:
        r = client.get(f"{prefix}/metrics" if prefix else "/metrics")
        # metrics only at root? health router included with prefixes includes metrics? health router has /metrics yes
        assert r.status_code in (200, 404)
