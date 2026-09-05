from types import SimpleNamespace

import pytest
from app.services import mcp_service


def _slot(start: str, end: str, available: bool = True) -> dict[str, object]:
    return {
        "id": "slot-1",
        "deliveryType": "SelfPickup",
        "branchId": "bran-1",
        "startsAt": start,
        "endsAt": end,
        "price": 0.0,
        "isAvailable": available,
    }


class FakeFulfillmentClient:
    def __init__(
        self,
        addresses: list,
        delivery_types: list,
        slots: list,
    ) -> None:
        self._addresses = addresses
        self._delivery_types = delivery_types
        self._slots = slots
        self.find_address_calls: list[str] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args) -> None:
        return None

    async def get_delivery_addresses(self):
        return self._addresses

    async def find_address(self, text):
        self.find_address_calls.append(text)
        return SimpleNamespace(
            text=text,
            coordinates=SimpleNamespace(lat=50.45, lng=30.52),
            city="Kyiv",
            street="Khreshchatyk",
            house_number="1",
        )

    async def get_available_delivery_types(self, **kwargs):
        return self._delivery_types

    async def call_tool(self, name, args):
        assert name == "silpo_get_time_slots"
        return self._slots


def _saved_address() -> SimpleNamespace:
    return SimpleNamespace(
        address_id="addr-1",
        label="Дім",
        text="Київ, вул. Анни Ахматової, 9",
        coordinates={"lat": 50.3957, "lng": 30.6217},
    )


def _delivery_types() -> list:
    return [
        SimpleNamespace(type="DeliveryHome", branch_id="bran-1", min_order=400.0),
        SimpleNamespace(type="SelfPickup", branch_id="bran-1", min_order=0.0),
    ]


def _patch_client(monkeypatch, client: FakeFulfillmentClient) -> None:
    monkeypatch.setattr(mcp_service.SilpoClient, "for_real_server", lambda: client)


@pytest.mark.asyncio
async def test_resolve_prefers_saved_address_and_self_pickup(monkeypatch) -> None:
    client = FakeFulfillmentClient(
        [_saved_address()], _delivery_types(), [_slot("2026-09-06T10:00:00", "2026-09-06T12:00:00")]
    )
    _patch_client(monkeypatch, client)

    bundle = await mcp_service.MCPProductService().resolve_fulfillment(None)

    assert bundle is not None
    assert bundle["latitude"] == 50.3957
    assert bundle["longitude"] == 30.6217
    assert bundle["delivery_type"] == "SelfPickup"
    assert bundle["branch_id"] == "bran-1"
    assert bundle["timeslot_start"] == "2026-09-06T10:00:00"
    assert bundle["timeslot_end"] == "2026-09-06T12:00:00"
    assert client.find_address_calls == []


@pytest.mark.asyncio
async def test_resolve_geocodes_user_address_when_no_saved(monkeypatch) -> None:
    client = FakeFulfillmentClient([], _delivery_types(), [_slot("2026-09-06T10:00:00", "2026-09-06T12:00:00")])
    _patch_client(monkeypatch, client)

    bundle = await mcp_service.MCPProductService().resolve_fulfillment("Хрещатик 1")

    assert bundle is not None
    assert bundle["latitude"] == 50.45
    assert bundle["longitude"] == 30.52
    assert client.find_address_calls == ["Хрещатик 1"]


@pytest.mark.asyncio
async def test_resolve_returns_none_without_any_address(monkeypatch) -> None:
    client = FakeFulfillmentClient([], _delivery_types(), [_slot("2026-09-06T10:00:00", "2026-09-06T12:00:00")])
    _patch_client(monkeypatch, client)

    assert await mcp_service.MCPProductService().resolve_fulfillment(None) is None
    assert client.find_address_calls == []


@pytest.mark.asyncio
async def test_resolve_picks_lowest_min_order_without_pickup(monkeypatch) -> None:
    types = [
        SimpleNamespace(type="DeliveryHome", branch_id="bran-9", min_order=400.0),
        SimpleNamespace(type="NovaPoshta", branch_id="bran-2", min_order=100.0),
    ]
    client = FakeFulfillmentClient([_saved_address()], types, [_slot("2026-09-06T10:00:00", "2026-09-06T12:00:00")])
    _patch_client(monkeypatch, client)

    bundle = await mcp_service.MCPProductService().resolve_fulfillment(None)

    assert bundle is not None
    assert bundle["delivery_type"] == "NovaPoshta"
    assert bundle["branch_id"] == "bran-2"


@pytest.mark.asyncio
async def test_resolve_returns_none_without_available_slots(monkeypatch) -> None:
    slots = [
        _slot("2026-09-06T10:00:00", "2026-09-06T12:00:00", available=False),
        _slot("2026-09-06T12:00:00", "2026-09-06T14:00:00", available=False),
    ]
    client = FakeFulfillmentClient([_saved_address()], _delivery_types(), slots)
    _patch_client(monkeypatch, client)

    assert await mcp_service.MCPProductService().resolve_fulfillment(None) is None
