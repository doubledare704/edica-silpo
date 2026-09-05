import os
from types import SimpleNamespace

import pytest
from app.enums import IntentEnum
from app.nodes.mcp_fetch import mcp_fetch_node
from app.services import mcp_service
from app.state import AgentState


@pytest.mark.asyncio
async def test_mcp_fetch_node_returns_products() -> None:
    state: AgentState = {
        "audio_bytes": None,
        "user_text": "Збери кошик",
        "intent": IntentEnum.PARTY,
        "budget": 2500.0,
        "people_count": 6,
        "dietary_restrictions": ["vegetarian"],
        "raw_item_requests": ["м'ясо", "овочі"],
        "calculated_items": [
            {
                "query": "Ошийник свинячий",
                "category": "meat",
                "quantity": 2,
                "prefer_private_label": False,
            },
            {
                "query": "Овочі для гриля Премія",
                "category": "vegetables",
                "quantity": 2,
                "prefer_private_label": True,
            },
        ],
        "mcp_products": [],
        "total_price": 0.0,
        "attempts": 0,
        "max_attempts": 3,
        "is_budget_exceeded": False,
        "cart_url": None,
        "summary_message": "",
        "audio_url": None,
        "messages": [],
    }
    result = await mcp_fetch_node(state)
    assert "mcp_products" in result
    products = result["mcp_products"]
    assert len(products) >= 2
    for p in products:
        assert "id" in p
        assert "title" in p
        assert "price" in p
        assert "is_private_label" in p
        assert "quantity" in p


@pytest.mark.asyncio
async def test_mcp_fetch_real_mode_selects_private_label_and_preserves_identifiers(monkeypatch) -> None:
    class FakeClient:
        def __init__(self) -> None:
            self.queries: list[tuple[str, dict[str, object]]] = []

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> None:
            return None

        async def get_products(self, query: str, **kwargs):
            self.queries.append((query, kwargs))
            return SimpleNamespace(
                items=[
                    SimpleNamespace(
                        id="regular-1",
                        title="Regular product",
                        price=120.0,
                        is_private_label=False,
                        company_id="company-regular",
                        branch_id="branch-regular",
                    ),
                    SimpleNamespace(
                        id="private-1",
                        title="Private label product",
                        price=90.0,
                        is_private_label=True,
                        company_id="company-private",
                        branch_id="branch-private",
                    ),
                ]
            )

    client = FakeClient()
    monkeypatch.setattr(mcp_service.settings, "MCP_MOCK_MODE", False)
    monkeypatch.setattr(mcp_service.SilpoClient, "for_real_server", lambda: client)

    products = await mcp_service.MCPProductService().fetch_products(
        [{"query": "кава", "quantity": 2, "prefer_private_label": True}]
    )

    assert products == [
        {
            "id": "private-1",
            "productId": "private-1",
            "title": "Private label product",
            "price": 90.0,
            "is_private_label": True,
            "companyId": "company-private",
            "branchId": "branch-private",
            "quantity": 2,
        }
    ]
    assert client.queries == [("кава", {"on_sale": True, "limit": 5})]


@pytest.mark.asyncio
@pytest.mark.skipif(os.getenv("SILPO_TEST_REAL") != "1", reason="Set SILPO_TEST_REAL=1 for the MCP integration test")
async def test_mcp_fetch_real_integration() -> None:
    previous_mode = mcp_service.settings.MCP_MOCK_MODE
    mcp_service.settings.MCP_MOCK_MODE = False
    try:
        products = await mcp_service.MCPProductService().fetch_products(
            [{"query": "молоко", "quantity": 1, "prefer_private_label": True}]
        )
    finally:
        mcp_service.settings.MCP_MOCK_MODE = previous_mode

    assert products
    assert products[0]["id"]
    assert products[0]["title"]
