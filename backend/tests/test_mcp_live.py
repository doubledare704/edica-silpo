"""Gated live Silpo MCP smoke test. Opt-in only, never runs by default.

Requires SILPO_LIVE_SMOKE=1 plus a completed Silpo OAuth login (the real
client opens a browser on first use and reuses encrypted on-disk tokens).
Without the flag the whole module skips, so default/CI runs stay offline.
"""

import os

import pytest
from app.services import mcp_service

_LIVE = os.getenv("SILPO_LIVE_SMOKE") == "1"

pytestmark = pytest.mark.skipif(
    not _LIVE,
    reason="Set SILPO_LIVE_SMOKE=1 to run the live Silpo MCP smoke test (needs OAuth login)",
)


@pytest.mark.asyncio
async def test_live_mcp_batch_search_smoke(monkeypatch) -> None:
    assert _LIVE, "live smoke test requires SILPO_LIVE_SMOKE=1"
    monkeypatch.setattr(mcp_service.settings, "MCP_MOCK_MODE", False)
    context = await mcp_service.mcp_product_service.resolve_shopping_context(None)
    assert context is not None and context.get("branch_id")
    product = await mcp_service.mcp_product_service.search_one("Вода", 1, False, None, "drinks", context)
    assert product is None or str(product.get("title", ""))
