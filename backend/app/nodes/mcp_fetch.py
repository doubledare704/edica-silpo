import logging
from typing import Any

from ..services.mcp_service import mcp_product_service
from ..state import SilpoAgentState

logger = logging.getLogger(__name__)


async def mcp_fetch_node(state: SilpoAgentState) -> dict[str, Any]:
    """Fetches SKU details, prices, and promotion flags via silpo-py-mcp."""
    calculated_items = state.get("calculated_items", [])
    budget = state.get("budget", 0.0) or 0.0
    remaining = state.get("remaining_budget")
    max_price = remaining if budget > 0 and remaining is not None and remaining >= 0 else None
    products = await mcp_product_service.fetch_products(
        calculated_items, max_price=max_price, context=state.get("shopping_context")
    )
    logger.info("mcp_fetch done requested=%d products=%d", len(calculated_items), len(products))
    return {"mcp_products": products}
