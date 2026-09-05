# edica-silpo
Edica — Autonomous AI shopping agent powered by Silpo Model Context Protocol (MCP). Calculates event meal plans, optimizes budget via private labels, and builds ready-to-buy carts.

## Setup

### Prerequisites

- Python 3.12+ with [`uv`](https://docs.astral.sh/uv/)
- Node.js for the SvelteKit frontend

### Backend configuration

Copy `.env.example` to `.env` and set `GEMINI_API_KEY` for real Gemini calls.

Development defaults:

- `MCP_MOCK_MODE=true` — mock catalog/cart responses (no Silpo OAuth needed)
- `TTS_MOCK_MODE=true`, `TTS_ENABLED=false` — audio replies off by default
- `TTS_PROVIDER=respeecher` — provider selected when speech is enabled

Real catalog/cart: set `MCP_MOCK_MODE=false` and complete Silpo OAuth setup.

Real speech: set `TTS_ENABLED=true`, `TTS_MOCK_MODE=false`, and configure the selected provider. For Respeecher:

- `RESPEECHER_API_KEY` — API key from the [Respeecher playground](https://space.respeecher.com/api-keys)
- `RESPEECHER_VOICE_ID` — voice id from the [Voices endpoint](https://space.respeecher.com/docs/space/api/voices/list)
- `RESPEECHER_MODEL` — `ua-rt` (default) or `en-rt` endpoint

### Frontend configuration

Copy `frontend/.env.example` to `frontend/.env` to override the default backend origin:

- `VITE_BACKEND_URL` — base URL of the FastAPI backend, default `http://localhost:8000`. Used for the agent SSE stream (`/api/agent/stream`), store search (`/api/stores/*`), and playback of generated TTS audio (`/static/audio/*`). Set it when the backend is not served from `localhost:8000`.

## Running

```bash
# Backend (FastAPI + LangGraph agent) on http://localhost:8000
uv run uvicorn backend.app.main:app --reload

# Frontend (SvelteKit) on http://localhost:5173
npm run dev --prefix frontend
```

## Validation

```bash
uv run ruff format --check backend/app backend/tests
uv run ruff check .
uv run pyrefly check
uv run pytest backend/tests
npm run test:run --prefix frontend
```