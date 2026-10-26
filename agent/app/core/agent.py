import asyncio
import json
import time
from pathlib import Path
from typing import Any, List, Optional

from app.config import settings
from app.core.confidence import below_threshold as below_threshold_helper
from app.core.confidence import detect_unknown, ensure_alternatives, vocabulary_words
from app.core.fallback import build_fallback, detect_emergency
from app.llm.base_provider import classify_error
from app.llm.client import LLMClient, _extract_json
from app.utils.timing import TimingContext
from app.schemas.request import SentenceRequest
from app.schemas.response import LLMOutput, SentenceResponse

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"


def load_vocabulary(path: Optional[str] = None) -> Any:
    p = Path(path) if path else PROMPTS_DIR / "vocabulary.json"
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def load_examples(path: Optional[str] = None) -> Any:
    p = Path(path) if path else PROMPTS_DIR / "examples.json"
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def load_system_prompt(path: Optional[str] = None) -> str:
    p = Path(path) if path else PROMPTS_DIR / "system_prompt.txt"
    return p.read_text(encoding="utf-8")


class Agent:
    def __init__(
        self,
        vocabulary=None,
        examples=None,
        llm_client=None,
        mock_mode=None,
    ):
        self.vocabulary = vocabulary if vocabulary is not None else load_vocabulary()
        self.examples = examples if examples is not None else load_examples()
        self.mock_mode = settings.mock_mode if mock_mode is None else bool(mock_mode)
        self.llm_client = llm_client if llm_client is not None else (None if self.mock_mode else LLMClient())
        self._system_template = load_system_prompt()
        self.last_raw_output = None

    @property
    def vocab_words(self) -> List[str]:
        return vocabulary_words(self.vocabulary)

    def _unknown(self, words: List[str]) -> List[str]:
        return detect_unknown(words, self.vocabulary)

    def _build_system_prompt(self, output_language: Optional[str] = None) -> str:
        lang = output_language or settings.output_language
        system = self._system_template.replace("{output_language}", lang)
        system += "\n\nKnown vocabulary: " + ", ".join(self.vocab_words)
        if self.examples:
            system += "\n\nExamples (words -> JSON):"
            for ex in self.examples:
                words = ex.get("words", ex.get("input", []))
                out = {
                    "sentence": ex.get("sentence", ex.get("output", "")),
                    "intent": ex.get("intent", "statement"),
                    "alternatives": ex.get("alternatives", []),
                }
                system += f"\nWords: {words}\n{json.dumps(out)}"
        return system

    def _build_user_prompt(self, words: List[str], confidences: List[float], alternatives: List[List[str]], unknown: List[str]) -> str:
        payload = {"words": words}
        if any(c != 1.0 for c in confidences):
            payload["confidences"] = confidences
        if any(a for a in alternatives):
            payload["alternatives"] = alternatives
        if unknown:
            payload["unknown_words"] = unknown
        return json.dumps(payload)

    def _mock(self, words: List[str], unknown: List[str], confidences: List[float]) -> SentenceResponse:
        sentence = " ".join(words).strip()
        if sentence:
            sentence = sentence[0].upper() + sentence[1:]
            if sentence[-1] not in ".!?":
                sentence += "."
        low = [w.lower() for w in words]
        if any(w in {"help", "pain", "danger", "emergency"} for w in low):
            intent = "emergency"
        elif any(w in {"hello", "hi", "hey"} for w in low):
            intent = "greeting"
        elif any(w in {"what", "where", "who", "how", "why", "when", "ok", "okay"} for w in low):
            intent = "question"
        elif any(w in {"want", "need", "please", "give"} for w in low):
            intent = "request"
        else:
            intent = "statement"
        conf = 0.9 if words else 0.1
        resp = SentenceResponse(
            sentence=sentence,
            intent=intent,
            confidence=conf,
            alternatives=[],
            fallback=False,
            unknown_words=unknown,
            raw_words=list(words),
        )
        if conf < settings.confidence_threshold:
            resp = ensure_alternatives(resp, raw_words=words)
        return resp

    async def process(self, request: Any) -> SentenceResponse:
        if isinstance(request, SentenceRequest):
            req = request
        elif isinstance(request, dict):
            req = SentenceRequest(**request)
        else:
            # allow list of words
            if isinstance(request, (list, tuple)):
                req = SentenceRequest(words=list(request))
            else:
                req = SentenceRequest(words=[])
        words = req.normalized_words()
        confidences = req.word_confidences()
        alts = req.word_alternatives()
        unknown = self._unknown(words)
        language = req.language or settings.output_language
        self.last_raw_output = None
        timings: dict = {}
        t_total = time.perf_counter()

        if not words:
            resp = build_fallback(words, unknown_words=unknown, confidence=0.1, fallback_reason="empty_input")
            timings["total"] = time.perf_counter() - t_total
            resp.timings = timings
            resp.stage_timings = dict(timings)
            resp.timing = dict(timings)
            resp.durations = dict(timings)
            resp.elapsed_ms = timings["total"] * 1000.0
            resp.duration_ms = resp.elapsed_ms
            return resp

        if self.mock_mode:
            t0 = time.perf_counter()
            resp = self._mock(words, unknown, confidences)
            timings["mock"] = time.perf_counter() - t0
            self.last_raw_output = resp.sentence
            timings["total"] = time.perf_counter() - t_total
            resp.timings = timings
            resp.stage_timings = dict(timings)
            resp.timing = dict(timings)
            resp.durations = dict(timings)
            resp.elapsed_ms = timings["total"] * 1000.0
            resp.duration_ms = resp.elapsed_ms
            return resp

        system = self._build_system_prompt(language)
        user = self._build_user_prompt(words, confidences, alts, unknown)
        try:
            t0 = time.perf_counter()
            raw = await asyncio.wait_for(
                self.llm_client.generate(system, user), timeout=settings.timeout
            )
            timings["llm"] = time.perf_counter() - t0
            self.last_raw_output = raw
            t1 = time.perf_counter()
            parsed = _extract_json(raw)
            validated = LLMOutput(**parsed)
            timings["validation"] = time.perf_counter() - t1
            resp = SentenceResponse(
                sentence=validated.sentence,
                intent=validated.intent,
                confidence=validated.confidence,
                alternatives=validated.alternatives,
                fallback=False,
                unknown_words=unknown,
                raw_words=list(words),
            )
            if detect_emergency(words, self.vocabulary):
                resp.intent = "emergency"
                resp.intent_overridden = True
                resp.overridden = True
                resp.intent_was_overridden = True
                resp.emergency_override = True
            if below_threshold_helper(resp.confidence):
                resp = ensure_alternatives(resp, raw_words=words)
            timings["total"] = time.perf_counter() - t_total
            resp.timings = timings
            resp.stage_timings = dict(timings)
            resp.timing = dict(timings)
            resp.durations = dict(timings)
            resp.elapsed_ms = timings["total"] * 1000.0
            resp.duration_ms = resp.elapsed_ms
            return resp
        except Exception as exc:
            reason = classify_error(exc)
            timings["error"] = reason
            timings["total"] = time.perf_counter() - t_total
            if detect_emergency(words, self.vocabulary):
                resp = build_fallback(
                    words,
                    unknown_words=unknown,
                    confidence=1.0,
                    intent="emergency",
                    fallback=True,
                    fallback_reason=reason,
                    emergency=True,
                    fallback_reasons=[reason, "emergency"],
                )
            else:
                resp = build_fallback(
                    words,
                    unknown_words=unknown,
                    confidence=0.1,
                    fallback_reason=reason,
                    fallback_reasons=[reason],
                )
            resp.timings = timings
            resp.stage_timings = dict(timings)
            resp.timing = dict(timings)
            resp.durations = dict(timings)
            resp.elapsed_ms = timings["total"] * 1000.0
            resp.duration_ms = resp.elapsed_ms
            return resp

    async def process_words(self, words, **kwargs):
        return await self.process(SentenceRequest(words=list(words)))

    def process_sync(self, request):
        return asyncio.get_event_loop().run_until_complete(self.process(request))


# aliases
SentenceAgent = Agent
AgentService = Agent


async def process(request, *args, **kwargs):
    return await Agent().process(request)


async def process_words(words, *args, **kwargs):
    return await Agent().process(list(words))


build_sentence = process
run = process
agent = Agent()