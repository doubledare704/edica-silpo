import pytest
from app.enums import IntentEnum
from app.nodes.mcp_fetch import mcp_fetch_node
from app.state import AgentState


@pytest.mark.asyncio
async def test_mcp_fetch_node_returns_products() -> None:
    state: AgentState = {
        "audio_bytes": None,
        "user_text": "Збери кошик",
        "intent": IntentEnum.PARTY,
        "budget": 2500.0,
        "people_count": 6,
        "dietary_restrictions": ["vegetarian"],
        "raw_item_requests": ["м'ясо", "овочі"],
        "calculated_items": [
            {
                "query": "Ошийник свинячий",
                "category": "meat",
                "quantity": 2,
                "prefer_private_label": False,
            },
            {
                "query": "Овочі для гриля Премія",
                "category": "vegetables",
                "quantity": 2,
                "prefer_private_label": True,
            },
        ],
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
    result = await mcp_fetch_node(state)
    assert "mcp_products" in result
    products = result["mcp_products"]
    assert len(products) >= 2
    for p in products:
        assert "id" in p
        assert "title" in p
        assert "price" in p
        assert "is_private_label" in p
        assert "quantity" in p
