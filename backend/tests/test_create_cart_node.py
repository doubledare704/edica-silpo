from types import SimpleNamespace

import pytest
from app.enums import IntentEnum
from app.nodes.create_cart import create_cart_node
from app.services import mcp_service
from app.state import SilpoAgentState


@pytest.mark.asyncio
async def test_create_cart_node_generates_url_and_summary(monkeypatch) -> None:
    state: SilpoAgentState = {
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

        async def get_delivery_addresses(self):
            return []

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
async def test_create_cart_node_creates_missing_cart_from_saved_address(monkeypatch) -> None:
    class FakeClient:
        def __init__(self) -> None:
            self.created_kwargs: dict[str, object] | None = None
            self.updated_cart: tuple[str, list[dict[str, object]]] | None = None

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> None:
            return None

        async def get_cart(self):
            return SimpleNamespace(cart_id=None, shopping_cart_id=None, exists=False)

        async def get_delivery_addresses(self):
            return [
                SimpleNamespace(
                    address_id="addr-1",
                    text="Київ, вул. Анни Ахматової, 9",
                    coordinates={"lat": 50.3957, "lng": 30.6217},
                )
            ]

        async def get_available_delivery_types(self, **kwargs):
            return [SimpleNamespace(type="SelfPickup", branch_id="bran-1", min_order=0.0)]

        async def call_tool(self, name, args):
            return [
                {
                    "deliveryType": "SelfPickup",
                    "branchId": "bran-1",
                    "startsAt": "2026-09-06T10:00:00",
                    "endsAt": "2026-09-06T12:00:00",
                    "isAvailable": True,
                }
            ]

        async def create_shopping_cart(self, **kwargs):
            self.created_kwargs = kwargs
            return SimpleNamespace(success=True, shopping_cart_id="cart-new")

        async def add_or_update_cart_products(self, cart_id: str, items: list[dict[str, object]]):
            self.updated_cart = (cart_id, items)
            return SimpleNamespace(share_url="https://silpo.ua/cart/share/cart-new")

    client = FakeClient()
    monkeypatch.setattr(mcp_service.settings, "MCP_MOCK_MODE", False)
    monkeypatch.setattr(mcp_service.SilpoClient, "for_real_server", lambda: client)

    result = await create_cart_node(
        {
            "intent": IntentEnum.PARTY,
            "people_count": 2,
            "total_price": 120.0,
            "mcp_products": [{"id": "product-1", "productId": "product-1", "quantity": 1}],
        }
    )

    assert result["cart_url"] == "https://silpo.ua/cart/share/cart-new"
    assert client.created_kwargs is not None
    assert client.created_kwargs["branch_id"] == "bran-1"
    assert client.updated_cart is not None and client.updated_cart[0] == "cart-new"
    assert result["fulfillment"] is not None
    assert result["fulfillment"]["branch_id"] == "bran-1"


@pytest.mark.asyncio
async def test_create_cart_node_falls_back_when_fulfillment_unresolvable(monkeypatch) -> None:
    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> None:
            return None

        async def get_cart(self):
            return SimpleNamespace(cart_id=None, shopping_cart_id=None, exists=False)

        async def get_delivery_addresses(self):
            return []

    monkeypatch.setattr(mcp_service.settings, "MCP_MOCK_MODE", False)
    monkeypatch.setattr(mcp_service.SilpoClient, "for_real_server", lambda: FakeClient())

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
    assert result["fulfillment"] is None


@pytest.mark.asyncio
async def test_create_cart_node_keeps_summary_when_real_cart_fails(monkeypatch) -> None:
    async def fail_create_cart(products, fulfillment=None):
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
