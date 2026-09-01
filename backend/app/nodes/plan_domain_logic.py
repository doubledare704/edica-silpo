from typing import Any

from ..domain.planners import get_domain_planner
from ..state import AgentState


def plan_domain_logic_node(state: AgentState) -> dict[str, Any]:
    """Plans shopping items, portions, and budget adjustments based on domain intent."""
    intent = state.get("intent")
    planner = get_domain_planner(intent)
    calculated_items = planner.plan(state)
    return {"calculated_items": calculated_items}
