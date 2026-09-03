from enum import StrEnum

from app.enums import IntentEnum, NodeName, SSEEvent


def test_intent_enum_values() -> None:
    assert issubclass(IntentEnum, StrEnum)
    assert IntentEnum.PARTY == "party"
    assert IntentEnum.BUDGET == "budget"
    assert IntentEnum.OFFICE == "office"
    assert IntentEnum.GOURMET == "gourmet"
    assert len(IntentEnum) == 4


def test_node_name_values() -> None:
    assert issubclass(NodeName, StrEnum)
    assert NodeName.STT == "stt"
    assert NodeName.SHOPPER_AGENT == "shopper_agent"
    assert NodeName.PARSE_INTENT == "parse_intent"
    assert NodeName.PLAN_DOMAIN_LOGIC == "plan_domain_logic"
    assert NodeName.MCP_FETCH == "mcp_fetch"
    assert NodeName.CHECK_CONSTRAINTS == "check_constraints"
    assert NodeName.CREATE_CART == "create_cart"
    assert NodeName.TTS == "tts"
    assert len(NodeName) == 8


def test_sse_event_values() -> None:
    assert issubclass(SSEEvent, StrEnum)
    assert SSEEvent.SESSION_INFO == "session_info"
    assert SSEEvent.THINKING_STEP == "thinking_step"
    assert SSEEvent.TOOL_START == "tool_start"
    assert SSEEvent.TOOL_END == "tool_end"
    assert SSEEvent.NODE_COMPLETE == "node_complete"
    assert len(SSEEvent) == 5
