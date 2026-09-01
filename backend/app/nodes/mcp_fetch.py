from typing import Any

from ..services.mcp_service import mcp_product_service
from ..state import AgentState


async def mcp_fetch_node(state: AgentState) -> dict[str, Any]:
    """Fetches SKU details, prices, and promotion flags via silpo-py-mcp."""
    calculated_items = state.get("calculated_items", [])
    products = await mcp_product_service.fetch_products(calculated_items)
    return {"mcp_products": products}
