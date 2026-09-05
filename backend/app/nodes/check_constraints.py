import logging
from typing import Any

from ..state import SilpoAgentState

logger = logging.getLogger(__name__)


async def check_constraints_node(state: SilpoAgentState) -> dict[str, Any]:
    """Calculates total cart cost and checks against the user budget."""
    mcp_products = state.get("mcp_products", [])
    budget = state.get("budget", 0.0)
    attempts = state.get("attempts", 0) + 1

    total_price = sum(item.get("price", 0.0) * item.get("quantity", 1) for item in mcp_products)
    is_budget_exceeded = budget > 0 and total_price > budget

    result = {
        "total_price": round(total_price, 2),
        "attempts": attempts,
        "is_budget_exceeded": is_budget_exceeded,
    }
    logger.info(
        "check_constraints done total=%s budget=%s exceeded=%s attempts=%d",
        result["total_price"],
        budget,
        is_budget_exceeded,
        attempts,
    )
    return result
