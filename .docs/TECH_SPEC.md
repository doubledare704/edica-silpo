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
    PARSE_INTENT = "parse_intent"
    PLAN_DOMAIN_LOGIC = "plan_domain_logic"
    MCP_FETCH = "mcp_fetch"
    CHECK_CONSTRAINTS = "check_constraints"
    CREATE_CART = "create_cart"
    TTS = "tts"
```

## 2. State topology (`app/state.py`)

```python
from typing import Any, TypedDict

from langchain_core.messages import BaseMessage

from .enums import IntentEnum


class AgentState(TypedDict):
    audio_bytes: bytes | None
    user_text: str | None
    intent: IntentEnum | None
    budget: float
    people_count: int | None
    dietary_restrictions: list[str]
    raw_item_requests: list[str]
    calculated_items: list[dict[str, Any]]
    mcp_products: list[dict[str, Any]]
    total_price: float
    attempts: int
    max_attempts: int
    is_budget_exceeded: bool
    cart_url: str | None
    summary_message: str
    audio_url: str | None
    messages: list[BaseMessage]
```

## 3. LangGraph topology and conditional edges

```text
[STT] ➔ [PARSE_INTENT] ➔ [PLAN_DOMAIN_LOGIC] ➔ [MCP_FETCH] ➔ [CHECK_CONSTRAINTS]
                                                                      |
            ┌───────────────────────────────────────────────────────┴────┐
            │ [is_budget_exceeded && attempts < max_attempts]          │
            ▼                                                          ▼
      [PLAN_DOMAIN_LOGIC]                                          [CREATE_CART]
                                                                      │
                                                                      ▼
                                                                   [TTS] ➔ END
```

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

- `event: session_info` → `{"thread_id": "string"}`
- `event: thinking_step` → `{"node": "string", "status": "string"}`
- `event: tool_start` → `{"tool": "string", "details": dict}`
- `event: tool_end` → `{"tool": "string", "status": "string"}`
- `event: node_complete` → `{"node": "string", "cart_url": "string", "summary": "string", "audio_url": "string"}`


