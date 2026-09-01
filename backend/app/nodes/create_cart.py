import uuid
from typing import Any

from ..domain.planners import get_domain_planner
from ..state import AgentState


def create_cart_node(state: AgentState) -> dict[str, Any]:
    """Generates the shareable Silpo cart link and summarizes the order."""
    total_price = state.get("total_price", 0.0)
    intent = state.get("intent")
    cart_id = str(uuid.uuid4())[:8]
    cart_url = f"https://silpo.ua/cart/share/mock_{cart_id}"

    planner = get_domain_planner(intent)
    summary_message = planner.format_summary(total_price, state)

    return {
        "cart_url": cart_url,
        "summary_message": summary_message,
    }
