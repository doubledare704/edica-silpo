"""Phase 2 (SDK 0.3.0): context-first MCP wrappers (batch search, promo products, slug-based)."""

from types import SimpleNamespace

import pytest
from app.services import mcp_service
from app.services.mcp_service import MOCK_SHOPPING_CONTEXT, MCPProductService

CTX = {
    "branch_id": "bran-1",
    "delivery_type": "SelfPickup",
    "timeslot_start": "2026-09-06T10:00:00",
    "timeslot_end": "2026-09-06T12:00:00",
}


def _item(price: float, pid: str, *, private: bool = False, image_url: str | None = None):
    return SimpleNamespace(
        product_id=pid,
        productId=pid,
        title=f"Product {pid}",
        slug=f"slug-{pid}",
        price=price,
        is_private_label=private,
        isPrivateLabel=private,
        company_id="c1",
        branch_id="b1",
        image_url=image_url,
        imageUrl=image_url,
    )


class FakeClient:
    def __init__(self, items: list) -> None:
        self._items = items
        self.calls: list[tuple[str, dict]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args) -> None:
        return None

    async def find_products_batch(self, branch_id, delivery_type, timeslot_start, timeslot_end, queries, limit=None):
        self.calls.append(("find_products_batch", {"queries": queries, "limit": limit}))
        return SimpleNamespace(results={q: list(self._items) for q in queries}, unmatched=[])

    async def get_products(self, branch_id, delivery_type, timeslot_start, timeslot_end, **kwargs):
        self.calls.append(("get_products", kwargs))
        items = list(self._items)
        if kwargs.get("to_price") is not None:
            items = [p for p in items if p.price <= kwargs["to_price"]]
        return SimpleNamespace(items=items)

    async def get_promotions(self, **kwargs):
        raise AssertionError("fetch_promo_products must use get_products, not get_promotions")

    async def get_similar_products(self, branch_id, slug, **kwargs):
        self.calls.append(("get_similar_products", {"slug": slug}))
        return [_item(60.0, "sim-1")]

    async def get_product_details(self, branch_id, slug, *args, **kwargs):
        self.calls.append(("get_product_details", {"slug": slug}))
        return SimpleNamespace(description="Fine aged cheese", composition=["milk", "salt"])

    async def get_replacements(self, branch_id, company_id, delivery_type, product_ids):
        self.calls.append(("get_replacements", {"product_ids": product_ids}))
        return [{"replacement": _item(45.0, "repl-1")}]

    async def get_categories(self, branch_id, **kwargs):
        self.calls.append(("get_categories", {}))
        return [SimpleNamespace(id="cat-1", name="Dairy")]


def _patch(monkeypatch, client: FakeClient) -> None:
    monkeypatch.setattr(mcp_service.settings, "MCP_MOCK_MODE", False)
    monkeypatch.setattr(mcp_service.SilpoClient, "for_real_server", lambda: client)
    monkeypatch.setattr(mcp_service.SilpoClient, "for_mock", lambda: client)


@pytest.mark.asyncio
async def test_search_one_uses_batch_search_with_context(monkeypatch) -> None:
    client = FakeClient([_item(500.0, "exp-1"), _item(40.0, "cheap-1")])
    _patch(monkeypatch, client)
    result = await MCPProductService().search_one("test", 1, False, 100.0, "dairy", CTX)
    assert result is not None
    assert result["id"] == "cheap-1"
    assert result["category"] == "dairy"
    assert result["slug"] == "slug-cheap-1"
    assert client.calls[0][0] == "find_products_batch"


@pytest.mark.asyncio
async def test_search_one_preserves_image_url(monkeypatch) -> None:
    client = FakeClient([_item(40.0, "img-1", image_url="https://images.silpo.ua/milk.jpg")])
    _patch(monkeypatch, client)
    result = await MCPProductService().search_one("milk", 1, False, None, None, CTX)
    assert result is not None
    assert result["image_url"] == "https://images.silpo.ua/milk.jpg"


@pytest.mark.asyncio
async def test_search_one_returns_none_when_nothing_fits(monkeypatch) -> None:
    client = FakeClient([_item(500.0, "exp-1")])
    _patch(monkeypatch, client)
    assert await MCPProductService().search_one("unknown-xyz-item", 1, False, 10.0, None, CTX) is None


