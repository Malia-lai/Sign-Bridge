# AI Agent — Completion Plan

> Plan to finish all remaining work for the Sign-Bridge AI agent service (`agent/`).
> Source of truth for outstanding tasks. Tick items off as they are completed.
> Companion session note: `[[merge-agent-into-main]]` (Obsidian).

## Overview

The agent service (`agent/`) is a FastAPI app that turns a list of signed words into a
natural sentence using an LLM (Mistral or Gemini), with mock mode, confidence handling,
emergency detection, fallback, and a token-aware rate limiter. The core is implemented and
tested (32 tests pass). The items below complete the unfinished stubs, harden the service,
add persistence/feedback, and ship it.

## Status legend
- `[ ]` todo
- `[x]` done

---

## Phase 1 — Foundations & Utilities (1–12)

1. [ ] Implement `app/utils/logger.py` with structured logging (JSON + console) and levels from env.
2. [ ] Add `LOG_LEVEL`, `LOG_FORMAT` settings to `app/config.py`.
3. [ ] Implement `app/utils/timing.py` with a context manager/decorator for per-stage timings.
4. [ ] Expose per-stage timings in `SentenceResponse` (or a dedicated timings model).
5. [ ] Implement `app/api/dependencies.py` (`get_settings`, `get_agent`, `get_llm_client`).
6. [ ] Refactor `app/main.py` to use dependencies and a lifespan for startup/shutdown.
7. [ ] Add startup validation that prompt files exist (fail fast with a clear error).
8. [ ] Add graceful shutdown closing httpx clients and DB connections.
9. [ ] Add request-ID middleware for tracing.
10. [ ] Move CORS allowed origins to env config (no wildcard in prod).
11. [ ] Enrich `/health` with model, provider, and mock-mode info.
12. [ ] Add `/ready` and basic `/metrics` endpoints.

## Phase 2 — Core Agent Enhancements (13–24)

13. [ ] Implement `app/core/buffer.py` (sliding window of recent words).
14. [ ] Integrate buffer into `Agent.process` to dedupe immediate repeats at agent level.
15. [ ] Add language validation in `SentenceRequest`.
16. [ ] Add max-words limit and validation.
17. [ ] Add confidence aggregation across words.
18. [ ] Add LRU sentence cache for identical word lists.
19. [ ] Add agent-level retry with configurable retries.
20. [ ] Support per-request timeout override.
21. [ ] Retry on invalid JSON output with stricter prompting.
22. [ ] Fall back to mock mode after repeated provider failure.
23. [ ] Add configurable emergency keyword list (beyond vocabulary tags).
24. [ ] Improve alternatives (distinct, meaningful, capped).

## Phase 3 — LLM Providers & Rate Limiting (25–38)

25. [ ] Add rate-limiter integration to `MistralProvider` (parity with Gemini).
26. [ ] Add usage tracking (input/output tokens) to `MistralProvider`.
27. [ ] Add `close()` method to `MistralProvider`.
28. [ ] Handle empty candidates / safety blocks in `GeminiProvider`.
29. [ ] Validate model name on provider init.
30. [ ] Provide default `generate_sync` in `BaseLLMProvider`.
31. [ ] Add provider registry/factory for new providers (OpenAI, etc.).
32. [ ] Add provider health-check method.
33. [ ] Add `reset()` and `stats()` to `SlidingWindowRateLimiter`.
34. [ ] (Optional) persist rate-limit window state in a shared store.
35. [ ] Add per-user/per-API-key rate limiting.
36. [ ] Add circuit breaker for providers.
37. [ ] Add provider selection strategy (primary + fallback chain).
38. [ ] Add mocked tests for `MistralProvider`.

## Phase 4 — API Layer (39–52)

