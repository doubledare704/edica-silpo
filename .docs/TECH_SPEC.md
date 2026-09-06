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
- picker: `remaining_budget` (budget minus priced picks; `0.0` when no budget is set),
  `unfulfilled_requests` (requested items not yet picked), `is_requirements_met`
  (coverage of planner `min_coverage` categories), `picker_trace` (tool calls for SSE/debug),
  `picker_accepted` (items accepted by the last picker run, used as a routing progress guard),
  `shopping_context` (`branch_id`/`delivery_type`/`timeslot_start`/`timeslot_end` resolved once
  per session and reused by all catalog calls; `None` when unresolvable)
- cart verify: `checkout_url` (official checkout link, preferred cart URL), `cart_validations`
  (server `validations[]` from the post-write verify read), `loyalty_hint` (ask-don't-apply
  bonus prompt when `bonusAvailable > 0`)
- retry: `attempts`, `max_attempts`, `is_budget_exceeded`
- output: `cart_url`, `summary_message`, `audio_url`
- fulfillment: `delivery_address` (user-supplied address text), `fulfillment`
  (resolved `create_shopping_cart` bundle, cached for retries; `None` when unresolvable)
- `current_step` is retained only for compatibility with prior state payloads.

All application code imports `SilpoAgentState` directly.

## Graph

```text
START
  -> stt
  -> parse_intent
  -> plan_domain_logic
  -> picker
  -> check_constraints
       | budget exceeded or requirements unmet (with progress) and attempts remain
       v
     picker
       | otherwise
       v
     create_cart
  -> tts
  -> END
```

All graph nodes are async. `check_constraints` increments `attempts` exactly once per catalog evaluation. `MemorySaver` persists conversations using `configurable.thread_id`.

## Picker loop

`picker` resolves `shopping_context` **cart-first** per the official Silpo flow
(`get_cart` → `get_cart_by_id` → branch/delivery/slot, with slot revalidation via
`get_time_slots`), falling back to the address flow only when no active cart exists.
On retry without over-budget it keeps verified picks and re-attempts only
`unfulfilled_requests` instead of re-searching everything. Requires `silpo-py-mcp>=0.3.0`
(context-first API): text search goes through `find_products_batch`, promo fillers through
`get_products(must_have_promotion=True, to_price=...)`, substitutes through slug-based
`get_similar_products` / `get_product_details` and `get_replacements`, slots through typed
`get_time_slots`, and cart writes through typed `add_or_update_cart_products(products=...)`.
Per seed item the picker calls allowed Silpo tools with a hard price ceiling,
`get_replacements`/`get_similar_products` substitutes on miss, `get_product_details`
enrichment for gourmet), scores candidates with the planner policy, and fills leftover
budget with promo products + `filler_queries` under `hard_fill`. An LLM advisor hook
(`GeminiPickerAdvisor` via `choose_picker_candidate`, greedy fallback on any failure)
chooses among shortlisted candidates. `MAX_PICKER_STEPS` (default 8) bounds tool calls;
`MIN_ITEM_PRICE_FLOOR` (default 15.0) stops filler top-ups. `check_constraints` recomputes
totals and coverage; `route_constraints` loops to `picker` while exceeded or unmet
(progress-guarded by `picker_accepted`), else proceeds to `create_cart`. `mcp_fetch`
remains as a standalone node helper but is no longer on the main path.

## Picker policy

Each `DomainPlanner` exposes a picker policy for the shared iterative picker:
`budget_mode` (`hard_fill` for party/budget/office, `soft` taste-first for gourmet),
`tool_allowlist` (allowed Silpo tools per intent), `min_coverage` (required categories),
`filler_queries` (cheap queries to fill leftover budget), and `score(candidate, remaining)`
(negative means reject under a hard ceiling).

## Integrations

### Gemini

STT and intent parsing use `google-genai` through `client.aio`. Intent parsing requests structured JSON and validates `ParsedIntentSchema`. Missing credentials, API failures, empty responses, and invalid output use deterministic local fallback logic.

### MCP and cart

Official Silpo cart flow, one-to-one: `get_cart` → `get_cart_by_id` (branch/delivery/slot
context, slot revalidated via `get_time_slots`) → `find_products_batch` → optional
`update_shopping_cart` when delivery settings changed → `add_or_update_cart_products`
(upsert, no clearing) → `get_cart_by_id` verify (`validations[]`, loyalty, checkout links).
`cart_url` is the checkout web link when available. Bonus flow is ask-don't-apply:
`loyalty_hint` surfaces `bonusAvailable`; applying stays a future explicit user action.

`MCP_MOCK_MODE=true` uses local/mock behavior. With `MCP_MOCK_MODE=false`, `SilpoClient.for_real_server()` handles the live catalog and OAuth flow. Product normalization preserves `productId`, `companyId`, `branchId`, price, private-label status, and quantity. Cart creation clears a dirty cart before updating products and returns a share URL; failures use a fallback URL without losing the summary. When `get_cart` reports no active cart, `create_cart` resolves fulfillment (saved address → geocode → delivery type → time slot) and creates one via `silpo_create_shopping_cart`; without a saved or supplied address it keeps the fallback URL.

### TTS

TTS is optional and selected with `TTS_PROVIDER`:

- `gemini`: async Gemini audio generation saved under `backend/static/audio/`.
- `respeecher`: async HTTP provider using `RESPEECHER_API_URL`, API key, and voice ID.
- `TTS_MOCK_MODE=true`: local mock audio URL.

Audio failures never prevent `summary_message` from returning. Speech text is Ukrainian, plain text, and numbers are converted to words before provider calls. Voice in, voice out: `audio_url` is produced only when the request carried voice input; text requests return no audio.

## SSE Contract

`POST /api/agent/stream` emits:

- `session_info`: thread ID
- `thinking_step`: actual graph node and status
- `tool_start` / `tool_end`: MCP activity (legacy `mcp_fetch` plus one pair per `picker_trace` entry)
- `node_complete`: final intent, totals, cart URL, summary, and audio URL (plus `remaining_budget`, `is_requirements_met`, `checkout_url`, `loyalty_hint`, `cart_validations`)

The endpoint accepts text or base64 audio/WebM input and preserves the existing frontend event names.

## Validation

```bash
uv run ruff format --check backend/app backend/tests
uv run ruff check .
uv run pyrefly check
uv run pytest backend/tests
npm run test:run --prefix frontend
```
