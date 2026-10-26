# Sign-Bridge AI Agent Service

FastAPI service that turns a list of signed words into a natural sentence using an LLM
(Mistral or Gemini), with mock mode, confidence handling, emergency detection, fallback,
and a token-aware rate limiter.

## Setup

```bash
cd agent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env
```

## Run

The service listens on port **8000** by default. From the repository root, start the
web app separately on port **3000** with `npm run dev`; the agent API is available at
`http://localhost:8000` and its interactive API reference at `/docs`.

```bash
cd /path/to/Sign-Bridge/agent
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Or with Docker:

```bash
docker compose up --build
```

## Environment variables

See `.env.example`. Key settings: `LLM_PROVIDER`, `MISTRAL_API_KEY`, `GEMINI_API_KEY`,
`MOCK_MODE`, `DATABASE_URL`, `CORS_ORIGINS`.

For offline development, set `MOCK_MODE=true` in `agent/.env`. Configure
`CORS_ORIGINS=http://localhost:3000` when calling the service from the Vite app in a
browser. If `API_KEY` is set, callers must send it in the `X-API-Key` request header.

## Endpoints

- `GET /health` — health + model/provider info
- `GET /ready` — readiness
- `GET /metrics` — basic metrics
- `POST /sentence` (alias `/v1/sentence`) — generate sentence
- `POST /feedback`, `GET /feedback/stats`
- `GET/DELETE /history`
- `GET /api/words`, `/api/status`, `/api/sequences/{label}`
- `WS /ws` — real-time landmark streaming
- `WS /ws/sentence` — sentence streaming

### Standalone request

```bash
curl -X POST http://localhost:8000/v1/sentence \
  -H 'Content-Type: application/json' \
  -d '{"words":["hello","water"],"language":"English"}'
```

The frontend and agent currently run as separate processes. The web app does not
automatically forward recognized signs to the agent; an integration should call
`POST http://localhost:8000/v1/sentence` with its recognized word list and use the
returned sentence. For browser calls, set `CORS_ORIGINS` to the frontend origin.

## Tests

```bash
pytest -q
```

Lint and check formatting with Ruff:

```bash
ruff check app tests
ruff format --check app tests
```

See [RELEASE.md](RELEASE.md) for the versioning, changelog, and tagging checklist.
