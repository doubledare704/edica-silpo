"""Official Silpo flow: cart-first context, slot validation, verify-after-write."""

from types import SimpleNamespace

import pytest
from app.services import mcp_service
from app.services.mcp_service import MCPProductService

UUID_A = "123e4567-e89b-12d3-a456-426614174000"
UUID_B = "223e4567-e89b-12d3-a456-426614174001"
SLOT_S = "2026-09-07T06:00:00+00:00"
SLOT_E = "2026-09-07T07:30:00+00:00"


def _slot(start: str, end: str) -> SimpleNamespace:
    return SimpleNamespace(starts_at=start, ends_at=end, is_available=True)


def _cart_detail(**overrides: object) -> dict:
    detail = {
        "cartId": "cart-1",
        "branchId": "bran-1",
        "deliveryType": "SelfPickup",
        "timeslot": {"startsAt": SLOT_S, "endsAt": SLOT_E},
        "items": [],
        "totals": {"totalPrice": 100.0, "itemsPrice": 100.0, "deliveryPrice": 0.0, "discount": 0.0},
        "loyalty": {"isEnabled": False, "bonusAvailable": 0.0, "bonusRequested": None, "bonusApplied": 0.0},
        "validations": [],
        "checkoutWebLink": "https://silpo.ua/checkout/cart-1",
        "checkoutMobileLink": "silpo://cart/cart-1",
    }
    detail.update(overrides)
    return detail


class OfficialFakeClient:
    def __init__(
        self,
        *,
        cart_id: str | None = "cart-1",
        detail: dict | None = None,
        slots: list | None = None,
    ) -> None:
        self._cart_id = cart_id
        self._detail = detail if detail is not None else _cart_detail()
        self._slots = slots if slots is not None else [_slot(SLOT_S, SLOT_E)]
        self.calls: list[str] = []
        self.updated: dict | None = None
        self.added: list | None = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args) -> None:
        return None

    async def get_cart(self):
        self.calls.append("get_cart")
        if self._cart_id is None:
            return SimpleNamespace(cart_id=None, shopping_cart_id=None, exists=False)
        return SimpleNamespace(cart_id=self._cart_id, shopping_cart_id=self._cart_id, exists=True)

    async def get_cart_by_id(self, cart_id: str):
        self.calls.append("get_cart_by_id")
        return dict(self._detail)

    async def get_time_slots(self, branch_id: str, **kwargs):
        self.calls.append("get_time_slots")
        return list(self._slots)

    async def find_address(self, text: str):
        self.calls.append("find_address")
        raise AssertionError("cart-first context must not geocode when cart detail exists")

    async def get_delivery_addresses(self):
        return []

    async def add_or_update_cart_products(self, cart_id: str, products: list):
        self.calls.append("add_or_update_cart_products")
        self.added = products
        return SimpleNamespace(cart={}, changed=True)

    async def update_shopping_cart(self, *args, **kwargs):
        self.calls.append("update_shopping_cart")
        self.updated = {"args": args, **kwargs}
        return SimpleNamespace(cart={}, changed=True)

    async def create_shopping_cart(self, **kwargs):
        self.calls.append("create_shopping_cart")
        return SimpleNamespace(shopping_cart_id="cart-new")


def _patch(monkeypatch, client: OfficialFakeClient) -> None:
    monkeypatch.setattr(mcp_service.settings, "MCP_MOCK_MODE", False)
    monkeypatch.setattr(mcp_service.SilpoClient, "for_real_server", lambda: client)


def _product(pid: str) -> dict:
    return {"productId": pid, "companyId": "c1", "branchId": "bran-1", "quantity": 1, "title": pid}


@pytest.mark.asyncio
async def test_context_prefers_existing_cart_detail(monkeypatch) -> None:
    client = OfficialFakeClient()
    _patch(monkeypatch, client)
    ctx = await MCPProductService().resolve_shopping_context("Київ, вул. Мишуги, 4")
    assert ctx == {
        "branch_id": "bran-1",
        "delivery_type": "SelfPickup",
        "timeslot_start": SLOT_S,
        "timeslot_end": SLOT_E,
    }
    assert "find_address" not in client.calls


@pytest.mark.asyncio
async def test_context_replaces_stale_slot_with_first_available(monkeypatch) -> None:
    client = OfficialFakeClient(slots=[_slot("2026-09-08T06:00:00+00:00", "2026-09-08T07:30:00+00:00")])
    _patch(monkeypatch, client)
    ctx = await MCPProductService().resolve_shopping_context(None)
    assert ctx is not None
    assert ctx["timeslot_start"] == "2026-09-08T06:00:00+00:00"


