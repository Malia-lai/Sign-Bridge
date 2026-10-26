import argparse
import asyncio
import json
import os
import re
import string
import sys
import time
import hashlib
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate the sign-language sentence agent.")
    parser.add_argument("--mode", choices=["mock", "real"], default="mock")
    parser.add_argument("--real", action="store_true", help="Shortcut for --mode real.")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between API calls (seconds).")
    parser.add_argument("--limit", type=int, default=None, help="Run only the first N cases.")
    parser.add_argument("--first", type=int, default=None, dest="limit", help="Alias for --limit.")
    parser.add_argument("-n", type=int, default=None, dest="limit", help="Alias for --limit.")
    parser.add_argument("--count", type=int, default=None, dest="limit", help="Alias for --limit.")
    parser.add_argument("--max-cases", type=int, default=None, dest="limit", help="Alias for --limit.")
    parser.add_argument("--ids", type=str, default=None, help="Comma-separated case ids to run.")
    parser.add_argument("--case-ids", type=str, default=None, dest="ids", help="Alias for --ids.")
    parser.add_argument("--rerun-fallbacks", type=str, default=None, help="Results file whose fallback cases should be re-run and merged.")
    parser.add_argument("--repeat", type=int, default=1, help="Repeat the full run N times.")
    parser.add_argument("--prompt-version", type=str, default="unversioned", help="Label for this prompt version.")
    parser.add_argument("--review", type=str, default=None, help="Print review details for failed cases in a results file.")
    parser.add_argument("--compare", action="store_true", help="Print comparison table of recent results files and exit.")
    parser.add_argument("--results-dir", type=str, default=None, help="Directory for result files.")
    parser.add_argument("--show-mock", action="store_true", help="Show mock runs in the comparison table.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.real:
        args.mode = "real"
    os.environ["MOCK_MODE"] = "true" if args.mode == "mock" else "false"
else:
    import argparse as _ap
    args = _ap.Namespace(
        mode="mock", real=False, delay=0, limit=None, ids=None, rerun_fallbacks=None,
        repeat=1, prompt_version="test", review=None, compare=False, results_dir=None, show_mock=False,
    )

from app.core.agent import Agent
from app.config import settings
from app.llm.rate_limiter import (
    estimate_call_tokens,
    estimate_prompt_tokens,
    SlidingWindowRateLimiter,
)
from app.schemas.request import SentenceRequest


def normalize_loose(text: str) -> str:
    text = (text or "").lower()
    text = text.translate(str.maketrans("", "", string.punctuation))
    return " ".join(text.split())


def normalize_strict(text: str) -> str:
    return " ".join((text or "").split())


def build_request(case):
    words = case.get("words", [])
    confidences = case.get("confidences")
    if confidences:
        items = [
            {"word": w, "confidence": c}
            for w, c in zip(words, confidences)
        ]
        return SentenceRequest(words=items)
    return SentenceRequest(words=list(words))


def estimate_case_prompt_tokens(agent, request):
    words = request.normalized_words()
    system = agent._build_system_prompt(request.language or settings.output_language)
    user = agent._build_user_prompt(
        words,
        request.word_confidences(),
        request.word_alternatives(),
        agent._unknown(words),
    )
    return estimate_prompt_tokens(system, user)


PROMPT_PATH = Path(__file__).resolve().parents[1] / "app" / "prompts" / "system_prompt.txt"


def prompt_hash() -> str:
    return hashlib.sha256(PROMPT_PATH.read_bytes()).hexdigest()[:12]


def results_directory(base: Path) -> Path:
    if args.results_dir:
        return Path(args.results_dir)
    if "PYTEST_CURRENT_TEST" in os.environ:
        return Path(tempfile.gettempdir()) / "sign-bridge-pytest-results"
    return base / "results"


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def print_review(path):
    data = load_json(path)
    results = data.get("results", [])
    failed = [r for r in results if r.get("fallback") or not r.get("intent_match") or not r.get("sentence_loose_match") or not r.get("unknown_flag_match")]
    print(f"Review: {path}")
    for r in failed:
        print("-" * 60)
        print("id:", r.get("id"))
        print("words:", r.get("words"))
        print("output:", repr(r.get("returned_sentence")))
        print("acceptable:", r.get("expected_sentences"))
        print("intent:", r.get("intent"), "expected:", r.get("expected_intent"), "acceptable_intents:", r.get("acceptable_intents"))
        print("fallback_reason:", r.get("fallback_reason"), "retry_count:", r.get("retry_count"))
    if not failed:
        print("No failed cases.")


def print_comparison(results_dir, limit=5, show_mock=False):
    out_dir = Path(results_dir)
    if not out_dir.exists():
        return
    files = sorted(out_dir.glob("run_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    selected = []
    for p in files:
        try:
            d = load_json(p)
        except Exception:
            continue
        s = d.get("summary", {})
        if (not show_mock) and s.get("mode") == "mock":
            continue
        selected.append((p, s))
        if len(selected) >= limit:
            break
    if not selected:
        print("No results files.")
        return
    print("\nComparison (recent runs):")
    print(f"{'file':34} {'prompt_version':16} {'provider':10} {'model':22} {'intent':>8} {'loose':>8} {'fallback':>9} {'avg_t':>8}")
    for p, s in selected:
        print(
            f"{p.name:34} {str(s.get('prompt_version','?')):16} {str(s.get('provider','?')):10} {str(s.get('model','?')):22} "
            f"{s.get('intent_accuracy',0):8} {s.get('loose_sentence_accuracy',0):8} "
            f"{s.get('fallback_rate',0):9} {s.get('average_response_time_seconds',0):8}"
        )


def summarize_results(results):
    n = len(results)
    non_fallback = [r for r in results if not r["fallback"]]
    nf = len(non_fallback)
    fallback_rate = (n - nf) / n if n else 0.0
    valid_json_rate = nf / n if n else 0.0
    intent_accuracy = (sum(1 for r in non_fallback if r["intent_match"]) / nf) if nf else 0.0
    loose_sentence_accuracy = (sum(1 for r in non_fallback if r["sentence_loose_match"]) / nf) if nf else 0.0
    strict_sentence_accuracy = (sum(1 for r in non_fallback if r["sentence_strict_match"]) / nf) if nf else 0.0
    unknown_flag_accuracy = (sum(1 for r in results if r["unknown_flag_match"]) / n) if n else 0.0
    avg_time = (sum(r.get("response_time_seconds", 0.0) for r in results) / n) if n else 0.0
    slowest = max((r.get("response_time_seconds", 0.0) for r in results), default=0.0)

    fallback_reasons = {}
    for r in results:
        if r["fallback"]:
            reason = r.get("fallback_reason") or "other"
            fallback_reasons[reason] = fallback_reasons.get(reason, 0) + 1

    run_provider = results[0]["provider"] if results else ("mock" if args.mode == "mock" else settings.llm_provider)
    empty_input_cases = [r["id"] for r in results if r.get("fallback_reason") == "empty_input"]
    empty_input_count = len(empty_input_cases)

    failed_cases = []
    for r in results:
        if (
            r["fallback"]
            or not r["intent_match"]
            or not r["sentence_loose_match"]
            or not r["unknown_flag_match"]
        ):
            failed_cases.append({
                "id": r["id"],
                "words": r["words"],
                "expected": r["expected_sentences"],
                "got": r["returned_sentence"],
                "fallback_reason": r["fallback_reason"],
            })

    summary = {
        "mode": args.mode,
        "prompt_version": args.prompt_version,
        "prompt_hash": prompt_hash(),
        "provider": run_provider,
        "cases": n,
        "scored_cases": nf,
        "empty_input_count": empty_input_count,
        "empty_input_cases": empty_input_cases,
        "non_fallback_cases": nf,
        "valid_json_rate": round(valid_json_rate, 4),
        "fallback_rate": round(fallback_rate, 4),
        "fallback_count_by_reason": fallback_reasons,
        "intent_accuracy": round(intent_accuracy, 4),
        "loose_sentence_accuracy": round(loose_sentence_accuracy, 4),
        "strict_sentence_accuracy": round(strict_sentence_accuracy, 4),
        "unknown_flag_accuracy": round(unknown_flag_accuracy, 4),
        "average_response_time_seconds": round(avg_time, 4),
        "slowest_response_time_seconds": round(slowest, 4),
        "failed_cases": failed_cases,
    }
    return summary


async def run():
    base = Path(__file__).resolve().parent
    with open(base / "dataset.json", encoding="utf-8") as f:
        cases = json.load(f)

    if args.ids:
        wanted = {int(x.strip()) for x in args.ids.split(",") if x.strip()}
        cases = [c for c in cases if c.get("id") in wanted]

    if args.limit is not None and args.limit > 0:
        cases = cases[:args.limit]

    # rerun fallbacks: load base results and restrict to fallback case ids
    merge_base_results = None
    if args.rerun_fallbacks:
        base_data = load_json(args.rerun_fallbacks)
        merge_base_results = base_data.get("results", [])
        fallback_ids = {r.get("id") for r in merge_base_results if r.get("fallback")}
        cases = [c for c in cases if c.get("id") in fallback_ids]

    agent = Agent()
    input_estimates = [estimate_case_prompt_tokens(agent, build_request(case)) for case in cases]
    estimated_input_tokens = max(input_estimates, default=0)
    estimated_tokens_per_call = estimated_input_tokens + settings.max_output_tokens
    safe_calls = SlidingWindowRateLimiter.safe_calls_per_minute(
        estimated_tokens_per_call,
        settings.requests_per_minute,
        settings.tokens_per_minute,
    )
    print(
        f"Estimated tokens per call: {estimated_tokens_per_call} "
        f"(prompt estimate {estimated_input_tokens} + max output {settings.max_output_tokens}); "
        f"safe calls per minute: {safe_calls} "
        f"(requests={settings.requests_per_minute}, tokens={settings.tokens_per_minute})"
    )

    repeat_metrics = []
    repeat_models = []
    last_out_path = None

    for repeat_idx in range(max(1, args.repeat)):
        results = []

        for case in cases:
            request = build_request(case)
            words = case.get("words", [])
            expected_intent = case.get("expected_intent")
            expected_sentences = case.get("expected_sentences")
            if isinstance(expected_sentences, str):
                expected_sentences = [expected_sentences]
            if not expected_sentences:
                single = case.get("expected_sentence") or case.get("sentence") or case.get("expected")
                expected_sentences = [single] if single is not None else []
            expected_sentences = [s for s in expected_sentences if s is not None]
            expect_unknown_flag = bool(case.get("expect_unknown_flag", False))
            acceptable_intents = case.get("acceptable_intents")
            if not acceptable_intents:
                acceptable_intents = [expected_intent] if expected_intent is not None else []

            start = time.perf_counter()
            if args.mode != "mock" and getattr(agent, "llm_client", None):
                agent.llm_client.last_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
            result = await agent.process(request)
            elapsed = time.perf_counter() - start

            intent_match = (not result.fallback) and (not acceptable_intents or result.intent in acceptable_intents)
            strict_match = (not result.fallback) and any(
                normalize_strict(result.sentence) == normalize_strict(s) for s in expected_sentences
            )
            loose_match = (not result.fallback) and any(
                normalize_loose(result.sentence) == normalize_loose(s) for s in expected_sentences
            )
            unknown_flag_match = bool(bool(result.unknown_words)) == expect_unknown_flag
            provider_name = "mock" if args.mode == "mock" else getattr(agent.llm_client, "last_provider_used", settings.llm_provider)
            retry_count = 0 if args.mode == "mock" else getattr(agent.llm_client, "last_retry_count", 0)
            raw_output = None if args.mode == "mock" else getattr(agent, "last_raw_output", None)
            usage = (
                getattr(agent.llm_client, "last_usage", {})
                if args.mode != "mock" and getattr(agent, "llm_client", None)
                else {}
            )
            if args.mode == "mock":
                model_name = "mock"
            else:
                prov = getattr(getattr(agent, "llm_client", None), "provider", None)
                model_name = getattr(prov, "model", None) or (
                    settings.gemini_model if settings.llm_provider == "gemini" else settings.model_name
                )

            record = {
                "id": case.get("id"),
                "words": words,
                "expected_intent": expected_intent,
                "expected_sentences": expected_sentences,
                "expect_unknown_flag": expect_unknown_flag,
                "returned_sentence": result.sentence,
                "intent": result.intent,
                "confidence": result.confidence,
                "response": {
                    "sentence": result.sentence,
                    "intent": result.intent,
                    "confidence": result.confidence,
                    "alternatives": list(result.alternatives),
                },
                "fallback": bool(result.fallback),
                "fallback_reason": result.fallback_reason,
                "fallback_reasons": list(result.fallback_reasons),
                "emergency": bool(result.emergency),
                "intent_overridden": bool(result.intent_overridden),
                "unknown_words": bool(result.unknown_words),
                "unknown_word_list": list(result.unknown_words),
                "response_time_seconds": round(elapsed, 4),
                "input_tokens": int(usage.get("input_tokens", 0)),
                "output_tokens": int(usage.get("output_tokens", 0)),
                "intent_match": bool(intent_match),
                "sentence_strict_match": bool(strict_match),
                "sentence_loose_match": bool(loose_match),
                "unknown_flag_match": bool(unknown_flag_match),
                "provider": provider_name,
                "model": model_name,
                "retry_count": int(retry_count),
                "acceptable_intents": acceptable_intents,
                "raw_output": raw_output,
            }
            results.append(record)

            print(
                f"[run {repeat_idx + 1}] {case.get('id', '?'):>2} "
                f"intent={result.intent:10} "
                f"conf={result.confidence:.2f} "
                f"fb={int(result.fallback)} "
                f"unk={int(bool(result.unknown_words))} "
                f"t={elapsed:.3f}s "
                f"intent_ok={int(intent_match)} "
                f"loose={int(loose_match)} "
                f"strict={int(strict_match)}"
            )

            if args.delay and args.delay > 0:
                await asyncio.sleep(args.delay)

        # merge rerun results into base results if requested
        if merge_base_results:
            by_id = {r.get("id"): r for r in results}
            merged = []
            for r in merge_base_results:
                rid = r.get("id")
                merged.append(by_id.get(rid, r))
            # append any new ids not in base
            base_ids = {r.get("id") for r in merge_base_results}
            for r in results:
                if r.get("id") not in base_ids:
                    merged.append(r)
            results = merged

        summary = summarize_results(results)
        summary["prompt_version"] = args.prompt_version
        summary["prompt_hash"] = prompt_hash()
        summary["model"] = results[0]["model"] if results else ("mock" if args.mode == "mock" else settings.gemini_model if settings.llm_provider == "gemini" else settings.model_name)

        print(f"\nRun {repeat_idx + 1} summary")
        for key, value in summary.items():
            if key != "failed_cases":
                if key in {"intent_accuracy", "loose_sentence_accuracy", "fallback_rate", "average_response_time_seconds"}:
                    print(f"{key}: {value} (scored_cases={summary.get('scored_cases', 0)})")
                else:
                    print(f"{key}: {value}")

        print("\nFailed cases:")
        if not summary["failed_cases"]:
            print("  none")
        for fc in summary["failed_cases"]:
            print(
                f"  id={fc['id']} words={fc['words']} "
                f"expected={fc['expected']} got={fc['got']!r} "
                f"fallback_reason={fc['fallback_reason']}"
            )

        out_dir = results_directory(base)
        out_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_model = "".join(c if c.isalnum() or c in "-_." else "-" for c in str(summary.get("model", "unknown")))
        out_path = out_dir / f"run_{timestamp}_{safe_model}.json"
        payload = {"summary": summary, "results": results}
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        print(f"\nSaved: {out_path}")
        last_out_path = out_path

        repeat_metrics.append({
            "intent_accuracy": summary["intent_accuracy"],
            "loose_sentence_accuracy": summary["loose_sentence_accuracy"],
            "fallback_rate": summary["fallback_rate"],
            "average_response_time_seconds": summary["average_response_time_seconds"],
        })
        repeat_models.append(summary.get("model"))

    if len(set(str(m) for m in repeat_models)) > 1:
        print(f"WARNING: repeated runs used different models: {repeat_models}")

    if len(repeat_metrics) > 1:
        def agg(key):
            vals = [m[key] for m in repeat_metrics]
            return min(vals), sum(vals) / len(vals), max(vals)
        print("\nRepeat aggregate")
        for key in ["intent_accuracy", "loose_sentence_accuracy", "fallback_rate", "average_response_time_seconds"]:
            lo, mean, hi = agg(key)
            print(f"{key}: min={lo} mean={round(mean, 4)} max={hi}")

    results_dir = results_directory(Path(__file__).resolve().parent)
    print_comparison(results_dir, 5, args.show_mock)


if __name__ == "__main__":
    base = Path(__file__).resolve().parent
    results_dir = results_directory(base)
    if args.compare:
        print_comparison(results_dir, 5, args.show_mock)
        sys.exit(0)
    if args.review:
        print_review(args.review)
        sys.exit(0)
    asyncio.run(run())
