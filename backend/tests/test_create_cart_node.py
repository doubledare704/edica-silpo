from types import SimpleNamespace

import pytest
from app.enums import IntentEnum
from app.nodes.create_cart import create_cart_node
from app.services import mcp_service
from app.state import AgentState


@pytest.mark.asyncio
async def test_create_cart_node_generates_url_and_summary(monkeypatch) -> None:
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
    monkeypatch.setattr(mcp_service.settings, "MCP_MOCK_MODE", True)

    result = await create_cart_node(state)
    assert "cart_url" in result
    assert result["cart_url"] is not None
    assert result["cart_url"].startswith("https://silpo.ua/cart")
    assert "summary_message" in result
    assert len(result["summary_message"]) > 0


@pytest.mark.asyncio
async def test_create_cart_node_updates_real_cart(monkeypatch) -> None:
    class FakeClient:
        def __init__(self) -> None:
            self.cleared_cart_ids: list[str] = []
            self.updated_cart: tuple[str, list[dict[str, object]]] | None = None

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> None:
            return None

        async def get_cart(self):
            return SimpleNamespace(id="cart-123", items=[{"productId": "old-product"}])

        async def clear_cart(self, cart_id: str):
            self.cleared_cart_ids.append(cart_id)

        async def add_or_update_cart_products(self, cart_id: str, items: list[dict[str, object]]):
            self.updated_cart = (cart_id, items)
            return SimpleNamespace(share_url="https://silpo.ua/cart/share/cart-123")

    client = FakeClient()
    monkeypatch.setattr(mcp_service.settings, "MCP_MOCK_MODE", False)
    monkeypatch.setattr(mcp_service.SilpoClient, "for_real_server", lambda: client)

    state = {
        "intent": IntentEnum.PARTY,
        "people_count": 2,
        "total_price": 120.0,
        "mcp_products": [
            {
                "id": "product-1",
                "productId": "product-1",
                "companyId": "company-1",
                "branchId": "branch-1",
                "quantity": 2,
            }
        ],
    }

    result = await create_cart_node(state)

    assert result["cart_url"] == "https://silpo.ua/cart/share/cart-123"
    assert client.cleared_cart_ids == ["cart-123"]
    assert client.updated_cart == (
        "cart-123",
        [{"productId": "product-1", "companyId": "company-1", "branchId": "branch-1", "quantity": 2}],
    )


@pytest.mark.asyncio
async def test_create_cart_node_keeps_summary_when_real_cart_fails(monkeypatch) -> None:
    async def fail_create_cart(products):
        raise RuntimeError("MCP unavailable")

    monkeypatch.setattr(mcp_service.settings, "MCP_MOCK_MODE", False)
    monkeypatch.setattr(mcp_service.mcp_product_service, "create_cart", fail_create_cart)

    result = await create_cart_node(
        {
            "intent": IntentEnum.PARTY,
            "people_count": 2,
            "total_price": 120.0,
            "mcp_products": [{"id": "product-1", "quantity": 1}],
        }
    )

    assert result["cart_url"].startswith("https://silpo.ua/cart/share/mock_")
    assert result["summary_message"]
