from app.enums import IntentEnum
from app.nodes.create_cart import create_cart_node
from app.state import AgentState


def test_create_cart_node_generates_url_and_summary() -> None:
    state: AgentState = {
        "audio_bytes": None,
        "user_text": "Збери кошик для пікніка",
        "intent": IntentEnum.PARTY,
        "budget": 2500.0,
        "people_count": 6,
        "dietary_restrictions": ["vegetarian"],
        "raw_item_requests": ["м'ясо", "овочі"],
        "calculated_items": [],
        "mcp_products": [
            {
                "id": "sku-1",
                "title": "Ошийник свинячий",
                "price": 240.0,
                "is_private_label": False,
                "quantity": 2,
            },
            {
                "id": "sku-2",
                "title": "Овочі для гриля Премія",
                "price": 85.0,
                "is_private_label": True,
                "quantity": 2,
            },
        ],
        "total_price": 650.0,
        "attempts": 1,
        "max_attempts": 3,
        "is_budget_exceeded": False,
        "cart_url": None,
        "summary_message": "",
        "audio_url": None,
        "messages": [],
    }
    result = create_cart_node(state)
    assert "cart_url" in result
    assert result["cart_url"] is not None
    assert result["cart_url"].startswith("https://silpo.ua/cart")
    assert "summary_message" in result
    assert len(result["summary_message"]) > 0
