import logging
from typing import Any

from ..services.mcp_service import mcp_product_service
from ..state import SilpoAgentState

logger = logging.getLogger(__name__)


async def mcp_fetch_node(state: SilpoAgentState) -> dict[str, Any]:
    """Fetches SKU details, prices, and promotion flags via silpo-py-mcp."""
    calculated_items = state.get("calculated_items", [])
    products = await mcp_product_service.fetch_products(calculated_items)
    logger.info("mcp_fetch done requested=%d products=%d", len(calculated_items), len(products))
    return {"mcp_products": products}