@pytest.mark.asyncio
async def test_search_one_without_context_uses_static_fallback() -> None:
    service = MCPProductService()
    result = await service.search_one("молоко", 1, True, 100.0, "dairy", None)
    assert result is not None
    assert result["quantity"] == 1
    assert await service.search_one("unknown-xyz-item", 1, False, 10.0, None, None) is None


@pytest.mark.asyncio
async def test_search_one_never_fabricates_with_live_context(monkeypatch) -> None:
    class EmptyClient(FakeClient):
        async def find_products_batch(self, *args, **kwargs):
            self.calls.append(("find_products_batch", {}))
            return SimpleNamespace(results={}, unmatched=["Вино біле сухе El Maestro"])

    _patch(monkeypatch, EmptyClient([]))
    service = MCPProductService()
    assert await service.search_one("Вино біле сухе El Maestro", 1, False, None, "wine", CTX) is None
    assert await service.search_one("Крекери до вина", 1, False, 1000.0, "crackers", CTX) is None


@pytest.mark.asyncio
async def test_fetch_products_skips_over_ceiling(monkeypatch) -> None:
    client = FakeClient([_item(500.0, "exp-1")])
    _patch(monkeypatch, client)
    products = await MCPProductService().fetch_products(
        [{"query": "unknown-xyz-item", "quantity": 1, "category": "general"}], max_price=10.0, context=CTX
    )
    assert products == []


@pytest.mark.asyncio
async def test_fetch_promo_products_uses_server_side_filters(monkeypatch) -> None:
    client = FakeClient([_item(500.0, "exp-1"), _item(25.0, "promo-1")])
    _patch(monkeypatch, client)
    promos = await MCPProductService().fetch_promo_products(CTX, max_price=100.0, limit=5)
    assert [p["id"] for p in promos] == ["promo-1"]
    call = next(c for c in client.calls if c[0] == "get_products")
    assert call[1].get("must_have_promotion") is True
    assert call[1].get("to_price") == 100.0


@pytest.mark.asyncio
async def test_fetch_similar_details_replacements_by_slug(monkeypatch) -> None:
    client = FakeClient([])
    _patch(monkeypatch, client)
    service = MCPProductService()
    assert [p["id"] for p in await service.fetch_similar("slug-x", CTX)] == ["sim-1"]
    details = await service.fetch_product_details("slug-x", CTX)
    assert details is not None and details["description"] == "Fine aged cheese"
    repls = await service.fetch_replacements({"productId": "p1", "company_id": "c1", "companyId": "c1"}, CTX)
    assert [p["id"] for p in repls] == ["repl-1"]


@pytest.mark.asyncio
async def test_resolve_shopping_context_mock_mode(monkeypatch) -> None:
    monkeypatch.setattr(mcp_service.settings, "MCP_MOCK_MODE", True)
    ctx = await MCPProductService().resolve_shopping_context(None)
    assert ctx == MOCK_SHOPPING_CONTEXT
    assert set(ctx) == {"branch_id", "delivery_type", "timeslot_start", "timeslot_end"}


@pytest.mark.asyncio
async def test_picker_wrappers_fail_soft(monkeypatch) -> None:
    class ExplodingClient(FakeClient):
        async def find_products_batch(self, *args, **kwargs):
            raise RuntimeError("boom")

        async def get_products(self, *args, **kwargs):
            raise RuntimeError("boom")

        async def get_similar_products(self, *args, **kwargs):
            raise RuntimeError("boom")

        async def get_product_details(self, *args, **kwargs):
            raise RuntimeError("boom")

        async def get_replacements(self, *args, **kwargs):
            raise RuntimeError("boom")

        async def get_categories(self, *args, **kwargs):
            raise RuntimeError("boom")

    _patch(monkeypatch, ExplodingClient([]))
    service = MCPProductService()
    assert await service.search_one("молоко", 1, False, None, None, None) is not None  # static fallback
    assert await service.search_one("молоко", 1, False, None, None, CTX) is None  # honest miss, no fabrication
    assert await service.fetch_promo_products(CTX, None) == []
    assert await service.fetch_similar("x", CTX) == []
    assert await service.fetch_product_details("x", CTX) is None
    assert await service.fetch_replacements({"productId": "p"}, CTX) == []
    assert await service.fetch_categories(CTX) == []
