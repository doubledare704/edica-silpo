import logging
import uuid
from typing import Any

from ..config import settings
from ..domain.planners import get_domain_planner
from ..services.mcp_service import mcp_product_service
from ..state import SilpoAgentState

logger = logging.getLogger(__name__)


async def create_cart_node(state: SilpoAgentState) -> dict[str, Any]:
    """Creates a real Silpo cart when enabled and always returns a summary."""
    total_price = state.get("total_price", 0.0)
    intent = state.get("intent")
    cart_url: str
    fulfillment = state.get("fulfillment")

    if settings.MCP_MOCK_MODE:
        cart_id = uuid.uuid4().hex[:8]
        cart_url = f"https://silpo.ua/cart/share/mock_{cart_id}"
    else:
        try:
            if fulfillment is None:
                logger.info("Current state: %s", state)
                fulfillment = await mcp_product_service.resolve_fulfillment(state.get("delivery_address"))

            logger.info("Current state.mcp_products: %s", state.get("mcp_products", []))
            cart_url = await mcp_product_service.create_cart(state.get("mcp_products", []), fulfillment)
        except Exception as exc:  # noqa: BLE001 - cart failure must not lose the summary
            cart_id = uuid.uuid4().hex[:8]
            cart_url = f"https://silpo.ua/cart/share/mock_{cart_id}"
            logger.warning("Silpo cart creation failed, using fallback URL: %s", exc)

    planner = get_domain_planner(intent)
    summary_message = planner.format_summary(total_price, state)

    logger.info(
        "create_cart done total=%s cart_url=%s has_fulfillment=%s summary_chars=%d",
        total_price,
        cart_url,
        fulfillment is not None,
        len(summary_message),
    )
    return {
        "cart_url": cart_url,
        "summary_message": summary_message,
        "fulfillment": fulfillment,
    }
