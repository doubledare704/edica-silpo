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
