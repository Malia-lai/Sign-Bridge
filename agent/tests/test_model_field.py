import asyncio
import contextlib
import io
import json
import os

import evaluation.run_eval as rev


def test_model_field_mock(tmp_path, monkeypatch):
    os.environ["MOCK_MODE"] = "true"
    monkeypatch.setattr(rev.settings, "mock_mode", True)
    rev.args.mode = "mock"
    rev.args.real = False
    rev.args.delay = 0
    rev.args.limit = 1
    rev.args.ids = None
    rev.args.rerun_fallbacks = None
    rev.args.repeat = 1
    rev.args.prompt_version = "test"
    rev.args.review = None
    rev.args.compare = False
    rev.args.results_dir = str(tmp_path)
    rev.args.show_mock = False

    asyncio.run(rev.run())

    files = sorted(tmp_path.glob("run_*.json"), key=lambda p: p.stat().st_mtime)
    assert files
    data = json.loads(files[-1].read_text())
    assert data["results"][0]["model"] == "mock"
    assert data["summary"]["model"] == "mock"
    assert set(data["results"][0]["response"]) == {
        "sentence",
        "intent",
        "confidence",
        "alternatives",
    }


def test_comparison_hides_mock_runs_by_default(tmp_path):
    for name, mode in (("mock", "mock"), ("real", "real")):
        (tmp_path / f"run_{name}.json").write_text(
            json.dumps({"summary": {"mode": mode, "prompt_version": name}}),
            encoding="utf-8",
        )

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        rev.print_comparison(tmp_path)
    assert "run_real.json" in output.getvalue()
    assert "run_mock.json" not in output.getvalue()

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        rev.print_comparison(tmp_path, show_mock=True)
    assert "run_mock.json" in output.getvalue()
