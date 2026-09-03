# Backend Code Review — Priority Action Plan

**Source:** SOLID & Best-Practice Audit (29 backend issues)  
**Date:** 2026-09-02  
**Status:** All 63 tests passing, lint/format/type clean

---

## 🔴 Critical — Do First (Security & Blocking)

| # | Issue | Location | Effort | Notes |
|---|-------|----------|--------|-------|
| 14 | CORS wildcard + credentials | `backend/app/main.py:26-27` | 🟢 Trivial | `allow_origins=["*"]` with `allow_credentials=True` rejected by browsers. Restrict to actual frontend host(s). |
| 35 | Phase D: OAuth + private-label filter not implemented | `backend/app/services/mcp_service.py:89` | 🟡 Medium | `SilpoClient.for_real_server()` called but real auth/filtering missing. Blocks `MCP_MOCK_MODE=False`. |
| 36 | Phase E: `create_cart_node` synchronous, mock URLs only | `backend/app/nodes/create_cart.py:8-21` | 🟡 Medium | Needs async + wire to real `SilpoClient.add_or_update_cart_products`. |
| 37 | Phase F: `TTS_PROVIDER` config ignored, `tts_service.py` dead code | `backend/app/nodes/tts.py:18-28` | 🟡 Medium | Route through `tts_service` based on `TTS_PROVIDER`. |

---

## 🟠 High — Architecture & SOLID Violations

| # | Issue | Location | Effort | Notes |
|---|-------|----------|--------|-------|
| 11 | DIP: `stt.py` imports concrete `gemini_service` | `backend/app/nodes/stt.py:3` | 🟢 Small | Inject `STTPort` / `Transcriber` interface in graph assembly. |
| 12 | DIP: `mcp_fetch.py` imports concrete `mcp_product_service` singleton | `backend/app/nodes/mcp_fetch.py:3` | 🟢 Small | Inject `ProductCatalogPort` into node factory. |
| 13 | DIP: `create_cart.py` calls `get_domain_planner(intent)` directly | `backend/app/nodes/create_cart.py:4` | 🟢 Small | Pass planner via closure/factory in `graph.py`. |
| 1 | SRP: `tts_node` mixes formatting, mock branching, orchestration | `backend/app/nodes/tts.py:11-33` | 🟡 Medium | Extract orchestration to `TTSService` / `TTSPort`; node only coordinates. |
| 2 | SRP: `parse_intent.py` defines schema + fallback parser | `backend/app/nodes/parse_intent.py:1-106` | 🟡 Medium | Move `ParsedIntentSchema` + `_extract_intent_fallback` to `domain/` or `services/`. |
| 3 | SRP: `mcp_service.py` static fallback catalog mixed with class | `backend/app/services/mcp_service.py:11-131` | 🟡 Medium | Separate catalog into data module or inject via dependency. |
| 5 | OCP: `_PLANNERS` dict requires modification to add intent | `backend/app/domain/planners.py:248-260` | 🟡 Medium | Use registry/decorator: `@register_planner(IntentEnum.X)`. |
| 6 | OCP: Hardcoded keyword lists in `_extract_intent_fallback` | `backend/app/nodes/parse_intent.py:18-71` | 🟡 Medium | Externalize intent keywords to config or strategy map. |

---

## 🟡 Medium — Correctness & Maintainability

| # | Issue | Location | Effort | Notes |
|---|-------|----------|--------|-------|
| 19 | Async inconsistency: 4/7 nodes sync in async `astream` | `plan_domain_logic.py:7`, `check_constraints.py:6`, `create_cart.py:8`, `tts.py:11` | 🟡 Medium | Make all nodes `async def` (Phase E partially requires this). |
| 8 | LSP: `tts_node` always returns mock URL; `try/except` dead code | `backend/app/nodes/tts.py:18-28` | 🟢 Small | Fix conditional: when enabled, call `tts_service.generate_audio_gemini(...)`. |
| 18 | Dead code: Real TTS paths unreachable from node | `backend/app/nodes/tts.py:20-28` | 🟢 Small | Wire `tts_node` to `tts_service.generate_audio_gemini(...)` when `TTS_PROVIDER="gemini"`. |
| 4 | SRP: `_sse_generator` does state init + accumulation + SSE formatting | `backend/app/main.py:47-101` | 🟡 Medium | Split: state init, event emission, final payload building. |
| 7 | OCP: Retry logic baked into `check_constraints_node` | `backend/app/nodes/check_constraints.py:6-19` | 🟢 Small | Inject `ConstraintPolicy` / `RetryStrategy` dependency. |
| 9 | ISP: `DomainPlanner` forces `plan` + `format_summary` | `backend/app/domain/planners.py:8-15` | 🟡 Medium | Split into `ItemPlanner` and `SummaryFormatter` protocols. |
| 22 | Duplication: `format_ukrainian_speech_text` called in node + service | `tts.py:14` + `tts_service.py:21` | 🟢 Small | Call once in service layer; node passes raw text. |
| 23 | Duplication: Async/thread-fallback copy-pasted in `gemini_service.py` | `gemini_service.py:86-104`, `159-180` | 🟢 Small | Extract `_generate_content_with_fallback(...)` helper. |
| 24 | Circular dependency risk: `gemini_service.py` imports from `nodes.parse_intent` | `backend/app/services/gemini_service.py:123` | 🟡 Medium | Move `ParsedIntentSchema` + fallback to `domain/` for safe top-level imports. |
| 25 | Error handling: Bare `except Exception:` with no logging | `backend/app/nodes/parse_intent.py:97` | 🟢 Small | Log exception (`logger.warning(...)`) before fallback. |
| 38 | Redundant conditional edges map keys to identical values | `backend/app/graph.py:50-57` | 🟢 Trivial | Simplify to `workflow.add_conditional_edges(NodeName.CHECK_CONSTRAINTS, _route_constraints)`. |
| 39 | Broad exception catch in `tts_service.py` | `backend/app/services/tts_service.py:67` | 🟢 Small | Catch `RuntimeError`, `OSError`, `ValueError` explicitly. |

