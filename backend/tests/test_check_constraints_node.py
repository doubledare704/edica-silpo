import pytest
from app.nodes.check_constraints import check_constraints_node
from app.state import AgentState


@pytest.mark.asyncio
async def test_check_constraints_within_budget() -> None:
    state: AgentState = {
        "audio_bytes": None,
        "user_text": None,
        "intent": None,
        "budget": 1000.0,
        "people_count": None,
        "dietary_restrictions": [],
        "raw_item_requests": [],
        "calculated_items": [],
        "mcp_products": [
            {
                "id": "sku-1",
                "title": "Ошийник",
                "price": 240.0,
                "is_private_label": False,
                "quantity": 2,
            },
            {
                "id": "sku-2",
                "title": "Овочі",
                "price": 85.0,
                "is_private_label": True,
                "quantity": 2,
            },
        ],
        "total_price": 0.0,
        "attempts": 0,
        "max_attempts": 3,
        "is_budget_exceeded": False,
        "cart_url": None,
        "summary_message": "",
        "audio_url": None,
        "messages": [],
    }
    result = await check_constraints_node(state)
    assert result["total_price"] == 650.0
    assert result["attempts"] == 1
    assert result["is_budget_exceeded"] is False


@pytest.mark.asyncio
async def test_check_constraints_budget_exceeded() -> None:
    state: AgentState = {
        "audio_bytes": None,
        "user_text": None,
        "intent": None,
        "budget": 500.0,
        "people_count": None,
        "dietary_restrictions": [],
        "raw_item_requests": [],
        "calculated_items": [],
        "mcp_products": [
            {
                "id": "sku-1",
                "title": "Ошийник",
                "price": 240.0,
                "is_private_label": False,
                "quantity": 2,
            },
            {
                "id": "sku-2",
                "title": "Овочі",
                "price": 85.0,
                "is_private_label": True,
                "quantity": 2,
            },
        ],
        "total_price": 0.0,
        "attempts": 0,
        "max_attempts": 3,
        "is_budget_exceeded": False,
        "cart_url": None,
        "summary_message": "",
        "audio_url": None,
        "messages": [],
    }
    result = await check_constraints_node(state)
    assert result["total_price"] == 650.0
    assert result["attempts"] == 1
    assert result["is_budget_exceeded"] is True
