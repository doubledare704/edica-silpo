import logging
from typing import Any

from ..domain.planners import get_domain_planner
from ..services import gemini_service
from ..state import SilpoAgentState

logger = logging.getLogger(__name__)


async def plan_domain_logic_node(state: SilpoAgentState) -> dict[str, Any]:
    """Plans shopping items, portions, and budget adjustments based on domain intent.

    Tries grounded menu research first; falls back to the deterministic planner
    when research is unavailable (mock mode, no key, or any failure).
    """
    intent = state.get("intent")
    meal_plan = state.get("meal_plan") or {}
    seed = list(meal_plan.get("shopping_seed") or [])
    if seed:
        logger.info("plan_domain_logic done intent=%s items=%d researched=meal_plan", intent, len(seed))
        return {"calculated_items": seed}
    user_text = (state.get("user_text") or "").strip()[:300]
    raw_requests = list(state.get("raw_item_requests") or [])
    goal = (
        f"intent={intent} budget={state.get('budget', 0.0) or 0.0} people={state.get('people_count')} "
        f"dietary={','.join(state.get('dietary_restrictions') or [])} "
        f"request={user_text} items={','.join(raw_requests)}"
    )
    try:
        researched = await gemini_service.research_menu(goal)
    except Exception as exc:  # noqa: BLE001 - research failure keeps the planner seed
        logger.debug("Menu research failed, using planner fallback: %s", exc)
        researched = None
    calculated_items = researched or get_domain_planner(intent).plan(state)
    logger.info(
        "plan_domain_logic done intent=%s items=%d researched=%s", intent, len(calculated_items), researched is not None
    )
    return {"calculated_items": calculated_items}
