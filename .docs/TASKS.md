# Spec-Driven Implementation Checklist

## Phase 1: Core environment and shared types

- [x] Create a Python 3.12+ project structure using `uv`
- [ ] Implement `app/enums.py` with `IntentEnum` and `NodeName`
- [ ] Implement `app/state.py` with `AgentState`
- [ ] Implement `app/config.py` with `Settings` including `TTS_ENABLED` and `TTS_MOCK_MODE`

## Phase 2: LangGraph nodes (TDD and mocking)

- [ ] TDD and implement `stt_node` for Whisper or audio parsing mock
- [ ] TDD and implement `parse_intent_node` for LLM entity extraction
- [ ] TDD and implement `plan_domain_logic_node` for party and budget math logic
- [ ] TDD and implement `mcp_fetch_node` using `silpo-py-mcp`
- [ ] TDD and implement `check_constraints_node` for constraint satisfaction loop
- [ ] TDD and implement `create_cart_node` for cart link generation
- [ ] TDD and implement `tts_node` with Respeecher API and mock fallback

## Phase 3: Graph assembly and FastAPI SSE endpoint

- [ ] Assemble `create_silpo_agent_graph()` with `MemorySaver` checkpointer
- [ ] Implement `POST /api/agent/stream` using native FastAPI `StreamingResponse`

## Phase 4: SvelteKit frontend

- [ ] Create a SvelteKit (Svelte 5) project with Tailwind CSS
- [ ] Implement `VoiceInput.svelte` for push-to-talk voice input
- [ ] Implement `AgentTimeline.svelte` for the SSE `EventSource` listener
- [ ] Implement `CartCard.svelte` with an audio player for Respeecher TTS output

## Phase 5: Post-MVP roadmap (Phase 2 intents)

- [ ] Implement `plan_office_logic` for the `OFFICE` intent
- [ ] Implement `plan_gourmet_logic` for the `GOURMET` intent
