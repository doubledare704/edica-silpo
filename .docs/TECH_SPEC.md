# Technical Specification

## Runtime

- Python 3.12+
- Package manager: `uv`
- Backend: FastAPI, LangGraph, native async `google-genai`
- Frontend: SvelteKit 5
- Gemini model: `gemini-3.5-flash-lite`
- Optional Gemini TTS model: `gemini-3.1-flash-tts-preview`

The 3.5 Flash Lite model is intentional: it provides lower availability and rate-limit risk for this workload than the busier 3.7 model.

## State

`backend/app/state.py` defines the single graph state, `SilpoAgentState`:

- `messages: Annotated[list[BaseMessage], add_messages]`
- audio input: `audio_bytes`, `user_text`
- intent: `intent`, `budget`, `people_count`, `dietary_restrictions`, `raw_item_requests`
- shopping: `calculated_items`, `mcp_products`, `total_price`
- retry: `attempts`, `max_attempts`, `is_budget_exceeded`
- output: `cart_url`, `summary_message`, `audio_url`
- `current_step` is retained only for compatibility with prior state payloads.

`AgentState` is a compatibility alias for `SilpoAgentState`. New code should import `SilpoAgentState`.

## Graph

```text
START
  -> stt
  -> parse_intent
  -> plan_domain_logic
  -> mcp_fetch
  -> check_constraints
       | budget exceeded and attempts remain
       v
    plan_domain_logic
       | otherwise
       v
    create_cart
  -> tts
  -> END
```

All graph nodes are async. `check_constraints` increments `attempts` exactly once per catalog evaluation. `MemorySaver` persists conversations using `configurable.thread_id`.

## Integrations

### Gemini

STT and intent parsing use `google-genai` through `client.aio`. Intent parsing requests structured JSON and validates `ParsedIntentSchema`. Missing credentials, API failures, empty responses, and invalid output use deterministic local fallback logic.

### MCP and cart

`MCP_MOCK_MODE=true` uses local/mock behavior. With `MCP_MOCK_MODE=false`, `SilpoClient.for_real_server()` handles the live catalog and OAuth flow. Product normalization preserves `productId`, `companyId`, `branchId`, price, private-label status, and quantity. Cart creation clears a dirty cart before updating products and returns a share URL; failures use a fallback URL without losing the summary.

### TTS

TTS is optional and selected with `TTS_PROVIDER`:

- `gemini`: async Gemini audio generation saved under `backend/static/audio/`.
- `respeecher`: async HTTP provider using `RESPEECHER_API_URL`, API key, and voice ID.
- `TTS_MOCK_MODE=true`: local mock audio URL.

Audio failures never prevent `summary_message` from returning. Speech text is Ukrainian, plain text, and numbers are converted to words before provider calls.

## SSE Contract

`POST /api/agent/stream` emits:

- `session_info`: thread ID
- `thinking_step`: actual graph node and status
- `tool_start` / `tool_end`: MCP activity
- `node_complete`: final intent, totals, cart URL, summary, and audio URL

The endpoint accepts text or base64 audio/WebM input and preserves the existing frontend event names.

## Validation

```bash
uv run ruff format --check backend/app backend/tests
uv run ruff check .
uv run pyrefly check
uv run pytest backend/tests
npm run test:run --prefix frontend
```
