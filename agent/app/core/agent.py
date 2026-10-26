import asyncio
import json
import time
from pathlib import Path
from typing import Any, List, Optional

from app.config import settings
from app.core.buffer import SlidingWindowBuffer
from app.core.cache import SentenceCache
from app.core.confidence import below_threshold as below_threshold_helper
from app.core.confidence import aggregate_confidence, detect_unknown, ensure_alternatives, vocabulary_words
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
        buffer=None,
        buffer_size=None,
        cache=None,
        cache_size=None,
        enable_cache=True,
        retries=None,
        agent_retries=None,
        max_retries=None,
        timeout=None,
        emergency_keywords=None,
        fallback_to_mock=None,
        system_prompt=None,
    ):
        self.vocabulary = vocabulary if vocabulary is not None else load_vocabulary()
        self.examples = examples if examples is not None else load_examples()
        self.mock_mode = settings.mock_mode if mock_mode is None else bool(mock_mode)
        self.llm_client = llm_client if llm_client is not None else (None if self.mock_mode else LLMClient())
        self._system_template = system_prompt if system_prompt is not None else load_system_prompt()
        self.last_raw_output = None

        # buffer
        if buffer is not None:
            self.buffer = buffer
        else:
            size = buffer_size if buffer_size is not None else getattr(settings, "buffer_size", 10)
            self.buffer = SlidingWindowBuffer(size=size)

        # cache
        self.enable_cache = bool(enable_cache)
        if cache is not None:
            self.cache = cache
        elif self.enable_cache:
            size = cache_size if cache_size is not None else getattr(settings, "cache_size", 128)
            self.cache = SentenceCache(capacity=size)
        else:
            self.cache = None

        # agent-level retries
        if retries is not None:
            self.retries = int(retries)
        elif agent_retries is not None:
            self.retries = int(agent_retries)
        elif max_retries is not None:
            self.retries = int(max_retries)
        else:
            self.retries = int(getattr(settings, "agent_retries", 2))

        self.timeout = timeout  # None -> settings/request
        self.emergency_keywords = emergency_keywords
        self.fallback_to_mock = getattr(settings, "fallback_to_mock", True) if fallback_to_mock is None else bool(fallback_to_mock)

        # simple stats
        self.last_retry_count = 0
        self.cache_hits = 0

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
        # buffer: dedupe immediate repeats at agent level
        raw_words = req.normalized_words()
        raw_confidences = req.word_confidences()
        raw_alts = req.word_alternatives()
        # pad confidences/alternatives to raw length
        if len(raw_confidences) < len(raw_words):
            raw_confidences = raw_confidences + [1.0] * (len(raw_words) - len(raw_confidences))
        if len(raw_alts) < len(raw_words):
            raw_alts = raw_alts + [[] for _ in range(len(raw_words) - len(raw_alts))]

        # immediate dedup within the request
        deduped_words = []
        deduped_conf = []
        deduped_alts = []
        prev = None
        for w, c, a in zip(raw_words, raw_confidences, raw_alts):
            s = str(w).strip()
            if not s:
                continue
            if s == prev:
                continue
            deduped_words.append(s)
            deduped_conf.append(c)
            deduped_alts.append(a)
            prev = s

        # buffer-level dedup: drop leading word if it repeats last buffered word
        if self.buffer is not None and deduped_words and self.buffer.get() and deduped_words[0] == self.buffer.get()[-1]:
            deduped_words = deduped_words[1:]
            deduped_conf = deduped_conf[1:]
            deduped_alts = deduped_alts[1:]

        words = deduped_words
        confidences = deduped_conf
        alts = deduped_alts
        unknown = self._unknown(words)
        language = req.language or settings.output_language
        self.last_raw_output = None
        timeout = req.timeout if getattr(req, "timeout", None) is not None else self.timeout
        if timeout is None:
            timeout = settings.timeout

        # confidence aggregation across words
        word_agg = aggregate_confidence(confidences) if confidences else 1.0

        # cache lookup
        cache_key = None
        if self.cache is not None:
            cache_key = self.cache.make_key(words, language)
            cached_resp = self.cache.get(cache_key)
            if cached_resp is not None:
                try:
                    resp_copy = SentenceResponse(**cached_resp.model_dump()) if hasattr(cached_resp, "model_dump") else SentenceResponse(**cached_resp)
                except Exception:
                    resp_copy = cached_resp
                resp_copy.cached = True
                self.cache_hits += 1
                return resp_copy

        timings: dict = {}
        t_total = time.perf_counter()

        if not words:
            resp = build_fallback(words, unknown_words=unknown, confidence=0.1, fallback_reason="empty_input")
            self._finalize_timings(resp, timings, t_total)
            self._maybe_cache(cache_key, resp)
            if self.buffer is not None:
                self.buffer.extend(words)
            return resp

        # agent-level retry loop
        last_exc = None
        strict = False
        result_resp = None
        for attempt in range(self.retries + 1):
            self.last_retry_count = attempt
            if self.mock_mode:
                t0 = time.perf_counter()
                resp = self._mock(words, unknown, confidences)
                timings["mock"] = time.perf_counter() - t0
                self.last_raw_output = resp.sentence
                # combine confidence with word aggregation
                resp.confidence = min(resp.confidence, word_agg) if confidences else resp.confidence
                # emergency detection
                if detect_emergency(words, self.vocabulary, emergency_keywords=self.emergency_keywords):
                    if resp.intent != "emergency":
                        resp.intent = "emergency"
                        resp.intent_overridden = True
                        resp.overridden = True
                        resp.intent_was_overridden = True
                        resp.emergency_override = True
                    resp.emergency = True
                    resp.emergency_fallback = True
                    resp.is_emergency = True
                    resp.emergency_flag = True
                timings["total"] = time.perf_counter() - t_total
                result_resp = resp
                break

            system = self._build_system_prompt(language)
            user = self._build_user_prompt(words, confidences, alts, unknown)
            if strict:
                system = system + "\n\nIMPORTANT: Return ONLY valid JSON matching the required schema. No markdown, no extra text."
                user = user + "\nReturn strictly valid JSON."
            try:
                t0 = time.perf_counter()
                raw = await asyncio.wait_for(
                    self.llm_client.generate(system, user), timeout=timeout
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
                if detect_emergency(words, self.vocabulary, emergency_keywords=self.emergency_keywords):
                    resp.intent = "emergency"
                    resp.intent_overridden = True
                    resp.overridden = True
                    resp.intent_was_overridden = True
                    resp.emergency_override = True
                    resp.emergency = True
                    resp.emergency_fallback = True
                    resp.is_emergency = True
                    resp.emergency_flag = True
                # confidence aggregation
                if confidences:
                    resp.confidence = min(resp.confidence, word_agg)
                if below_threshold_helper(resp.confidence):
                    resp = ensure_alternatives(resp, raw_words=words)
                timings["total"] = time.perf_counter() - t_total
                result_resp = resp
                break
            except Exception as exc:
                last_exc = exc
                reason = classify_error(exc)
                # invalid JSON -> retry with stricter prompting
                if "json" in reason or "invalid" in reason or "expecting value" in str(exc).lower():
                    strict = True
                    if attempt < self.retries:
                        continue
                # other retryable? retry on any exception up to retries
                if attempt < self.retries:
                    continue
                # exhausted
                break

        if result_resp is not None:
            self._finalize_timings(result_resp, timings, t_total)
            self._maybe_cache(cache_key, result_resp)
            if self.buffer is not None:
                self.buffer.extend(words)
            return result_resp

        # repeated provider failure -> fallback
        reason = classify_error(last_exc) if last_exc is not None else "other"
        # fall back to mock mode if configured
        if self.fallback_to_mock and not self.mock_mode:
            self.mock_mode = True
            self.llm_client = None
            emergency = detect_emergency(words, self.vocabulary, emergency_keywords=self.emergency_keywords)
            resp = self._mock(words, unknown, confidences)
            self.last_raw_output = resp.sentence
            if emergency:
                resp.intent = "emergency"
                resp.intent_overridden = True
                resp.overridden = True
                resp.intent_was_overridden = True
                resp.emergency_override = True
            resp.fallback = True
            resp.fallback_reason = reason
            resp.fallback_reasons = [reason] + (["emergency"] if emergency else [])
            resp.emergency = emergency
            resp.emergency_fallback = emergency
            resp.is_emergency = emergency
            resp.emergency_flag = emergency
            if confidences:
                resp.confidence = min(resp.confidence, word_agg)
            timings["mock_fallback"] = time.perf_counter() - t_total
            timings["total"] = time.perf_counter() - t_total
            self._finalize_timings(resp, timings, t_total)
            self._maybe_cache(cache_key, resp)
            if self.buffer is not None:
                self.buffer.extend(words)
            return resp

        if detect_emergency(words, self.vocabulary, emergency_keywords=self.emergency_keywords):
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
        if confidences:
            try:
                resp.confidence = min(resp.confidence, word_agg)
            except Exception:
                pass
        timings["total"] = time.perf_counter() - t_total
        self._finalize_timings(resp, timings, t_total)
        self._maybe_cache(cache_key, resp)
        if self.buffer is not None:
            self.buffer.extend(words)
        return resp

    def _finalize_timings(self, resp, timings, t_total):
        if "total" not in timings:
            timings["total"] = time.perf_counter() - t_total
        try:
            resp.timings = dict(timings)
            resp.stage_timings = dict(timings)
            resp.timing = dict(timings)
            resp.durations = dict(timings)
            resp.elapsed_ms = timings["total"] * 1000.0
            resp.duration_ms = resp.elapsed_ms
        except Exception:
            pass

    def _maybe_cache(self, cache_key, resp):
        if self.cache is not None and cache_key is not None:
            try:
                # store a copy
                copy_resp = SentenceResponse(**resp.model_dump())
                copy_resp.cached = False
                self.cache.set(cache_key, copy_resp)
            except Exception:
                try:
                    self.cache.set(cache_key, resp)
                except Exception:
                    pass

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