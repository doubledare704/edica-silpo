# Project Status

## Current Architecture

```text
START -> stt -> parse_intent -> plan_domain_logic -> mcp_fetch
       -> check_constraints -- budget retry --> plan_domain_logic
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
- Gemini and Respeecher TTS routing with non-blocking failure behavior.
- Explicit LangGraph topology, budget retry routing, `MemorySaver`, and truthful SSE.
- Temporary ReAct/create-agent experiment removed from production and dependencies.
- Backend and frontend regression coverage.

## Configuration

Copy `.env.example` to `.env` and set `GEMINI_API_KEY` for real Gemini calls.

- Development defaults: `MCP_MOCK_MODE=true`, `TTS_MOCK_MODE=true`, `TTS_ENABLED=false`.
- Real catalog/cart: set `MCP_MOCK_MODE=false` and complete Silpo OAuth setup.
- Real speech: set `TTS_ENABLED=true`, `TTS_MOCK_MODE=false`, and configure the selected provider.

## Validation

```bash
uv run ruff format --check backend/app backend/tests
uv run ruff check .
uv run pyrefly check
uv run pytest backend/tests
npm run test:run --prefix frontend
```

## Open Work

- Run gated live Gemini/MCP/TTS smoke tests with real credentials.
- Keep `.docs/LANGRAPH_DISCOVERY.md` as historical reference only; it is not the active architecture contract.

## Phase 8: `create_shopping_cart` integration (silpo-py-mcp 0.2.0, per `.docs/SPEC_CREATE_SHOPPING_CART.md`)

- [x] **Phase 8.1 (service-only):** `MCPProductService.ensure_cart()` + `resolve_fulfillment()` + unit tests; node/state untouched, zero behavior change.
- [x] **Phase 8.2 (wiring):** `delivery_address`/`fulfillment` state fields + `TECH_SPEC.md` update + `create_cart_node` wiring + regression test.
