import logging
from typing import Any

from ..domain.planners import get_domain_planner
from ..state import SilpoAgentState

logger = logging.getLogger(__name__)


async def plan_domain_logic_node(state: SilpoAgentState) -> dict[str, Any]:
    """Plans shopping items, portions, and budget adjustments based on domain intent."""
    intent = state.get("intent")
    planner = get_domain_planner(intent)
    calculated_items = planner.plan(state)
    logger.info("plan_domain_logic done intent=%s items=%d", intent, len(calculated_items))
    return {"calculated_items": calculated_items}
