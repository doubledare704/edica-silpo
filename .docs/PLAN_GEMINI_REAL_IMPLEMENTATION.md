# Plan: Real Implementation for Every LangGraph Node + Gemini Multimodal Intent

**Date:** 2026-09-02
**Status:** Draft for review
**Decisions incorporated:** Single model (`gemini-3.7-flash` for STT+intent), TTS both with toggle (Respeecher xor Gemini), Silpo MCP real OAuth enabled, frontend keeps `WebM`, LLM output Ukrainian (enum English, entities Ukrainian).

## 1. Goal & Constraints

*   Replace all mocked nodes (`backend/app/nodes/*.py`) with production implementations.
*   Preserve topology `TECH_SPEC.md:58-67` and `AgentState` `TECH_SPEC.md:26-54` — **no new nodes or state fields** per `AGENTS.md:1`.
*   LangGraph guesses `IntentEnum` via Gemini prompt calls; input is multimodal (`text | audio/webm` via `POST /api/agent/stream` `backend/app/main.py:41-44`).
*   Single model: `gemini-3.7-flash` (1M context, native audio). `gemini-3.5-transcribe` deferred. TTS uses `gemini-3.1-flash-tts-preview` when toggled.

## 2. Current Mock Inventory

| Node `app/enums.py:11-18` | File | Mock Today | Evidence |
|---|---|---|---|
| `STT` | `nodes/stt.py:6-15` | Hardcoded Ukrainian string if `audio_bytes` | Returns `"Збери кошик для пікніка..."` |
| `PARSE_INTENT` | `nodes/parse_intent.py:18-93` | Regex budget/people + keyword intent + static `raw_item_requests` | `_extract_intent_fallback` |
| `PLAN_DOMAIN_LOGIC` | `nodes/plan_domain_logic.py:7-12` + `domain/planners.py:18-260` | Real math, isolated from MCP prices | Quantity math + retry shrink |
| `MCP_FETCH` | `nodes/mcp_fetch.py:7-11` + `services/mcp_service.py:69-131` | `SilpoClient.for_mock()` when `MCP_MOCK_MODE=True` + `STATIC_MCP_FALLBACK_CATALOG` | Mock server |
| `CHECK_CONSTRAINTS` | `nodes/check_constraints.py:6-19` | Real sum+flag | `price*quantity` |
| `CREATE_CART` | `nodes/create_cart.py:8-21` | `uuid` -> `https://silpo.ua/cart/share/mock_...` | No `get_cart`/`add_or_update_cart_products` |
| `TTS` | `nodes/tts.py:11-33` + `utils/speech.py:109-118` | Always `/static/audio/mock_response.mp3` in mock | No API call |

Config `app/config.py:1-19` has `OPENAI_API_KEY`, `RESPEECHER_*`, `MCP_MOCK_MODE`, `TTS_*` but **no Gemini keys**. `pyproject.toml:7-15` missing `google-genai`. No `.env` at repo root (verified `2026-09-02`).

## 3. Target Architecture

Topology unchanged `app/graph.py:30-63`:

```
[STT: gemini-3.7-flash transcribe] -> [PARSE_INTENT: gemini-3.7-flash structured] -> [PLAN_DOMAIN_LOGIC] -> [MCP_FETCH: SilpoClient.for_real_server] -> [CHECK_CONSTRAINTS] --(is_budget_exceeded && attempts < max_attempts)--> loop
                                                                                                                     \-> [CREATE_CART: get_cart + add_or_update_cart_products] -> [TTS: Respeecher xor Gemini toggle] -> END
```

`_route_constraints:19-28` unchanged. Nodes become `async` where they call network. New services only: `app/services/gemini_service.py`, `app/services/tts_service.py`.

## 4. Cross-Cutting: Config, Deps, Secrets

**Deps `pyproject.toml`:**
```toml
dependencies = [
  "google-genai>=2.3.0",
  # ... existing
]
```

