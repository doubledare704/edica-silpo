from app.domain.planners import (
    BudgetDomainPlanner,
    GeneralDomainPlanner,
    PartyDomainPlanner,
    get_domain_planner,
)
from app.enums import IntentEnum
from app.state import AgentState


def test_get_domain_planner_instances() -> None:
    assert isinstance(get_domain_planner(IntentEnum.PARTY), PartyDomainPlanner)
    assert isinstance(get_domain_planner(IntentEnum.BUDGET), BudgetDomainPlanner)
    assert isinstance(get_domain_planner(None), GeneralDomainPlanner)


def test_budget_planner_plan_and_summary() -> None:
    planner = BudgetDomainPlanner()
    state: AgentState = {
        "audio_bytes": None,
        "user_text": None,
        "intent": IntentEnum.BUDGET,
        "budget": 500.0,
        "people_count": None,
        "dietary_restrictions": [],
        "raw_item_requests": [],
        "calculated_items": [],
        "mcp_products": [{"id": "1", "title": "Хліб", "price": 28.5, "quantity": 1}],
        "total_price": 28.5,
        "attempts": 0,
        "max_attempts": 3,
        "is_budget_exceeded": False,
        "cart_url": None,
        "summary_message": "",
        "audio_url": None,
        "messages": [],
    }
    items = planner.plan(state)
    assert len(items) == 3
    summary = planner.format_summary(28.5, state)
    assert "економний кошик" in summary
