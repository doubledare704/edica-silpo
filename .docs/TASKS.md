# Spec-Driven Implementation Checklist

## Phase 1: Core environment and shared types

- [x] Create a Python 3.12+ project structure using `uv`
- [x] Implement `app/enums.py` with `IntentEnum` and `NodeName`
- [x] Implement `app/state.py` with `AgentState`
- [x] Implement `app/config.py` with `Settings` including `TTS_ENABLED` and `TTS_MOCK_MODE`

## Phase 2: LangGraph nodes (TDD and mocking)

- [x] TDD and implement `stt_node` for Whisper or audio parsing mock
- [x] TDD and implement `parse_intent_node` for LLM entity extraction
- [x] TDD and implement `plan_domain_logic_node` for party and budget math logic
- [x] TDD and implement `mcp_fetch_node` using `silpo-py-mcp`
- [x] TDD and implement `check_constraints_node` for constraint satisfaction loop
- [x] TDD and implement `create_cart_node` for cart link generation
- [x] TDD and implement `tts_node` with Respeecher API and mock fallback

## Phase 3: Graph assembly and FastAPI SSE endpoint

- [x] Assemble `create_silpo_agent_graph()` with `MemorySaver` checkpointer
- [x] Implement `POST /api/agent/stream` using native FastAPI `StreamingResponse`

## Phase 4: SvelteKit frontend

- [x] Create a SvelteKit (Svelte 5) project with Tailwind CSS
- [x] Implement `VoiceInput.svelte` for push-to-talk voice input
- [x] Implement `AgentTimeline.svelte` for the SSE `EventSource` listener
- [x] Implement `CartCard.svelte` with an audio player for Respeecher TTS output

## Phase 5: Post-MVP roadmap (Phase 2 intents)

- [x] Implement `plan_office_logic` for the `OFFICE` intent
- [x] Implement `plan_gourmet_logic` for the `GOURMET` intent

## Phase 6: Real Implementation for Every LangGraph Node + Gemini Multimodal Intent (per `.docs/PLAN_GEMINI_REAL_IMPLEMENTATION.md` 2026-09-02)

> Goal: Replace all mocked nodes `backend/app/nodes/*.py` with production implementations. Preserve topology `TECH_SPEC.md:58-67` and `AgentState` `TECH_SPEC.md:26-54` — no new nodes/state fields per `AGENTS.md:1`. Single model `gemini-3.7-flash` (STT+intent), TTS `gemini-3.1-flash-tts-preview` xor Respeecher via `TTS_PROVIDER` toggle. Decisions locked per Plan §10.