39. [ ] Implement `app/api/routes/feedback.py` (`POST /feedback`).
40. [ ] Add `GET /feedback/stats`.
41. [ ] Implement `app/api/websocket.py` (`/ws/sentence`).
42. [ ] Define WebSocket message protocol (types + examples).
43. [ ] Add friendly 422 validation error handlers.
44. [ ] Add optional API-key authentication middleware.
45. [ ] Add per-IP rate-limiting middleware.
46. [ ] Add request/response logging middleware.
47. [ ] Add OpenAPI tags and descriptions.
48. [ ] Add `/v1` versioning prefix.
49. [ ] Handle CORS preflight explicitly.
50. [ ] Enrich health endpoint with provider/model info (see 11).
51. [ ] Return safe error responses (no stack traces in prod).
52. [ ] Customize Swagger UI (title, description, contact).

## Phase 5 — Services & Business Logic (53–62)

53. [ ] Implement `app/services/correction_service.py`.
54. [ ] Implement `app/services/history_service.py`.
55. [ ] Add history endpoints (`GET`/`DELETE /history`).
56. [ ] Feed corrections back into the agent (learning loop).
57. [ ] Add vocabulary management endpoints (add/remove/list).
58. [ ] Add import/export vocabulary.
59. [ ] Make prompt templates loadable from config/DB.
60. [ ] (Optional) A/B test prompts.

## Phase 6 — Data & Persistence (63–72)

61. [ ] Implement `app/db/database.py` (async engine + sessions).
62. [ ] Implement `app/db/models.py` (Feedback, History, Vocabulary, Prompt).
63. [ ] Implement `app/db/repository.py` (CRUD).
64. [ ] Add Alembic migrations.
65. [ ] Add DB health check.
66. [ ] Configure connection pooling.
67. [ ] Support SQLite (default) + Postgres via env.
68. [ ] Add data retention/cleanup job.
69. [ ] Add backup/restore scripts.
70. [ ] Add seeding script for default vocabulary/prompts.

## Phase 7 — Feedback & Correction (73–80)

71. [ ] Design feedback schema (rating, corrected sentence, metadata).
72. [ ] Implement feedback storage.
73. [ ] Aggregate feedback for prompt tuning.
74. [ ] Apply feedback-driven prompt improvements.
75. [ ] Add "did you mean?" suggestions for unknown words.
76. [ ] Calibrate confidence based on feedback.
77. [ ] Compute accuracy metrics from feedback.
78. [ ] Export feedback dataset for training.

## Phase 8 — WebSocket & Streaming (81–86)

79. [ ] Implement WebSocket connection manager.
80. [ ] Stream partial sentence updates.
81. [ ] Add heartbeat/ping-pong.
82. [ ] Document client reconnection handling.
83. [ ] Add backpressure handling.
84. [ ] Add WebSocket auth.

## Phase 9 — Testing (87–94)

85. [ ] Implement `tests/conftest.py` with shared fixtures.
86. [ ] Implement `tests/test_api.py` (integration tests).
87. [ ] Implement `tests/test_feedback.py`.
88. [ ] Add tests for buffer, timing, dependencies.
89. [ ] Add tests for correction/history services.
90. [ ] Add tests for DB repository.
91. [ ] Add tests for WebSocket.
92. [ ] Add coverage reporting (`pytest-cov`) with threshold.

## Phase 10 — Docs, Docker, Ops & Integration (95–100)

93. [ ] Write `agent/README.md` (setup, run, env vars).
94. [ ] Write `docs/architecture.md`.
95. [ ] Write `docs/api-contract.md` (endpoints, schemas, examples).
96. [ ] Complete `docker-compose.yml` and `Dockerfile` (multi-stage + healthcheck).
97. [ ] Add CI (GitHub Actions) for tests + lint.
98. [ ] Add linting/formatting config (ruff/black).
99. [ ] Integrate agent with frontend or document standalone usage + port.
100. [ ] Release checklist: version bump, changelog, tag.

---

## Notes

- Keep the agent runnable in mock mode (`MOCK_MODE=true`) at all times for tests and offline dev.
- Maintain backward compatibility of `/sentence` and `/health` endpoints.
- Prefer small, focused PRs per phase.
- Update `agent/.env.example` when adding new settings (remove duplicate `LLM_PROVIDER`).
