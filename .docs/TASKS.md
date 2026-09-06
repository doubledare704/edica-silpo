# Project Status

## Current Architecture

```text
START -> stt -> parse_intent -> plan_domain_logic -> picker
       -> check_constraints -- exceeded/unmet --> picker
       -> create_cart -> tts -> END
```

- State: `SilpoAgentState` TypedDict with the `add_messages` reducer.
- Gemini: `gemini-3.5-flash-lite`, chosen for availability and lower rate-limit pressure.
- Gemini calls: native async `google-genai` through `client.aio`.
- MCP/cart: mock by default; real OAuth-backed calls when `MCP_MOCK_MODE=false`.
- TTS: optional; selected with `TTS_PROVIDER` (`gemini` or `respeecher`).
- Recovery: deterministic fallbacks preserve a usable response when integrations fail.
- SSE: reports actual graph nodes and preserves existing event names.

## Completed

- Core project, domain planners, and intents: `party`, `budget`, `office`, `gourmet`.
- Async Gemini STT and structured multimodal intent parsing with fallback.
- Real-capable MCP product search with private-label selection and cart identifiers.
- Real-capable cart mutation with dirty-cart clearing and fallback URLs.
- Missing carts (`exists:false`) are created via `silpo_create_shopping_cart` with resolved fulfillment (saved address → geocode → delivery type → slot); unresolvable fulfillment keeps the fallback URL.
- Real Respeecher WAV TTS for voice requests, immediate browser playback with a manual fallback, and non-blocking provider failures.
- Explicit LangGraph topology, budget retry routing, `MemorySaver`, and truthful SSE.
- Temporary ReAct/create-agent experiment removed from production and dependencies.
- Backend and frontend regression coverage.
- Fixed live cart write: bypass stale `add_or_update_cart_products` SDK wrapper, send `products` array via `call_tool` (server rejects `items` with MCP -32602).
- Migrated to `silpo-py-mcp>=0.3.0` context-first API: `shopping_context` in state, batch search, server-side promo/price filters, slug-based details/similar, typed slots and cart writes.
- Cart write validates items (UUID productId + companyId/branchId) before touching the live cart, so static-fallback SKUs fail fast instead of wiping the cart and falling back to a mock URL.

## Configuration

Copy `.env.example` to `.env` and set `GEMINI_API_KEY` for real Gemini calls.

- Development defaults: `MCP_MOCK_MODE=true`, `TTS_MOCK_MODE=false`, `TTS_ENABLED=true`; voice replies use Respeecher when its key is configured.
- Real catalog/cart: set `MCP_MOCK_MODE=false` and complete Silpo OAuth setup.
- Real speech: configure `RESPEECHER_API_KEY`, `RESPEECHER_VOICE_ID`, and the selected provider. Set `TTS_MOCK_MODE=true` only when a deterministic local fixture is needed.

## Validation

```bash
uv run ruff format --check backend/app backend/tests
uv run ruff check .
uv run pyrefly check
uv run pytest backend/tests
npm run test:run --prefix frontend
```

## Open Work

- [x] Iterative picker phase 1: extend `SilpoAgentState` (remaining_budget, unfulfilled_requests, is_requirements_met, picker_trace) + per-intent picker policy in planners.
- [x] Iterative picker phase 2: picker service ReAct loop + node with full Silpo toolset.
- [x] Iterative picker phase 3: check_constraints fill/exit routing + SSE tool events.
- Run gated live Gemini/MCP smoke tests with real credentials.
- Keep `.docs/LANGRAPH_DISCOVERY.md` as historical reference only; it is not the active architecture contract.