**Config `app/config.py` additions:**
```python
GEMINI_API_KEY: str = ""
GEMINI_MODEL: str = "gemini-3.7-flash"
GEMINI_TTS_MODEL: str = "gemini-3.1-flash-tts-preview"
TTS_PROVIDER: Literal["respeecher", "gemini"] = "respeecher"
GEMINI_MOCK_MODE: bool = False
# SilpoSettings already via silpo-py-mcp (oauth_storage_dir, oauth_encryption_key, mcp_url)
```

Add `.env.example` at repo root:
```
GEMINI_API_KEY=
GEMINI_MODEL=gemini-3.7-flash
GEMINI_MOCK_MODE=false
TTS_ENABLED=false
TTS_MOCK_MODE=true
TTS_PROVIDER=respeecher
RESPEECHER_API_KEY=
RESPEECHER_VOICE_ID=
MCP_MOCK_MODE=true
```

Validation gate per `AGENTS.md:6`: `uv run ruff format --check . && uv run ruff check . && uv run pyrefly check`.

## 5. Gemini Service Layer (new)

**File: `backend/app/services/gemini_service.py`**

*   Singleton `genai.Client(api_key=settings.GEMINI_API_KEY)` lazy; raises if missing and `GEMINI_MOCK_MODE==False`.
*   `async def transcribe_audio(audio_bytes: bytes, mime: str="audio/webm") -> str`
    *   `client.models.generate_content(model=GEMINI_MODEL, contents=[Part.from_bytes(...), "Transcribe verbatim in Ukrainian, no translation..."], config={"temperature": 0.0})`
    *   Fallback to hardcoded mock on error.
*   `async def parse_intent_multimodal(user_text: str | None, audio_bytes: bytes | None) -> ParsedIntentSchema`
    *   Multimodal `contents`: if `audio_bytes` present, inline `audio/webm` + text prompt; else text only.
    *   Ukrainian system prompt: "Ти асистент Silpo Smart Shopper. Визнач IntentEnum {party,budget,office,gourmet}, budget (грн), people_count, dietary_restrictions [vegetarian, vegan...], raw_item_requests (укр назви товарів). Відповідай JSON строго за схемою." Few-shot from `CONTRACTS.md:5-22`.
    *   Structured output: `config={"response_mime_type":"application/json", "response_schema": ParsedIntentSchema}` (Gemini 3.7 supports it).
    *   Wrap `try/except` -> fallback `_extract_intent_fallback` + `logger.warning`.

Why single model: one client/billing, consistent Ukrainian tokenizer, native audio.

## 6. Per-Node Real Implementation

### 6.1 STT `nodes/stt.py:6-15` -> async
*   Keep `WebM` (decision). `main.py:108-111` already base64-decodes; detect mime from header bytes (`webm` -> `audio/webm` else `audio/wav`).
*   Priority: if `user_text` present return it (user corrected transcription wins); elif `audio_bytes` -> `gemini_service.transcribe_audio`; else `None`.
*   `GEMINI_MOCK_MODE` or missing key -> return current hardcoded fallback to keep `tests/test_stt_node.py` green.
*   Test extension: async mock `patch("app.services.gemini_service.client.models.generate_content")` returning Ukrainian.

### 6.2 PARSE_INTENT `nodes/parse_intent.py:1-93` -> async multimodal
*   Signature `async def parse_intent_node(state: AgentState) -> dict`.
*   If `state["audio_bytes"]` exists and `GEMINI_MODEL` configured, call multimodal parse with both audio+text; else text-only. `STT` already wrote `user_text` but re-feeding raw audio improves confidence.
*   Reuse `ParsedIntentSchema` strictly (enum English, entities Ukrainian) — satisfies `Strict schema only` + `Ukrainian LLM output`. Replace static map `parse_intent.py:55-63` (hardcoded `raw_item_requests` per intent) with LLM output; keep hard fallback for CI.
*   Handles `OFFICE`/`GOURMET` now via LLM keywords, not regex only.
*   Tests: extend `tests/test_parse_intent_node.py:6-32` with mocked Gemini JSON; add multimodal audio path test.

