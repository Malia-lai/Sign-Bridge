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

1. [x] Implement `app/utils/logger.py` with structured logging (JSON + console) and levels from env.
2. [x] Add `LOG_LEVEL`, `LOG_FORMAT` settings to `app/config.py`.
3. [x] Implement `app/utils/timing.py` with a context manager/decorator for per-stage timings.
4. [x] Expose per-stage timings in `SentenceResponse` (or a dedicated timings model).
5. [x] Implement `app/api/dependencies.py` (`get_settings`, `get_agent`, `get_llm_client`).
6. [x] Refactor `app/main.py` to use dependencies and a lifespan for startup/shutdown.
7. [x] Add startup validation that prompt files exist (fail fast with a clear error).
8. [x] Add graceful shutdown closing httpx clients and DB connections.
9. [x] Add request-ID middleware for tracing.
10. [x] Move CORS allowed origins to env config (no wildcard in prod).
11. [x] Enrich `/health` with model, provider, and mock-mode info.
12. [x] Add `/ready` and basic `/metrics` endpoints.

## Phase 2 — Core Agent Enhancements (13–24)

13. [x] Implement `app/core/buffer.py` (sliding window of recent words).
14. [x] Integrate buffer into `Agent.process` to dedupe immediate repeats at agent level.
15. [x] Add language validation in `SentenceRequest`.
16. [x] Add max-words limit and validation.
17. [x] Add confidence aggregation across words.
18. [x] Add LRU sentence cache for identical word lists.
19. [x] Add agent-level retry with configurable retries.
20. [x] Support per-request timeout override.
21. [x] Retry on invalid JSON output with stricter prompting.
22. [x] Fall back to mock mode after repeated provider failure.
23. [x] Add configurable emergency keyword list (beyond vocabulary tags).
24. [x] Improve alternatives (distinct, meaningful, capped).

## Phase 3 — LLM Providers & Rate Limiting (25–38)

25. [x] Add rate-limiter integration to `MistralProvider` (parity with Gemini).
26. [x] Add usage tracking (input/output tokens) to `MistralProvider`.
27. [x] Add `close()` method to `MistralProvider`.
28. [x] Handle empty candidates / safety blocks in `GeminiProvider`.
29. [x] Validate model name on provider init.
30. [x] Provide default `generate_sync` in `BaseLLMProvider`.
31. [x] Add provider registry/factory for new providers (OpenAI, etc.).
32. [x] Add provider health-check method.
33. [x] Add `reset()` and `stats()` to `SlidingWindowRateLimiter`.
34. [x] (Optional) persist rate-limit window state in a shared store.
35. [x] Add per-user/per-API-key rate limiting.
36. [x] Add circuit breaker for providers.
37. [x] Add provider selection strategy (primary + fallback chain).
38. [x] Add mocked tests for `MistralProvider`.

## Phase 4 — API Layer (39–52)

39. [x] Implement `app/api/routes/feedback.py` (`POST /feedback`).
40. [x] Add `GET /feedback/stats`.
41. [x] Implement `app/api/websocket.py` (`/ws/sentence`).
42. [x] Define WebSocket message protocol (types + examples).
43. [x] Add friendly 422 validation error handlers.
44. [x] Add optional API-key authentication middleware.
45. [x] Add per-IP rate-limiting middleware.
46. [x] Add request/response logging middleware.
47. [x] Add OpenAPI tags and descriptions.
48. [x] Add `/v1` versioning prefix.
49. [x] Handle CORS preflight explicitly.
50. [x] Enrich health endpoint with provider/model info (see 11).
51. [x] Return safe error responses (no stack traces in prod).
52. [x] Customize Swagger UI (title, description, contact).

## Phase 5 — Services & Business Logic (53–62)

53. [x] Implement `app/services/correction_service.py`.
54. [x] Implement `app/services/history_service.py`.
55. [x] Add history endpoints (`GET`/`DELETE /history`).
56. [x] Feed corrections back into the agent (learning loop).
57. [x] Add vocabulary management endpoints (add/remove/list).
58. [x] Add import/export vocabulary.
59. [x] Make prompt templates loadable from config/DB.
60. [x] (Optional) A/B test prompts.

## Phase 6 — Data & Persistence (63–72)

61. [x] Implement `app/db/database.py` (async engine + sessions).
62. [x] Implement `app/db/models.py` (Feedback, History, Vocabulary, Prompt).
63. [x] Implement `app/db/repository.py` (CRUD).
64. [x] Add Alembic migrations.
65. [x] Add DB health check.
66. [x] Configure connection pooling.
67. [x] Support SQLite (default) + Postgres via env.
68. [x] Add data retention/cleanup job.
69. [x] Add backup/restore scripts.
70. [x] Add seeding script for default vocabulary/prompts.

## Phase 7 — Feedback & Correction (73–80)

71. [x] Design feedback schema (rating, corrected sentence, metadata).
72. [x] Implement feedback storage.
73. [x] Aggregate feedback for prompt tuning.
74. [x] Apply feedback-driven prompt improvements.
75. [x] Add "did you mean?" suggestions for unknown words.
76. [x] Calibrate confidence based on feedback.
77. [x] Compute accuracy metrics from feedback.
78. [x] Export feedback dataset for training.

## Phase 8 — WebSocket & Streaming (81–86)

79. [x] Implement WebSocket connection manager.
80. [x] Stream partial sentence updates.
81. [x] Add heartbeat/ping-pong.
82. [x] Document client reconnection handling.
83. [x] Add backpressure handling.
84. [x] Add WebSocket auth.

## Phase 9 — Testing (87–94)

85. [x] Implement `tests/conftest.py` with shared fixtures.
86. [x] Implement `tests/test_api.py` (integration tests).
87. [x] Implement `tests/test_feedback.py`.
88. [x] Add tests for buffer, timing, dependencies.
89. [x] Add tests for correction/history services.
90. [x] Add tests for DB repository.
91. [x] Add tests for WebSocket.
92. [x] Add coverage reporting (`pytest-cov`) with threshold.

## Phase 10 — Docs, Docker, Ops & Integration (95–100)

93. [x] Write `agent/README.md` (setup, run, env vars).
94. [x] Write `docs/architecture.md`.
95. [x] Write `docs/api-contract.md` (endpoints, schemas, examples).
96. [x] Complete `docker-compose.yml` and `Dockerfile` (multi-stage + healthcheck).
97. [x] Add CI (GitHub Actions) for tests + lint.
98. [ ] Add linting/formatting config (ruff/black).
99. [ ] Integrate agent with frontend or document standalone usage + port.
100. [ ] Release checklist: version bump, changelog, tag.

---

## Notes

- Keep the agent runnable in mock mode (`MOCK_MODE=true`) at all times for tests and offline dev.
- Maintain backward compatibility of `/sentence` and `/health` endpoints.
- Prefer small, focused PRs per phase.
- Update `agent/.env.example` when adding new settings (remove duplicate `LLM_PROVIDER`).
