# Architecture

FastAPI app (`app/main.py`) with lifespan-managed startup/shutdown. Routes under
`app/api/routes/` and `app/api/websocket.py`. Business logic in `app/core/` (agent,
buffer, confidence, emergency, fallback, cache, retry) and `app/services/`
(correction, history). LLM providers behind `app/llm/` with a registry/factory.
Persistence via `app/db/` (SQLAlchemy async, Alembic migrations). Rate limiting in
`app/rate_limiter/`. Middleware: request-id, CORS, auth, per-IP rate limit, logging.