### 6.3 PLAN_DOMAIN_LOGIC `nodes/plan_domain_logic.py:7-12` + `domain/planners.py:18-260`
*   **No LLM** — keep deterministic planners (SOLID). Already covers `PARTY`, `BUDGET`, `OFFICE`, `GOURMET` with quantity math and `prefer_private_label` + retry reduction.
*   Minor: planners expose `prefer_private_label` for `MCP_FETCH` to prefer `on_sale`/`is_private_label` search.

### 6.4 MCP_FETCH `nodes/mcp_fetch.py:7-11` + `services/mcp_service.py:69-131`
*   Enable real OAuth (decision): `MCP_MOCK_MODE=False` in prod. `SilpoClient.for_real_server()` uses `StreamableHttpTransport("https://mcp.silpo.ua/mcp")` + `build_oauth` + `build_encrypted_token_storage` (`silpo_py_mcp/client.py:for_real_server`). Surface `SilpoSettings` from env; first run opens browser — document for dev.
*   Enhance `fetch_products`: respect `prefer_private_label` -> `get_products(query, on_sale=True)` or post-filter `is_private_label`, `limit=5`, pick cheapest private-label if flag else most relevant. Pagination handled.
*   Store `productId`, `companyId`, `branchId` from `SilpoProduct` for cart (inspect `SilpoProduct` fields) — extend product dict with these keys.
*   Hybrid fallback: `try: async with client` except `SilpoAuthError`/`SilpoConnectionError` -> log and fallback to `STATIC_MCP_FALLBACK_CATALOG`; never breaks pipeline.
*   Tests: `tests/test_mcp_fetch_node.py:8-50` mock still pass; add gated real integration test `SILPO_TEST_REAL=1`.

### 6.5 CHECK_CONSTRAINTS `nodes/check_constraints.py:6-19`
*   Keep as-is: `total_price = sum(p["price"]*p["quantity"])`, `is_budget_exceeded = budget>0 and total_price>budget`, increment `attempts`. Real prices now come from MCP.

### 6.6 CREATE_CART `nodes/create_cart.py:8-21` -> async real
*   Signature `async`.
*   If `MCP_MOCK_MODE`: keep `mock_{uuid[:8]}` for determinism.
*   If real: `cart = await client.get_cart(); if dirty: await client.clear_cart(cart.id); result = await client.add_or_update_cart_products(cart.id, items=[{"productId": p["id"], "companyId": p["companyId"], "branchId": p["branchId"], "quantity": p["quantity"]}])`; `cart_url = f"https://silpo.ua/cart/{cart.id}"` or `result.share_url` if provided by `CartSummary`/`CartUpdateResult`; fallback to mock URL on error.
*   Summary via `planner.format_summary` unchanged (plain Ukrainian before TTS).

### 6.7 TTS `nodes/tts.py:11-33` + `utils/speech.py:109-118`
*   Both with toggle (decision): `TTS_PROVIDER` selects branch. Keep `format_ukrainian_speech_text:109-118` pre-processor (numbers -> words, strip markdown) per `TECH_SPEC.md:72-79`.
*   Branch A `respeecher`: if `TTS_PROVIDER=="respeecher"` and `TTS_ENABLED` and not `TTS_MOCK_MODE`, call Respeecher API (`RESPEECHER_API_KEY`, `VOICE_ID`) -> save to `/static/audio/{uuid}.mp3`, return `/static/audio/...`. Fallback `audio_url=None` on failure (spec `TECH_SPEC.md:84-85`).
*   Branch B `gemini`: if `TTS_PROVIDER=="gemini"`, call `client.models.generate_content(model=GEMINI_TTS_MODEL, contents=formatted_summary)` (returns `output_audio.data`), save bytes to `static/audio/{uuid}.mp3`. On failure try other provider then `None`.
*   `TTS_MOCK_MODE=True` still returns `/static/audio/mock_response.mp3` for dev. Never blocks `summary_message`.

## 7. SSE & Frontend

