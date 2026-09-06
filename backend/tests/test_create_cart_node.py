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

        async def get_cart_by_id(self, cart_id: str):
            return {
                "cartId": cart_id,
                "branchId": "branch-1",
                "deliveryType": "SelfPickup",
                "timeslot": {"startsAt": "2026-09-06T10:00:00", "endsAt": "2026-09-06T12:00:00"},
                "items": [],
                "totals": {"totalPrice": 480.0},
                "loyalty": {"isEnabled": False, "bonusAvailable": 0.0, "bonusRequested": None},
                "validations": [],
                "checkoutWebLink": "https://silpo.ua/checkout/cart-123",
                "checkoutMobileLink": "silpo://cart/cart-123",
            }

        async def get_delivery_addresses(self):
            return []

        async def clear_cart(self, cart_id: str):
            self.cleared_cart_ids.append(cart_id)

        async def add_or_update_cart_products(self, cart_id: str, products: list[dict[str, object]]):
            self.updated_cart = (cart_id, products)
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
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "productId": "123e4567-e89b-12d3-a456-426614174000",
                "companyId": "company-1",
                "branchId": "branch-1",
                "quantity": 2,
            }
        ],
    }

    result = await create_cart_node(state)

    assert result["cart_url"] == "https://silpo.ua/checkout/cart-123"
    assert result["checkout_url"] == "https://silpo.ua/checkout/cart-123"
    assert result["total_price"] == 480.0
    assert client.cleared_cart_ids == []
    assert client.updated_cart == (
        "cart-123",
        [
            {
                "productId": "123e4567-e89b-12d3-a456-426614174000",
                "companyId": "company-1",
                "branchId": "branch-1",
                "quantity": 2,
            }
        ],
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

        async def get_time_slots(self, branch_id, **kwargs):
            assert branch_id == "bran-1"
            return [
                SimpleNamespace(
                    startsAt="2026-09-06T10:00:00",
                    endsAt="2026-09-06T12:00:00",
                    isAvailable=True,
                )
            ]

        async def call_tool(self, name, args):
            raise AssertionError(f"unexpected call_tool: {name}")

        async def create_shopping_cart(self, **kwargs):
            self.created_kwargs = kwargs
            return SimpleNamespace(success=True, shopping_cart_id="cart-new")

        async def get_cart_by_id(self, cart_id: str):
            return {
                "cartId": cart_id,
                "branchId": "bran-1",
                "deliveryType": "SelfPickup",
                "timeslot": {"startsAt": "2026-09-06T10:00:00", "endsAt": "2026-09-06T12:00:00"},
                "items": [],
                "totals": {"totalPrice": 120.0},
                "loyalty": {"isEnabled": False, "bonusAvailable": 0.0, "bonusRequested": None},
                "validations": [],
                "checkoutWebLink": "https://silpo.ua/checkout/cart-new",
                "checkoutMobileLink": "silpo://cart/cart-new",
            }

        async def add_or_update_cart_products(self, cart_id: str, products: list[dict[str, object]]):
            self.updated_cart = (cart_id, products)
            return SimpleNamespace(share_url="https://silpo.ua/cart/share/cart-new")

    client = FakeClient()
    monkeypatch.setattr(mcp_service.settings, "MCP_MOCK_MODE", False)
    monkeypatch.setattr(mcp_service.SilpoClient, "for_real_server", lambda: client)

    result = await create_cart_node(
        {
            "intent": IntentEnum.PARTY,
            "people_count": 2,
            "total_price": 120.0,
            "mcp_products": [
                {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "productId": "123e4567-e89b-12d3-a456-426614174000",
                    "companyId": "company-1",
                    "branchId": "branch-1",
                    "quantity": 1,
                }
            ],
        }
    )

    assert result["cart_url"] == "https://silpo.ua/checkout/cart-new"
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


@pytest.mark.asyncio
async def test_create_cart_rejects_fallback_skus_without_touching_cart(monkeypatch) -> None:
    class GuardClient:
        def __init__(self) -> None:
            self.calls: list[str] = []

        async def __aenter__(self):
            self.calls.append("connect")
            return self

        async def __aexit__(self, *args) -> None:
            return None

        def __getattr__(self, name: str):
            async def _boom(*args: object, **kwargs: object):
                self.calls.append(name)
                raise AssertionError(f"cart must not be touched, called {name}")

            return _boom

    client = GuardClient()
    monkeypatch.setattr(mcp_service.settings, "MCP_MOCK_MODE", False)
    monkeypatch.setattr(mcp_service.SilpoClient, "for_real_server", lambda: client)

    with pytest.raises(ValueError, match="not real Silpo products"):
        await mcp_service.MCPProductService().create_cart(
            [
                {"id": "sku-1", "productId": "sku-1", "title": "Ошийник свинячий", "price": 240.0, "quantity": 1},
                {"id": "sku-2", "title": "Без productId", "price": 10.0, "quantity": 1},
            ]
        )
    assert client.calls == []


@pytest.mark.asyncio
async def test_create_cart_accepts_real_uuid_products(monkeypatch) -> None:
    seen: dict[str, object] = {}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> None:
            return None

        async def get_cart(self):
            return SimpleNamespace(id="cart-123", items=[])

        async def get_cart_by_id(self, cart_id: str):
            return {
                "cartId": cart_id,
                "branchId": "bran-1",
                "deliveryType": "SelfPickup",
                "timeslot": {"startsAt": "2026-09-06T10:00:00", "endsAt": "2026-09-06T12:00:00"},
                "items": [],
                "totals": {"totalPrice": 240.0},
                "loyalty": {"isEnabled": False, "bonusAvailable": 0.0, "bonusRequested": None},
                "validations": [],
                "checkoutWebLink": "https://silpo.ua/checkout/cart-123",
                "checkoutMobileLink": "silpo://cart/cart-123",
            }

        async def add_or_update_cart_products(self, cart_id: str, products: list[dict[str, object]]):
            seen["products"] = products
            return SimpleNamespace(share_url="https://silpo.ua/cart/share/cart-123")

    monkeypatch.setattr(mcp_service.settings, "MCP_MOCK_MODE", False)
    monkeypatch.setattr(mcp_service.SilpoClient, "for_real_server", FakeClient)

    url = await mcp_service.MCPProductService().create_cart(
        [
            {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "productId": "123e4567-e89b-12d3-a456-426614174000",
                "companyId": "company-1",
                "branchId": "branch-1",
                "quantity": 2,
            }
        ]
    )
    assert url["cart_url"] == "https://silpo.ua/checkout/cart-123"
    assert url["verified_total"] == 240.0
    assert seen["products"] == [
        {
            "productId": "123e4567-e89b-12d3-a456-426614174000",
            "companyId": "company-1",
            "branchId": "branch-1",
            "quantity": 2,
        }
    ]


@pytest.mark.asyncio
async def test_create_cart_node_keeps_computed_total_when_verified_total_is_zero(monkeypatch) -> None:
    """Live Silpo returns totals.totalPrice=0.0 right after write; it must not clobber the computed total."""

    class ZeroTotalClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> None:
            return None

        async def get_cart(self):
            return SimpleNamespace(cart_id="cart-zero", shopping_cart_id="cart-zero", exists=True)

        async def get_cart_by_id(self, cart_id: str):
            return {
                "cartId": cart_id,
                "branchId": "bran-1",
                "deliveryType": "SelfPickup",
                "timeslot": {"startsAt": "2026-09-06T10:00:00", "endsAt": "2026-09-06T12:00:00"},
                "items": [],
                "totals": {"totalPrice": 0.0},
                "loyalty": {"isEnabled": False, "bonusAvailable": 0.0, "bonusRequested": None},
                "validations": [],
                "checkoutWebLink": "https://silpo.ua/checkout/cart-zero",
                "checkoutMobileLink": "silpo://cart/cart-zero",
            }

        async def add_or_update_cart_products(self, cart_id: str, products: list[dict[str, object]]):
            return SimpleNamespace(share_url="https://silpo.ua/cart/share/cart-zero")

    monkeypatch.setattr(mcp_service.settings, "MCP_MOCK_MODE", False)
    monkeypatch.setattr(mcp_service.SilpoClient, "for_real_server", ZeroTotalClient)

    fulfillment = {
        "address_type": "delivery",
        "latitude": 50.4,
        "longitude": 30.6,
        "delivery_type": "SelfPickup",
        "branch_id": "bran-1",
        "timeslot_start": "2026-09-06T10:00:00",
        "timeslot_end": "2026-09-06T12:00:00",
    }
    result = await create_cart_node(
        {
            "intent": IntentEnum.PARTY,
            "people_count": 2,
            "total_price": 480.0,
            "fulfillment": fulfillment,
            "mcp_products": [
                {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "productId": "123e4567-e89b-12d3-a456-426614174000",
                    "companyId": "company-1",
                    "branchId": "branch-1",
                    "title": "Ошийник свинячий",
                    "price": 240.0,
                    "quantity": 2,
                }
            ],
        }
    )

    assert result["total_price"] == 480.0


@pytest.mark.asyncio
async def test_create_cart_node_accepts_verified_total_when_server_returns_one(monkeypatch) -> None:
    """A genuine non-zero server total is still authoritative."""

    class ServerTotalClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> None:
            return None

        async def get_cart(self):
            return SimpleNamespace(cart_id="cart-real", shopping_cart_id="cart-real", exists=True)

        async def get_cart_by_id(self, cart_id: str):
            return {
                "cartId": cart_id,
                "branchId": "bran-1",
                "deliveryType": "SelfPickup",
                "timeslot": {"startsAt": "2026-09-06T10:00:00", "endsAt": "2026-09-06T12:00:00"},
                "items": [],
                "totals": {"totalPrice": 525.5},
                "loyalty": {"isEnabled": False, "bonusAvailable": 0.0, "bonusRequested": None},
                "validations": [],
                "checkoutWebLink": "https://silpo.ua/checkout/cart-real",
                "checkoutMobileLink": "silpo://cart/cart-real",
            }

        async def add_or_update_cart_products(self, cart_id: str, products: list[dict[str, object]]):
            return SimpleNamespace(share_url="https://silpo.ua/cart/share/cart-real")

    monkeypatch.setattr(mcp_service.settings, "MCP_MOCK_MODE", False)
    monkeypatch.setattr(mcp_service.SilpoClient, "for_real_server", ServerTotalClient)

    fulfillment = {
        "address_type": "delivery",
        "latitude": 50.4,
        "longitude": 30.6,
        "delivery_type": "SelfPickup",
        "branch_id": "bran-1",
        "timeslot_start": "2026-09-06T10:00:00",
        "timeslot_end": "2026-09-06T12:00:00",
    }
    result = await create_cart_node(
        {
            "intent": IntentEnum.PARTY,
            "people_count": 2,
            "total_price": 480.0,
            "fulfillment": fulfillment,
            "mcp_products": [
                {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "productId": "123e4567-e89b-12d3-a456-426614174000",
                    "companyId": "company-1",
                    "branchId": "branch-1",
                    "title": "Ошийник свинячий",
                    "price": 240.0,
                    "quantity": 2,
                }
            ],
        }
    )

    assert result["total_price"] == 525.5
