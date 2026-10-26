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

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Or with Docker:

```bash
docker compose up --build
```

## Environment variables

See `.env.example`. Key settings: `LLM_PROVIDER`, `MISTRAL_API_KEY`, `GEMINI_API_KEY`,
`MOCK_MODE`, `DATABASE_URL`, `CORS_ORIGINS`.

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

## Tests

```bash
pytest -q
```
