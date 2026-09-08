import logging
from typing import Any

from ..domain.planners import BudgetDomainPlanner
from ..enums import IntentEnum
from ..services import gemini_service
from ..state import SilpoAgentState

logger = logging.getLogger(__name__)

_WEEKLY_MARKERS = ("тиждень", "тижнев", "на тиждень", "7 днів", "сім днів", "week")


def is_weekly_budget_request(state: SilpoAgentState) -> bool:
    """Triggers only for weekly-menu queries with a specific budget."""
    if state.get("intent") != IntentEnum.BUDGET:
        return False
    if not (state.get("budget", 0.0) or 0.0) > 0:
        return False
    user_text = (state.get("user_text") or "").lower()
    return any(marker in user_text for marker in _WEEKLY_MARKERS)


def _weekly_days(seed: list[dict[str, Any]]) -> list[dict[str, Any]]:
    dishes = [str(item.get("dish") or item.get("query", "")) for item in seed if str(item.get("query", ""))]
    fallback = dishes or ["Хек з гречкою та овочами"]
    return [{"day": f"День {i + 1}", "dishes": [fallback[i % len(fallback)]]} for i in range(7)]


async def plan_meals_node(state: SilpoAgentState) -> dict[str, Any]:
    """Dedicated weekly-menu node: LLM seed with deterministic planner fallback."""
    if not is_weekly_budget_request(state):
        return {"meal_plan": None}
    user_text = (state.get("user_text") or "").strip()[:300]
    raw_requests = list(state.get("raw_item_requests") or [])
    goal = (
        f"intent={state.get('intent')} budget={state.get('budget', 0.0) or 0.0} "
        f"people={state.get('people_count')} request={user_text} items={','.join(raw_requests)}"
    )
    try:
        seed = await gemini_service.plan_weekly_meals(goal)
    except Exception as exc:  # noqa: BLE001 - LLM failure keeps deterministic fallback
        logger.debug("Weekly meal LLM failed, using planner fallback: %s", exc)
        seed = None
    llm_used = bool(seed)
    if not seed:
        seed = BudgetDomainPlanner().plan(state)
    for item in seed:
        try:
            item["quantity"] = max(1, min(6, int(item.get("quantity", 1) or 1)))
        except (TypeError, ValueError):
            item["quantity"] = 1
    meal_plan: dict[str, Any] = {
        "days": _weekly_days(seed),
        "shopping_seed": seed,
        "budget": state.get("budget", 0.0) or 0.0,
        "people_count": state.get("people_count"),
    }
    logger.info("plan_meals done items=%d llm=%s", len(seed), llm_used)
    return {"meal_plan": meal_plan, "calculated_items": seed}