---

## 🟢 Low — Polish & Cleanup

| # | Issue | Location | Effort | Notes |
|---|-------|----------|--------|-------|
| 10 | ISP: `AgentState` carries unused fields (`messages`, `audio_url`) | `backend/app/state.py:9-26` | 🟢 Small | Document which fields each node reads/writes (LangGraph may require). |
| 15 | Security: Static mount exposes all of `backend/static/` | `backend/app/main.py:33-35` | 🟢 Trivial | Mount dedicated `static/audio/` or use `html=False`. |
| 16 | Dead code: `OPENAI_API_KEY` defined but unused | `backend/app/config.py:44` | 🟢 Trivial | Remove. |
| 17 | Dead code: `messages: list[BaseMessage]` never populated | `backend/app/state.py:3,26` | 🟢 Trivial | Remove unless checkpointer requires externally. |
| 20 | Type safety: `accumulated_state: dict[str, object]` loses type info | `backend/app/main.py:76` | 🟢 Small | Use `dict[str, Any]` or dedicated accumulator type. |
| 21 | Type safety: `StateGraph(AgentState) # type: ignore[type-var]` | `backend/app/graph.py:32` | 🟢 Small | Verify `AgentState` satisfies `StateGraph` TypedDict; remove ignore if correct. |
| 26 | Magic numbers: `budget=0.0`, `max_attempts=3` in two places | `backend/app/state.py:20,22` | 🟢 Trivial | Define constants (`DEFAULT_MAX_ATTEMPTS = 3`). |
| 27 | Rounding bug: `int(total_price)` truncates decimals | `backend/app/domain/planners.py:84-86,112-114,155-157,224-226` | 🟢 Small | Use `round(total_price, 0)` or `int(round(total_price))`. |
| 28 | Inconsistent rounding: `round(total_price, 2)` vs truncate | `backend/app/nodes/check_constraints.py:16` | 🟢 Small | Standardize on one rounding strategy across pipeline. |
| 33 | Config: `extra="ignore"` swallows unknown env vars | `backend/app/config.py:36` | 🟢 Trivial | Use `extra="forbid"` in production; `ignore` only for tests. |
| 34 | Module-level state: `_client` singleton, `mcp_product_service` at import | `gemini_service.py:16`, `mcp_service.py:131` | 🟡 Medium | Use dependency injection or lightweight service locator. |

---

## 📋 Suggested Execution Order

### Sprint 1 (Critical Security & Unblock Real Integrations)
1. **#14** — Fix CORS (5 min)
2. **#35** — Implement OAuth + private-label filter for MCP (2-4 hrs)
3. **#36** — Make `create_cart_node` async + wire real cart API (2-4 hrs)
4. **#37** — Wire `tts_node` to `tts_service` via `TTS_PROVIDER` (1-2 hrs)

### Sprint 2 (DIP & SRP — Decouple Nodes from Concrete Services)
5. **#11** — Inject `STTPort` into `stt_node` (30 min)
6. **#12** — Inject `ProductCatalogPort` into `mcp_fetch_node` (30 min)
7. **#13** — Pass planner via factory in `graph.py` (30 min)
8. **#1** — Extract `TTSService` / `TTSPort`; thin `tts_node` (1-2 hrs)
9. **#2** — Move schema + fallback parser to `domain/` (1 hr)
10. **#3** — Separate fallback catalog from `MCPProductService` (1 hr)

### Sprint 3 (OCP & Async Consistency)
11. **#5** — Registry/decorator for planners (1-2 hrs)
12. **#6** — Externalize intent keywords (1 hr)
13. **#19** — Make all nodes `async def` (1-2 hrs)
14. **#7** — Inject `RetryStrategy` into `check_constraints_node` (30 min)

### Sprint 4 (Duplication, Dead Code, Polish)
15. **#8, #18** — Fix TTS conditional + wire real paths (30 min)
16. **#4** — Split `_sse_generator` (1 hr)
17. **#22, #23** — Extract helpers for duplication (30 min)
18. **#24** — Move schema to `domain/` to break circular dep (30 min)
19. **#25, #39** — Add logging + narrow exception types (30 min)
20. **#27, #28** — Fix rounding consistency (30 min)
21. **#16, #17, #33** — Remove dead code, fix config (15 min)
22. **#38** — Simplify conditional edges (5 min)
23. **#10, #20, #21, #26, #34** — Type safety, docs, module-level state (1-2 hrs)

---

## 📝 Notes

- **TDD Required:** For each task, create unit test in `backend/tests/` first, verify failure, then implement minimal fix.
- **Validation Gate:** After each task, run `uv run ruff format --check .`, `uv run ruff check .`, `uv run pyrefly check`, and `uv run pytest backend/tests/`.
- **Task Tracking:** Update `.docs/TASKS.md` with each task; mark `[x]` on completion.
- **Architecture Guardrails:** No new nodes, endpoints, or `AgentState` fields beyond `.docs/TECH_SPEC.md`.