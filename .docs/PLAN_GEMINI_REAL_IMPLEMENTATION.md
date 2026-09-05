# Implementation Decision Record

Status: implemented

## Decisions

- Use an explicit LangGraph workflow rather than a hidden ReAct/create-agent wrapper.
- Use `gemini-3.5-flash-lite` for STT and structured intent parsing. This is intentional because the 3.7 model has higher availability/rate-limit risk for this workload.
- Use native async `google-genai` calls through `client.aio`.
- Keep deterministic fallback logic for missing credentials, provider errors, malformed output, and empty responses.
- Use real Silpo MCP/catalog/cart operations when `MCP_MOCK_MODE=false`; keep mock mode as the default for development and CI.
- Keep TTS optional and provider-selected with `TTS_PROVIDER=gemini|respeecher`.
- Preserve the public SSE event contract while reporting actual graph-node execution.
- Use one shared `SilpoAgentState` TypedDict with the `add_messages` reducer.

## Implemented Workflow

```text
START -> stt -> parse_intent -> plan_domain_logic -> mcp_fetch
       -> check_constraints -- retry while budget exceeded --> plan_domain_logic
       -> create_cart -> tts -> END
```

## Live Configuration

Set these in `.env` only when the corresponding integrations are available:

```dotenv
GEMINI_API_KEY=
GEMINI_MODEL=gemini-3.5-flash-lite
GEMINI_MOCK_MODE=false
MCP_MOCK_MODE=false
TTS_ENABLED=true
TTS_MOCK_MODE=false
TTS_PROVIDER=gemini
```

Silpo OAuth may require a first interactive login. Keep live integration tests gated with `SILPO_TEST_REAL=1`.

## Verification

The implementation is covered by backend unit/integration-contract tests and frontend Vitest tests. Run the commands in `.docs/TASKS.md` for the current validation gate.

Historical design exploration is retained in `.docs/LANGRAPH_DISCOVERY.md`; it is not an active implementation contract.
