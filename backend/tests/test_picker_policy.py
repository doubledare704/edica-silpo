"""Phase 1: per-intent picker policy + extended picker state fields."""

from app.domain.planners import get_domain_planner
from app.enums import IntentEnum
from app.state import SilpoAgentState


def test_picker_state_fields_present() -> None:
    for field in [
        "remaining_budget",
        "unfulfilled_requests",
        "is_requirements_met",
        "picker_trace",
    ]:
        assert field in SilpoAgentState.__annotations__, f"missing {field}"


def test_party_planner_picker_policy() -> None:
    planner = get_domain_planner(IntentEnum.PARTY)
    assert planner.budget_mode() == "hard_fill"
    assert "search_products" in planner.tool_allowlist()
    assert len(planner.min_coverage()) >= 2
    assert len(planner.filler_queries()) >= 1


def test_budget_planner_prefers_private_label_tools() -> None:
    planner = get_domain_planner(IntentEnum.BUDGET)
    assert planner.budget_mode() == "hard_fill"
    allowlist = planner.tool_allowlist()
    assert "search_products" in allowlist
    assert "get_promotions" in allowlist


def test_gourmet_planner_soft_budget_and_taste_tools() -> None:
    planner = get_domain_planner(IntentEnum.GOURMET)
    assert planner.budget_mode() == "soft"
    allowlist = planner.tool_allowlist()
    assert "get_product_details" in allowlist
    assert "get_similar_products" in allowlist


def test_office_planner_hard_fill_policy() -> None:
    planner = get_domain_planner(IntentEnum.OFFICE)
    assert planner.budget_mode() == "hard_fill"
    assert "search_products" in planner.tool_allowlist()


def test_planner_score_prefers_cheaper_within_budget() -> None:
    planner = get_domain_planner(IntentEnum.BUDGET)
    cheap = {"price": 30.0, "is_private_label": True, "quantity": 1}
    expensive = {"price": 300.0, "is_private_label": False, "quantity": 1}
    assert planner.score(cheap, remaining=500.0) > planner.score(expensive, remaining=500.0)


def test_planner_score_rejects_over_budget_hard_fill() -> None:
    planner = get_domain_planner(IntentEnum.BUDGET)
    over = {"price": 600.0, "is_private_label": False, "quantity": 1}
    assert planner.score(over, remaining=100.0) < 0
