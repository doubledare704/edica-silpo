from typing import ClassVar, Self

import pytest
from app.main import app
from app.services import mcp_service
from httpx import ASGITransport, AsyncClient


class _FakeBranchesClient:
    """Stands in for SilpoClient with script-like branch shapes."""

    branches: ClassVar[list[dict[str, object]]] = [
        {
            "branchId": "b-far",
            "name": "Сільпо Львів (центр)",
            "city": "Львів",
            "address": "вул. Степана Бандери, 3",
            "coordinates": {"lat": 49.8383, "lng": 24.0232},
            "open": True,
            "hasPickup": True,
        },
        {
            "branchId": "b-closed",
            "name": "Сільпо Зачинене",
            "city": "Київ",
            "address": "вул. Закрита, 1",
            "coordinates": {"lat": 50.4501, "lng": 30.5234},
            "open": False,
            "hasPickup": True,
        },
        {
            "branchId": "b-ghost",
            "name": "Сільпо Без координат",
            "city": "Київ",
            "address": "вул. Невідома, 0",
        },
        {
            "branchId": "b-near",
            "name": "Сільпо Поруч",
            "city": "Київ",
            "address": "вул. Хрещатик, 1",
            "latitude": 50.4501,
            "longitude": 30.5234,
        },
    ]

    def __init__(self) -> None:
        self.list_limit: int | None = None

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False

    async def find_address(self, text: str) -> dict[str, object]:
        return {"text": text, "coordinates": {"lat": 50.4501, "lng": 30.5234}}

    async def list_branches(self, limit: int | None = None) -> list[dict[str, object]]:
        self.list_limit = limit
        return list(self.branches)


@pytest.mark.asyncio
async def test_nearest_branches_fetch_big_page_and_rank_like_script(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeBranchesClient()
    monkeypatch.setattr(mcp_service.SilpoClient, "for_mock", classmethod(lambda cls: fake))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/stores/nearest", params={"address": "Київ", "limit": 10})
        assert response.status_code == 200
        payload = response.json()
        assert fake.list_limit == 500
        branch_ids = [store["branch_id"] for store in payload["stores"]]
        assert branch_ids == ["b-near", "b-far"]
        assert payload["stores"][0]["city"] == "Київ"
        assert payload["stores"][0]["display_address"] == "Київ, вул. Хрещатик, 1"
        assert payload["stores"][0]["distance_km"] == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_nearest_stores_sorted_by_distance() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/stores/nearest",
            params={"address": "Київ, вул. Анни Ахматової, 9", "limit": 10},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["latitude"] == pytest.approx(50.3957)
        assert payload["longitude"] == pytest.approx(30.6217)
        stores = payload["stores"]
        assert len(stores) == 2
        assert stores[0]["branch_id"] == "bran-2"
        assert stores[0]["distance_km"] == pytest.approx(0.0)
        assert stores[1]["branch_id"] == "bran-1"
        assert stores[1]["distance_km"] > 100
        assert set(stores[0]) >= {"branch_id", "name", "address", "distance_km", "has_pickup"}


@pytest.mark.asyncio
async def test_nearest_stores_limit_clamps_to_nearest() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/stores/nearest",
            params={"address": "Київ, вул. Анни Ахматової, 9", "limit": 1},
        )
        assert response.status_code == 200
        stores = response.json()["stores"]
        assert len(stores) == 1
        assert stores[0]["branch_id"] == "bran-2"


@pytest.mark.asyncio
async def test_saved_addresses_returns_stored_list() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/stores/saved-addresses")
        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 1
        assert payload[0]["address_id"] == "addr-1"
        assert payload[0]["label"] == "Дім"
        assert payload[0]["text"] == "Київ, вул. Анни Ахматової, 9"


@pytest.mark.asyncio
async def test_nearest_stores_rejects_blank_address() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/stores/nearest", params={"address": "   "})
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_nearest_stores_rejects_limit_above_ten() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/stores/nearest", params={"address": "Київ", "limit": 50})
        assert response.status_code == 422
