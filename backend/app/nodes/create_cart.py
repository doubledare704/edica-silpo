import logging
import uuid
from typing import Any

from ..config import settings
from ..domain.planners import get_domain_planner
from ..services.mcp_service import mcp_product_service
from ..state import SilpoAgentState

logger = logging.getLogger(__name__)


async def create_cart_node(state: SilpoAgentState) -> dict[str, Any]:
    """Writes the picked cart via the official flow and always returns a summary."""
    total_price = state.get("total_price", 0.0)
    intent = state.get("intent")
    fulfillment = state.get("fulfillment")
    checkout_url: str | None = None
    cart_validations: list[dict[str, Any]] = []
    loyalty_hint: str | None = None

    if settings.MCP_MOCK_MODE:
        cart_id = uuid.uuid4().hex[:8]
        cart_url = f"https://silpo.ua/cart/share/mock_{cart_id}"
    else:
        try:
            if fulfillment is None:
                fulfillment = await mcp_product_service.resolve_fulfillment(state.get("delivery_address"))
            written = await mcp_product_service.create_cart(state.get("mcp_products", []), fulfillment)
            cart_url = written["cart_url"]
            fulfillment = written["fulfillment"]
            checkout_url = written["checkout_url"]
            cart_validations = written["validations"]
            loyalty_hint = written["loyalty_hint"]
            verified_total = written["verified_total"]
            if verified_total is not None and float(verified_total) > 0:
                total_price = float(verified_total)
        except Exception as exc:  # noqa: BLE001 - cart failure must not lose the summary
            cart_id = uuid.uuid4().hex[:8]
            cart_url = f"https://silpo.ua/cart/share/mock_{cart_id}"
            logger.warning("Silpo cart creation failed, using fallback URL: %s", exc)

    planner = get_domain_planner(intent)
    summary_message = planner.format_summary(total_price, state)
    if loyalty_hint:
        summary_message = f"{summary_message} {loyalty_hint}"

    logger.info(
        "create_cart done total=%s cart_url=%s has_fulfillment=%s validations=%d summary_chars=%d",
        total_price,
        cart_url,
        fulfillment is not None,
        len(cart_validations),
        len(summary_message),
    )
    return {
        "cart_url": cart_url,
        "summary_message": summary_message,
        "fulfillment": fulfillment,
        "total_price": total_price,
        "checkout_url": checkout_url,
        "cart_validations": cart_validations,
        "loyalty_hint": loyalty_hint,
    }
