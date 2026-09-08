import pytest
from app.main import app
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_offers_overview_returns_mock_bonuses_and_promos() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/offers")
        assert response.status_code == 200
        payload = response.json()
        assert set(payload) >= {
            "loyalty",
            "promotions",
            "promo_products",
            "personal_promos",
            "coupons",
            "promo_codes",
        }
        assert payload["loyalty"]["bonus_balance"] == pytest.approx(125.5)
        assert len(payload["promotions"]) == 2
        assert payload["promotions"][0]["title"] == "Ціна тижня: Яйця С1"
        assert len(payload["promo_products"]) == 2
        assert len(payload["personal_promos"]) == 1
        assert len(payload["coupons"]) == 1
        assert len(payload["promo_codes"]) == 1


@pytest.mark.asyncio
async def test_profile_overview_returns_mock_profile_and_addresses() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/profile")
        assert response.status_code == 200
        payload = response.json()
        assert set(payload) >= {"profile", "loyalty", "addresses"}
        assert payload["profile"]["name"] == "Олексій"
        assert payload["loyalty"]["bonus_balance"] == pytest.approx(125.5)
        assert len(payload["addresses"]) == 1
        assert payload["addresses"][0]["address_id"] == "addr-1"
