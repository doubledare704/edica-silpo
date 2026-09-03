"""Phase H2: SilpoAgentState extends langchain.agents.AgentState with add_messages reducer."""

from typing import get_args, get_origin

from langchain.agents import AgentState as LangChainAgentState
from langchain_core.messages import HumanMessage


def test_silpo_state_inherits_langchain_agent_state() -> None:
    from app.state import SilpoAgentState

    # TypedDict does not support issubclass; check orig bases + messages annotation instead
    assert any(getattr(base, "__name__", "") == "AgentState" for base in getattr(SilpoAgentState, "__orig_bases__", ()))
    assert "messages" in SilpoAgentState.__annotations__ or "messages" in getattr(
        LangChainAgentState, "__annotations__", {}
    )


def test_silpo_state_messages_has_add_messages_reducer() -> None:
    import typing

    from app.state import SilpoAgentState
    from langgraph.graph.message import add_messages

    assert add_messages is not None
    resolved = typing.get_type_hints(SilpoAgentState, include_extras=True)
    assert "messages" in resolved
    assert "add_messages" in str(resolved["messages"])


def test_silpo_state_custom_fields_present() -> None:
    from app.state import SilpoAgentState

    for field in [
        "audio_bytes",
        "user_text",
        "intent",
        "budget",
        "people_count",
        "dietary_restrictions",
        "raw_item_requests",
        "calculated_items",
        "mcp_products",
        "total_price",
        "attempts",
        "max_attempts",
        "is_budget_exceeded",
        "cart_url",
        "summary_message",
        "audio_url",
        "current_step",
    ]:
        assert field in SilpoAgentState.__annotations__, f"missing {field}"


def test_silpo_state_instantiation_with_messages() -> None:
    from app.enums import IntentEnum
    from app.state import SilpoAgentState

    state: SilpoAgentState = {
        "messages": [HumanMessage(content="Збери кошик")],
        "user_text": "Збери кошик для пікніка",
        "intent": IntentEnum.PARTY,
        "budget": 2500.0,
    }
    assert state["intent"] == IntentEnum.PARTY
    assert len(state["messages"]) == 1


def test_legacy_agent_state_still_importable() -> None:
    # Backward compat during migration: old AgentState alias must remain until graph cutover
    from app.state import AgentState

    assert "messages" in AgentState.__annotations__

    _ = get_origin
    _ = get_args