- [x] **Phase A. Foundations** — Add `google-genai>=2.3.0` to `pyproject.toml:7-15`; extend `backend/app/config.py:1-19` with `GEMINI_API_KEY`, `GEMINI_MODEL="gemini-3.7-flash"`, `GEMINI_TTS_MODEL="gemini-3.1-flash-tts-preview"`, `TTS_PROVIDER: Literal["respeecher","gemini"]="respeecher"`, `GEMINI_MOCK_MODE: bool=False`; add `.env.example` at repo root; scaffold `backend/app/services/gemini_service.py` (lazy `genai.Client`, `transcribe_audio(audio_bytes, mime="audio/webm")`, `parse_intent_multimodal(text, audio_bytes) -> ParsedIntentSchema` with `response_mime_type="application/json"` + `response_schema`, fallback to `_extract_intent_fallback`); new `backend/app/services/tts_service.py` stub — Files: `pyproject.toml`, `app/config.py`, `services/gemini_service.py` — Tests: unit mock + `uv run pyrefly check`
- [x] **Phase B. STT** — Make `nodes/stt.py:6-15` `async`; keep `WebM` (detect `audio/webm` vs `audio/wav` from header, `main.py:108-111` base64 already); priority: `user_text` wins else `audio_bytes -> gemini_service.transcribe_audio` else `None`; `GEMINI_MOCK_MODE` or missing key returns hardcoded fallback `"Збери кошик для пікніка..."` to keep `tests/test_stt_node.py` green — Tests: `tests/test_stt_node.py` async mock `patch("app.services.gemini_service.client.models.generate_content")` + manual curl base64 WebM
- [ ] **Phase C. Parse Intent** — Make `nodes/parse_intent.py:1-93` `async`; multimodal `contents` (audio `audio/webm` + Ukrainian prompt) if `state["audio_bytes"]` else text-only; Ukrainian prompt + `response_schema=ParsedIntentSchema` (enum English, entities Ukrainian); replace static map `parse_intent.py:55-63` with LLM output; keep hard fallback for CI; handle `OFFICE`/`GOURMET` via LLM — Tests: `tests/test_parse_intent_node.py:6-32` with mocked Gemini JSON + multimodal audio path (`CONTRACTS.md:5-22` fixture)
- [ ] **Phase D. MCP Real** — Enable real OAuth `MCP_MOCK_MODE=False` via `SilpoClient.for_real_server()` (`StreamableHttpTransport("https://mcp.silpo.ua/mcp")` + `build_oauth` + `build_encrypted_token_storage`); enhance `services/mcp_service.py:69-131` `fetch_products` to respect `prefer_private_label` (`on_sale=True` / `is_private_label` filter, `limit=5`, cheapest private-label); store `productId`, `companyId`, `branchId` from `SilpoProduct`; hybrid fallback to `STATIC_MCP_FALLBACK_CATALOG` on `SilpoAuthError`/`SilpoConnectionError` — Tests: `tests/test_mcp_fetch_node.py:8-50` still pass + gated `SILPO_TEST_REAL=1` real integration
- [ ] **Phase E. Cart Real** — Make `nodes/create_cart.py:8-21` `async`; if `MCP_MOCK_MODE` keep `mock_{uuid[:8]}`; else `cart = await client.get_cart(); if dirty: await client.clear_cart(cart.id); result = await client.add_or_update_cart_products(cart.id, items=[{productId, companyId, branchId, quantity}])`; `cart_url = f"https://silpo.ua/cart/{cart.id}"` or `result.share_url`; fallback to mock URL on error; summary via `planner.format_summary` unchanged — Tests: `tests/test_create_cart_node.py`
- [ ] **Phase F. TTS Dual** — Implement `services/tts_service.py` provider toggle `TTS_PROVIDER`; keep `utils/speech.py:109-118` `format_ukrainian_speech_text` pre-processor (numbers -> words, strip markdown) per `TECH_SPEC.md:72-79`; Branch A `respeecher` (`TTS_PROVIDER=="respeecher"` + `TTS_ENABLED` + not `TTS_MOCK_MODE` -> Respeecher API -> `/static/audio/{uuid}.mp3`); Branch B `gemini` (`TTS_PROVIDER=="gemini"` -> `client.models.generate_content(model=GEMINI_TTS_MODEL, contents=formatted_summary, config={response_modalities:["audio"], speech_config:...})` -> bytes to `static/audio/{uuid}.mp3`); `TTS_MOCK_MODE=True` returns `/static/audio/mock_response.mp3`; never blocks `summary_message` (`TECH_SPEC.md:84-85`) — Tests: `tests/test_tts_node.py:6-65`, verify `audio_url` static serving `main.py:32-35`
- [ ] **Phase G. E2E Hardening** — SSE `app/main.py:47-101` + `app/graph.py:30-63` `MemorySaver` `thread_id`, `ruff`/`pyrefly` gates; `frontend/src/lib/components/VoiceInput.svelte:28-44` WebM record + base64, `AgentTimeline.svelte:61-112` POST SSE — Tests: `tests/test_api_stream.py`, `tests/test_graph.py`, `frontend vitest run`; Validation gate per `AGENTS.md:6`: `uv run ruff format --check . && uv run ruff check . && uv run pyrefly check && uv run pytest backend/tests`

> Each phase: create failing test first -> minimal impl -> `uv run ruff format --check . && uv run ruff check . && uv run pyrefly check && uv run pytest backend/tests` -> mark `[x]` and STOP for review (single active task per `AGENTS.md:2-3`).
