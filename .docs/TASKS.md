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

- [ ] Implement `plan_office_logic` for the `OFFICE` intent
- [ ] Implement `plan_gourmet_logic` for the `GOURMET` intent
