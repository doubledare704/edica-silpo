# Technical Specification & Architecture Contract

## 1. Shared domain enums (`app/enums.py`)

```python
from enum import StrEnum


class IntentEnum(StrEnum):
    PARTY = "party"
    BUDGET = "budget"
    OFFICE = "office"
    GOURMET = "gourmet"


class NodeName(StrEnum):
    STT = "stt"
    SHOPPER_AGENT = "shopper_agent"
    PARSE_INTENT = "parse_intent"
    PLAN_DOMAIN_LOGIC = "plan_domain_logic"
    MCP_FETCH = "mcp_fetch"
    CHECK_CONSTRAINTS = "check_constraints"
    CREATE_CART = "create_cart"
    TTS = "tts"
```

## 2. State topology (`app/state.py`)

Legacy `AgentState` (plain `TypedDict`, kept for node compat) plus hybrid
`SilpoAgentState(LangChainAgentState)` used by the wrapper graph and `create_agent`
subgraph — `messages` inherits the `add_messages` reducer; domain fields are
`NotRequired` with an extra `current_step` tracker:

```python
class SilpoAgentState(LangChainAgentState):
    audio_bytes: NotRequired[bytes | None]
    user_text: NotRequired[str | None]
    intent: NotRequired[IntentEnum | None]
    budget: NotRequired[float]
    people_count: NotRequired[int | None]
    dietary_restrictions: NotRequired[list[str]]
    raw_item_requests: NotRequired[list[str]]
    calculated_items: NotRequired[list[dict[str, Any]]]
    mcp_products: NotRequired[list[dict[str, Any]]]
    total_price: NotRequired[float]
    attempts: NotRequired[int]
    max_attempts: NotRequired[int]
    is_budget_exceeded: NotRequired[bool]
    cart_url: NotRequired[str | None]
    summary_message: NotRequired[str]
    audio_url: NotRequired[str | None]
    current_step: NotRequired[str]
```

## 3. LangGraph topology and conditional edges

Hybrid wrapper (LangGraph v1, `create_agent` subgraph). Physical nodes: `stt`,
`shopper_agent`, `tts`. Legacy `NodeName` values are preserved for the SSE
contract — `INNER_TO_LEGACY` in `app/graph.py` maps inner ReAct activity back to
legacy step names, and `POST /api/agent/stream` expands `shopper_agent` into the
five legacy `thinking_step` events.

```text
[STT] ➔ [SHOPPER_AGENT] ➔ [TTS] ➔ END
            |
            ├─ prod (GEMINI_API_KEY set): create_agent ReAct loop
            │    [parse→plan_items ➔ fetch_products ➔ check_budget ⇄(retry)➔ create_cart]
            │    router: ToolStrategy(IntentRoute) strict IntentEnum;
            │    prompts: intent_router dynamic_prompt; guard: budget_guard
            └─ offline/mock or LLM error: deterministic fallback
                 [PARSE_INTENT] ➔ [PLAN_DOMAIN_LOGIC] ➔ [MCP_FETCH] ➔ [CHECK_CONSTRAINTS]
                                                                       |
             ┌───────────────────────────────────────────────────────┴────┐
             │ [is_budget_exceeded && attempts < max_attempts]          │
             ▼                                                          ▼
       [PLAN_DOMAIN_LOGIC]                                          [CREATE_CART]
```

All Gemini calls are pure-async via `client.aio.models.generate_content` — no
`asyncio.to_thread` sync fallback anywhere (`rg to_thread backend/` is empty).

## 4. Respeecher TTS preparation and formatting contract

All text responses passed into `tts_node` before sending them to the Respeecher API must follow this system contract:

- **Language:** Ukrainian only in all cases.
- **Plain text only:** no Markdown, no lists, no URLs, no JSON, and no IDs.
- **Numbers as words:** all numbers, dates, prices, and times must be written as words such as "тридцять чотири гривні" and "п'ятнадцяте травня".
- **Item and sentence limits:** a maximum of two items per sentence; the total response should be one or two short sentences.
- **Tool-call fillers:** insert a short filler phrase immediately before the tool call, for example "Секунду.", "Дай перевірю.", or "Хвилинку."

### 4.1 Respeecher configuration

- `TTS_ENABLED` (`bool`, default: `False`): global speech enable flag.
- `TTS_MOCK_MODE` (`bool`, default: `True`): when `True`, returns the local audio path `/static/audio/mock_response.mp3`.
- **Error fallback:** a TTS failure must not block the main `summary_message`; set `audio_url = None` instead.

## 5. SSE protocol contract (`POST /api/agent/stream`)

Event names are defined in `SSEEvent` (`app/enums.py`) and emitted via
`fastapi.sse.ServerSentEvent` with `response_class=EventSourceResponse`:

- `event: session_info` → `{"thread_id": "string"}`
- `event: thinking_step` → `{"node": "string", "status": "string"}`
- `event: tool_start` → `{"tool": "string", "details": dict}`
- `event: tool_end` → `{"tool": "string", "status": "string"}`
- `event: node_complete` → `{"node": "string", "cart_url": "string", "summary": "string", "audio_url": "string"}`