@pytest.mark.asyncio
async def test_write_verifies_cart_and_surfaces_loyalty_and_checkout(monkeypatch) -> None:
    detail = _cart_detail(
        loyalty={"isEnabled": True, "bonusAvailable": 125.5, "bonusRequested": None, "bonusApplied": 0.0},
        validations=[{"code": "MIN_ORDER", "message": "Мінімальне замовлення 400 грн", "severity": "warning"}],
    )
    client = OfficialFakeClient(detail=detail)
    _patch(monkeypatch, client)
    result = await MCPProductService().create_cart([_product(UUID_A), _product(UUID_B)], None)
    assert result["cart_url"] == "https://silpo.ua/checkout/cart-1"
    assert result["checkout_url"] == "https://silpo.ua/checkout/cart-1"
    assert result["verified_total"] == 100.0
    assert result["validations"] == [
        {"code": "MIN_ORDER", "message": "Мінімальне замовлення 400 грн", "severity": "warning"}
    ]
    assert "125" in (result["loyalty_hint"] or "")
    assert "clear_cart" not in client.calls
    assert client.added is not None and len(client.added) == 2


@pytest.mark.asyncio
async def test_write_applies_changed_delivery_settings(monkeypatch) -> None:
    client = OfficialFakeClient()
    _patch(monkeypatch, client)
    fulfillment = {
        "address_type": "delivery",
        "latitude": 50.4,
        "longitude": 30.6,
        "delivery_type": "DeliveryHome",
        "branch_id": "bran-9",
        "timeslot_start": "2026-09-09T06:00:00+00:00",
        "timeslot_end": "2026-09-09T07:30:00+00:00",
    }
    await MCPProductService().create_cart([_product(UUID_A)], fulfillment)
    assert "update_shopping_cart" in client.calls
    assert client.updated is not None
    assert client.updated["branch_id"] == "bran-9"


@pytest.mark.asyncio
async def test_write_skips_update_when_settings_match(monkeypatch) -> None:
    client = OfficialFakeClient()
    _patch(monkeypatch, client)
    fulfillment = {
        "address_type": "delivery",
        "latitude": 50.4,
        "longitude": 30.6,
        "delivery_type": "SelfPickup",
        "branch_id": "bran-1",
        "timeslot_start": SLOT_S,
        "timeslot_end": SLOT_E,
    }
    await MCPProductService().create_cart([_product(UUID_A)], fulfillment)
    assert "update_shopping_cart" not in client.calls


@pytest.mark.asyncio
async def test_write_continues_when_delivery_update_rejected(monkeypatch, caplog) -> None:
    class RejectUpdateClient(OfficialFakeClient):
        async def update_shopping_cart(self, *args, **kwargs):
            self.calls.append("update_shopping_cart")
            raise RuntimeError("MCP error -32602: shipments too small")

    client = RejectUpdateClient()
    _patch(monkeypatch, client)
    fulfillment = {
        "address_type": "delivery",
        "latitude": 50.4,
        "longitude": 30.6,
        "delivery_type": "DeliveryHome",
        "branch_id": "bran-9",
        "timeslot_start": "2026-09-09T06:00:00+00:00",
        "timeslot_end": "2026-09-09T07:30:00+00:00",
    }
    with caplog.at_level("WARNING", logger="app.services.mcp_service"):
        result = await MCPProductService().create_cart([_product(UUID_A)], fulfillment)
    assert result["cart_url"] == "https://silpo.ua/checkout/cart-1"
    assert client.added is not None and len(client.added) == 1
    assert any("delivery update failed" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_write_builds_shipments_from_written_items(monkeypatch) -> None:
    client = OfficialFakeClient()
    _patch(monkeypatch, client)
    fulfillment = {
        "address_type": "delivery",
        "latitude": 50.4,
        "longitude": 30.6,
        "delivery_type": "DeliveryHome",
        "branch_id": "bran-9",
        "timeslot_start": "2026-09-09T06:00:00+00:00",
        "timeslot_end": "2026-09-09T07:30:00+00:00",
    }
    await MCPProductService().create_cart([_product(UUID_A)], fulfillment)
    assert client.updated is not None
    assert client.updated["args"][4] == [
        {"branchId": "bran-9", "companyId": "c1", "items": [{"productId": UUID_A, "quantity": 1}]}
    ]
