from enum import StrEnum


class IntentEnum(StrEnum):
    PARTY = "party"
    BUDGET = "budget"
    OFFICE = "office"
    GOURMET = "gourmet"
    UNSUPPORTED = "unsupported"


class NodeName(StrEnum):
    STT = "stt"
    SHOPPER_AGENT = "shopper_agent"
    PARSE_INTENT = "parse_intent"
    UNSUPPORTED = "unsupported"
    PLAN_DOMAIN_LOGIC = "plan_domain_logic"
    MCP_FETCH = "mcp_fetch"
    CHECK_CONSTRAINTS = "check_constraints"
    CREATE_CART = "create_cart"
    TTS = "tts"


class SSEEvent(StrEnum):
    SESSION_INFO = "session_info"
    THINKING_STEP = "thinking_step"
    TOOL_START = "tool_start"
    TOOL_END = "tool_end"
    NODE_COMPLETE = "node_complete"
