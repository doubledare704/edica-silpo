import logging
from typing import Any

from ..domain.planners import get_domain_planner
from ..state import SilpoAgentState

logger = logging.getLogger(__name__)


async def check_constraints_node(state: SilpoAgentState) -> dict[str, Any]:
    """Totals the picked cart and evaluates budget, coverage, and remaining budget."""
    mcp_products = state.get("mcp_products", [])
    budget = state.get("budget", 0.0) or 0.0
    attempts = state.get("attempts", 0) + 1
    planner = get_domain_planner(state.get("intent"))
    hard = planner.budget_mode() == "hard_fill"

    total_price = sum(float(item.get("price", 0.0) or 0.0) * int(item.get("quantity", 1) or 1) for item in mcp_products)
    is_budget_exceeded = hard and budget > 0 and total_price > budget
    remaining_budget = round(budget - total_price, 2) if budget > 0 else 0.0

    unfulfilled = state.get("unfulfilled_requests", [])
    categories = {str(item.get("category")) for item in mcp_products if item.get("category")}
    if not mcp_products:
        is_requirements_met = False
    elif not categories and not unfulfilled:
        is_requirements_met = True
    else:
        is_requirements_met = all(req in categories for req in planner.min_coverage()) and not unfulfilled

    result = {
        "total_price": round(total_price, 2),
        "attempts": attempts,
        "is_budget_exceeded": is_budget_exceeded,
        "remaining_budget": remaining_budget,
        "is_requirements_met": is_requirements_met,
    }
    logger.info(
        "check_constraints done total=%s budget=%s exceeded=%s met=%s remaining=%s attempts=%d",
        result["total_price"],
        budget,
        is_budget_exceeded,
        is_requirements_met,
        remaining_budget,
        attempts,
    )
    return result