*   `app/main.py:47-101` generator already emits `thinking_step` per node + `tool_start/tool_end` for `MCP_FETCH`. No change for multimodal (base64 already passed `main.py:107-111`).
*   `frontend/src/lib/components/VoiceInput.svelte:28-44` records `audio/webm`, base64-encodes, posts to `/api/agent/stream`; `AgentTimeline.svelte:61-112` fetch-based SSE reader (POST). No UI redesign; optional `audioMime` field is additive, non-breaking.

## 8. Execution Phasing (TDD per `AGENTS.md:2-3`, single active task)

| Phase | Scope | Files Touched | Tests |
|---|---|---|---|
| **A. Foundations** | Add `google-genai` dep, `app/config.py` Gemini fields, `.env.example`, scaffold `services/gemini_service.py` with mock passthrough | `pyproject.toml:7-15`, `app/config.py:1-19`, new `services/gemini_service.py` | Unit mock, `uv run pyrefly check` |
| **B. STT** | `stt_node` async multimodal transcribe, keep WebM | `nodes/stt.py:6-15` | `tests/test_stt_node.py` + manual curl base64 WebM |
| **C. Parse Intent** | `parse_intent_node` async structured multimodal, Ukrainian prompt, `response_schema` | `nodes/parse_intent.py:1-93` | `tests/test_parse_intent_node.py:6-32` with mocked JSON, `CONTRACTS.md:12-22` fixture |
| **D. MCP Real** | Wire real OAuth, enhance `fetch_products` with `prefer_private_label`, persist `companyId/branchId` | `services/mcp_service.py:69-131` | Mock still pass, gated real `SILPO_TEST_REAL=1` |
| **E. Cart Real** | `create_cart_node` async real `get_cart`+`add_or_update_cart_products` | `nodes/create_cart.py:8-21` | `tests/test_create_cart_node.py` |
| **F. TTS Dual** | `services/tts_service.py` + provider toggle, keep `utils/speech.py:109-118` contract | `nodes/tts.py:11-33` | `tests/test_tts_node.py:6-65`, verify `audio_url` static serving `main.py:32-35` |
| **G. E2E Hardening** | SSE E2E `MemorySaver` thread_ids, `ruff`/`pyrefly` | `app/graph.py:30-63`, `app/main.py:47-101` | `tests/test_api_stream.py`, `tests/test_graph.py`, `frontend vitest run` |

Each phase: create failing test first -> minimal implementation -> `uv run ruff format --check . && uv run ruff check . && uv run pyrefly check && uv run pytest backend/tests` -> mark checklist and stop for review.

## 9. Risks & Mitigations

*   **No AgentState extension** — store only existing fields; raw audio not persisted beyond `audio_bytes`.
*   **OAuth browser in docker/CI** — gate real MCP behind env; CI uses mock; document manual login once -> encrypted token cached (`oauth_storage_dir`).
*   **WebM compatibility** — Gemini supports `audio/webm;codecs=opus`; limit frontend to 30s max; add timeSlice check if needed.
*   **Structured output brittleness** — `temperature=0.1`, strict `IntentEnum` StrEnum, fallback regex on parse error, log warning.
*   **Cost** — single `gemini-3.7-flash` cheapest; `GEMINI_MOCK_MODE` in tests avoids billing.
*   **Numbers-as-words contract** — `utils/speech.py` remains mandatory before any TTS call; enforce in both providers.

## 10. Review Checklist for Approver

*   [x] Approve `google-genai>=2.3.0` and single-model strategy (vs split transcribe model)
*   [x] Confirm `GEMINI_API_KEY` will be placed in untracked `.env` at repo root
*   [x] Approve `TTS_PROVIDER` toggle design (vs Respeecher-only per old spec)
*   [x] Approve real MCP OAuth plan (browser login, encrypted storage) vs staying mock
*   [x] Approve phase order B->C->D->E->F or prefer C before B (they share one model)
*   [x] Confirm `.docs/TASKS.md` should be extended with these 6 phases or tracked separately
