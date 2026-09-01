import pytest
from app.enums import IntentEnum, NodeName
from app.graph import create_silpo_agent_graph
from app.state import AgentState


@pytest.mark.asyncio
async def test_silpo_agent_graph_full_run() -> None:
    graph = create_silpo_agent_graph()
    initial_state: AgentState = {
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
    # Check that all spec nodes are in the graph definition
    for node in NodeName:
        assert node.value in graph.nodes or node in graph.nodes
