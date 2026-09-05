from typing import Any, get_type_hints

from app.enums import IntentEnum
from app.state import AgentState, SilpoAgentState
from langchain_core.messages import HumanMessage
from langgraph.graph.message import add_messages


def test_agent_state_annotations() -> None:
    hints = get_type_hints(AgentState)
    assert hints["audio_bytes"] == bytes | None
    assert hints["user_text"] == str | None
    assert hints["intent"] == IntentEnum | None
    assert hints["budget"] is float
    assert hints["people_count"] == int | None
    assert hints["dietary_restrictions"] == list[str]
    assert hints["raw_item_requests"] == list[str]
    assert hints["calculated_items"] == list[dict[str, Any]]
    assert hints["mcp_products"] == list[dict[str, Any]]
    assert hints["total_price"] is float
    assert hints["attempts"] is int
    assert hints["max_attempts"] is int
    assert hints["is_budget_exceeded"] is bool
    assert hints["cart_url"] == str | None
    assert hints["summary_message"] is str
    assert hints["audio_url"] == str | None
    assert "add_messages" in str(get_type_hints(AgentState, include_extras=True)["messages"])


def test_agent_state_is_the_graph_state() -> None:
    assert AgentState is SilpoAgentState
    assert add_messages is not None


def test_agent_state_instantiation() -> None:
    state: AgentState = {
        "audio_bytes": None,
        "user_text": "Збери кошик для пікніка",
        "intent": IntentEnum.PARTY,
        "budget": 2500.0,
        "people_count": 6,
        "dietary_restrictions": ["vegetarian"],
        "raw_item_requests": ["м'ясо", "овочі"],
        "calculated_items": [{"name": "meat", "quantity": 1}],
        "mcp_products": [{"id": "sku-1", "title": "Ошийник", "price": 240.0}],
        "total_price": 240.0,
        "attempts": 0,
        "max_attempts": 3,
        "is_budget_exceeded": False,
        "cart_url": "https://silpo.ua/cart/mock",
        "summary_message": "Зібрано кошик",
        "audio_url": "/static/audio/mock.mp3",
        "messages": [HumanMessage(content="Збери кошик")],
    }
    assert state["intent"] == IntentEnum.PARTY
    assert state["budget"] == 2500.0
    assert len(state["messages"]) == 1
