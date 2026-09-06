import pytest
from app.enums import IntentEnum, NodeName
from app.graph import create_silpo_agent_graph, route_constraints
from app.state import SilpoAgentState


@pytest.mark.asyncio
async def test_silpo_agent_graph_full_run() -> None:
    graph = create_silpo_agent_graph()
    initial_state: SilpoAgentState = {
        "audio_bytes": None,
        "user_text": "Збери кошик для пікніка на 6 людей до 2500 грн, один вегетаріанець",
        "intent": None,
        "budget": 0.0,
        "people_count": None,
        "dietary_restrictions": [],
        "raw_item_requests": [],
        "calculated_items": [],
        "mcp_products": [],
        "total_price": 0.0,
        "attempts": 0,
        "max_attempts": 3,
        "is_budget_exceeded": False,
        "cart_url": None,
        "summary_message": "",
        "audio_url": None,
        "messages": [],
    }
    config = {"configurable": {"thread_id": "test-session-123"}}
    final_state = await graph.ainvoke(initial_state, config=config)

    assert final_state["intent"] == IntentEnum.PARTY
    assert final_state["cart_url"] is not None
    assert final_state["cart_url"].startswith("https://silpo.ua/cart")
    assert len(final_state["mcp_products"]) > 0
    assert final_state["total_price"] > 0
    assert len(final_state["summary_message"]) > 0


@pytest.mark.asyncio
async def test_silpo_agent_graph_nodes_registered() -> None:
    graph = create_silpo_agent_graph()
    expected_nodes = [
        NodeName.STT,
        NodeName.PARSE_INTENT,
        NodeName.PLAN_DOMAIN_LOGIC,
        NodeName.PICKER,
        NodeName.CHECK_CONSTRAINTS,
        NodeName.CREATE_CART,
        NodeName.TTS,
    ]
    for node in expected_nodes:
        assert node.value in graph.nodes, f"missing graph node {node}"


@pytest.mark.asyncio
async def test_silpo_agent_graph_ends_unsupported_request_before_planning() -> None:
    graph = create_silpo_agent_graph()
    initial_state: SilpoAgentState = {
        "user_text": "Привіт, як справи? бла-бла-бла",
        "messages": [],
    }

    final_state = await graph.ainvoke(initial_state, config={"configurable": {"thread_id": "unsupported-request"}})

    assert final_state["intent"] == IntentEnum.UNSUPPORTED
    assert final_state["summary_message"]
    assert final_state.get("calculated_items") is None
    assert final_state.get("mcp_products") is None
    assert final_state.get("cart_url") is None


def test_route_constraints_loops_only_while_attempts_remain() -> None:
    assert route_constraints({"is_budget_exceeded": True, "attempts": 1, "max_attempts": 3}) == (NodeName.PICKER.value)
    assert route_constraints({"is_budget_exceeded": True, "attempts": 3, "max_attempts": 3}) == (
        NodeName.CREATE_CART.value
    )
    assert route_constraints({"is_budget_exceeded": False, "attempts": 1, "max_attempts": 3}) == (
        NodeName.CREATE_CART.value
    )
