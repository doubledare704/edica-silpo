from types import SimpleNamespace

import pytest
from app.services import mcp_service


class FakeCartClient:
    def __init__(self, cart, created_id: str = "cart-new") -> None:
        self._cart = cart
        self._created_id = created_id
        self.created_kwargs: dict[str, object] | None = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args) -> None:
        return None

    async def get_cart(self):
        return self._cart

    async def create_shopping_cart(self, **kwargs):
        self.created_kwargs = kwargs
        return SimpleNamespace(success=True, shopping_cart_id=self._created_id)


def _patch_client(monkeypatch, client: FakeCartClient) -> None:
    monkeypatch.setattr(mcp_service.SilpoClient, "for_real_server", lambda: client)


@pytest.mark.asyncio
async def test_ensure_cart_returns_existing_id_without_creating(monkeypatch) -> None:
    client = FakeCartClient(SimpleNamespace(cart_id="cart-1", shopping_cart_id=None, exists=True))
    _patch_client(monkeypatch, client)

    cart_id = await mcp_service.MCPProductService().ensure_cart(None)

    assert cart_id == "cart-1"
    assert client.created_kwargs is None


@pytest.mark.asyncio
async def test_ensure_cart_creates_when_missing(monkeypatch) -> None:
    client = FakeCartClient(SimpleNamespace(cart_id=None, shopping_cart_id=None, exists=False))
    _patch_client(monkeypatch, client)
    fulfillment = {
        "address_type": "delivery",
        "latitude": 50.3957,
        "longitude": 30.6217,
        "delivery_type": "SelfPickup",
        "branch_id": "bran-1",
        "timeslot_start": "2026-09-06T10:00:00",
        "timeslot_end": "2026-09-06T12:00:00",
    }

    cart_id = await mcp_service.MCPProductService().ensure_cart(fulfillment)

    assert cart_id == "cart-new"
    assert client.created_kwargs == fulfillment


@pytest.mark.asyncio
async def test_ensure_cart_raises_without_fulfillment(monkeypatch) -> None:
    client = FakeCartClient(SimpleNamespace(cart_id=None, shopping_cart_id=None, exists=False))
    _patch_client(monkeypatch, client)

    with pytest.raises(ValueError, match="fulfillment"):
        await mcp_service.MCPProductService().ensure_cart(None)
    assert client.created_kwargs is None
