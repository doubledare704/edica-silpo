# Project Status

## Current Architecture

```text
START -> stt -> parse_intent -> plan_meals -> plan_domain_logic -> picker
       -> check_constraints -- exceeded/unmet --> picker
       -> create_cart -> tts -> END
```

- State: `SilpoAgentState` TypedDict with the `add_messages` reducer.
- Gemini: `gemini-3.5-flash-lite` primary with ordered failover (`GEMINI_MODEL_FALLBACKS`, default `gemini-3.1-flash-lite,gemini-2.5-flash-lite`); plain-JSON calls additionally use `GEMINI_MODEL_FALLBACKS_PLAIN` (Gemma codes, empty until confirmed via `models.list`).
- Gemini calls: native async `google-genai` through `client.aio` with per-model failover on 429/503/504/`model_not_found` only.
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
- Bumped to `silpo-py-mcp>=0.3.1`: mock cart tools accept only `shoppingCartId` (legacy `cartId` alias removed, matching live schema), certificates optional; typed client unchanged and already sends `shoppingCartId`.
- Live search never fabricates static-fallback products when a shopping context exists (real mode): misses stay misses and surface as `unfulfilled_requests`; the static catalog is demo/offline-only.
- Stream request carries the frontend's selected store address (`delivery_address`) into agent state so picker context and cart fulfillment resolve against the user's chosen Silpo.
- Official Silpo cart flow: cart-first context with slot revalidation, delivery update on change, upsert without clearing, post-write verify (validations/loyalty/checkout links); picker retries only previous misses.
- Delivery update is best-effort (warn-and-continue) with shipments built from written items, so a rejected update never kills a valid cart write.
- Weekly budget planner: 8 calorie-priority staples with 7-day quantities scaled by people; picker retries misses with simplified (first-word) queries.
- Weekly budget diversity fix: `BudgetDomainPlanner` honors `raw_item_requests` (fish→хек protein, veg, cereal) with weekly rates and backfills missing staples without chicken when fish covers protein; intent fallback extracts риба/крупа and routes тиждень→BUDGET; relevance rejects other cereal subtype (гречана≠манна) and accepts риба→хек; picker top-up capped at 6 per SKU and runs only when requirements met, so 2000 грн weekly yields diverse cart instead of 38× manna.
- Cart card bugfixes: live server `totalPrice=0` no longer clobbers the computed total (non-zero verified totals stay authoritative); `CartItemsPreview` uses unique per-render keys so duplicate SKUs no longer crash the `each` block and break the expand toggle; product `image_url` flows from MCP normalization through SSE `node_complete` into the preview tiles with emoji fallback.

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
- [x] Picker relevance gate: strict-reject deterministic query↔title validation between MCP search and cart acceptance (mismatches stay `unfulfilled` with `rejected_irrelevant` trace).
- [x] Review hardening of relevance gate: grill-modifier false accept (`Курка для гриля` vs `Овочі для гриля`), `group:` prefix collision, positive-case locks.
- [x] Goal-aligned picker loop: LLM query formulation from user request + LLM judge auditing survivors (accept/reject/suggest-query), deterministic gate as pre-filter, offline fallback unchanged.
- [x] Goal-constraint enforcement on all paths: deterministic alcohol backstop + LLM judge for promos, qualifier preservation (fresh/non-alcoholic) end-to-end.
- [x] Menu-grounded research + budget-fill band: grounded research_menu in plan node, picker prefers calculated_items, core quantity top-up to 70% band, disposable-ware backstop.
- [x] Party planner honors `raw_item_requests` (chicken/mushrooms/non-alcoholic) instead of hardcoded seed queries.
- [x] Picker advisor prompt: pass original query + `{"reject": true}` veto; intent prompt few-shots for grill/non-alcoholic extraction.
- [x] Grounded-research 400 fix: drop `response_mime_type` with the search tool (API rejects the combo), bare-JSON prompt + list extraction (live smoke caught it always falling back).
- [x] Weekly plan_meals node for budget weekly-menu queries: dedicated `plan_meals` node (BUDGET + budget + weekly marker) builds 7-day `meal_plan` via `plan_weekly_meals` LLM with deterministic planner fallback; `plan_domain_logic` prefers `meal_plan.shopping_seed`; non-weekly passthrough preserves party/office/gourmet flow.
- [x] Surface weekly meal_plan in SSE node_complete + CartCard: `_serialize_meal_plan` in `node_complete`, weekly `format_summary` wording, `🍽️ Тижневе меню` timeline label, `MealPlan` types + `normalizeMealPlan`, CartCard 7-day section.
- [x] Weekly seed coverage backfill: `plan_meals` merges LLM seed with missing `min_coverage` staples (dairy/bakery) from `BudgetDomainPlanner`, so a thin 2-item LLM seed can no longer fail coverage and skip top-up/promo fill.
- [x] Nearby-branch retry for assortment misses: picker re-searches `not_found`/`rejected_irrelevant` seed items in up to `MAX_NEARBY_BRANCHES` (2) branches within `MAX_NEARBY_DISTANCE_KM` (10 км) with per-branch slot validation; branch-independent rejections (constraints/judge/budget) are never retried; hits traced as `accepted_nearby` with branch/distance.
- [x] Per-query cart replace: `create_cart` clears stale items via `clear_cart` before upsert when reusing a non-empty server cart, so queries no longer accumulate; clear failures warn-and-continue without killing the write.
- [x] Honest empty cart: all-miss queries ensure a real (cleared) cart and return its URL instead of raising into a mock fallback link; `find_nearby_contexts` logs a skip breakdown (primary/far/no-slot) when resolving zero branches.
- [x] Picker observability + quota: `LOG_PICKER_REJECTIONS` flag elevates query→title rejections to INFO (gourmet live-gap diagnosis); nearby skip reasons always logged; deterministic relevance runs before the LLM judge so quota is not spent on clear mismatches.
- [x] Weekly seed preservation: picker skips generic LLM query formulation when `meal_plan.shopping_seed` is present (the party-oriented 2–6-query formulator was compressing the 12-item weekly seed); saves one LLM call per run.
- [x] Query-in-progress hero: `QueryInProgress` shows the submitted query in an animated gradient border (global `query-flow` keyframes, reduced-motion safe) instead of dead disabled inputs while streaming; voice queries fall back to a voice label.
- [x] Remove the unused header microphone icon and wire the discounts navigation item to a real page.
- [x] Bonuses and lower-price offers: add `/api/offers` backed by Silpo MCP and a responsive `/discounts` page for bonuses, promotions, discounted products, coupons, and promo codes.
- [x] Profile page: add `/api/profile` and `/profile` with MCP profile/loyalty data, saved delivery address, delivery settings, and preferred Silpo branches.
- [x] Gemini model failover chain for long-tail dialogues: `_agenerate` tries Flash fallbacks in order on retryable quota/overload errors (`429`/`503`/`504`/`model_not_found`) and fails fast on 400/401/403; audio/structured/grounded calls stay Flash-only while plain-JSON calls (judge/advisor/formulate/weekly) use the extended plain chain with `gemma-4-26b-a4b-it,gemma-4-31b-it` (codes confirmed in API changelog/reference); no graph/state changes (`backend/tests/test_gemini_rotation.py`).
- [x] Budget ring shows real fill fraction: `CartCard` takes optional `budget` (from `node_complete.total_price + remaining_budget` via `AgentTimeline`, no backend change), ring `stroke-dasharray` is `total/budget` clamped to 100% and stays full when the budget is unknown.
- [x] Tomato synonym false reject: `is_relevant` accepts `помідори↔Томат` via a new `_SYNONYM_GROUPS` entry, so assortment hits like `Томат` are no longer dropped as `rejected_irrelevant` (weekly coverage).
- [x] Gourmet empty-cart acceptance: short-stem plural match in `is_relevant` (`Сири→Сир`, 3+ chars prefix) plus judge/advisor prompt hardening (price is not a rejection criterion — budget is enforced separately), after a gourmet run accepted 0/4 on a bogus "price too low" LLM veto.
- [x] Honest empty-cart state: `node_complete` carries `unfulfilled_requests`; zero-item runs render `EmptyCart` ("Нічого не знайдено" + missing list + retry) instead of the success banner, cart card, and checkout link.
- [ ] Run gated live Gemini/MCP smoke tests with real credentials.
  Status: parse/formulate/judge verified live OK (`test_gemini_live.py`, throttled, quota-aware skips);
  `plan_weekly_meals` has offline unit coverage (mock-mode, parse+dish, fish→meat normalization, failure→None)
  plus a gated `test_live_plan_weekly_meals_smoke` (collects OK, not yet run live);
  grounded `research_menu` still unverified live — key's token quota starved (light calls pass, grounded 429s);
  re-run `test_gemini_live.py::test_live_research_menu_smoke` and `::test_live_plan_weekly_meals_smoke`
  after quota reset. Failover chain verified live against the same starvation (3.5→3.1 both 429, chain
  exhausted into deterministic fallback as designed); `gemini-2.5-flash-lite` returned live `404
  model_not_found` on that key but is NOT retired per docs (deprecation table: no shutdown date announced —
  likely project/quota-scoped, chain skips dead codes anyway). Gemma-4 plain fallbacks still need one live
  capability probe (bare-JSON acceptance) after quota reset. MCP live opt-in only (`SILPO_LIVE_SMOKE=1`, needs completed OAuth login), skipped by default.
- Keep `.docs/LANGRAPH_DISCOVERY.md` as historical reference only; it is not the active architecture contract.
