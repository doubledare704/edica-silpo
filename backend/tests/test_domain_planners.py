from app.domain.planners import (
    BudgetDomainPlanner,
    GeneralDomainPlanner,
    GourmetDomainPlanner,
    OfficeDomainPlanner,
    PartyDomainPlanner,
    get_domain_planner,
)
from app.enums import IntentEnum
from app.state import SilpoAgentState


def _make_state(intent: IntentEnum | None, **overrides: object) -> SilpoAgentState:
    base: SilpoAgentState = {
        "audio_bytes": None,
        "user_text": None,
        "intent": intent,
        "budget": 1000.0,
        "people_count": None,
        "dietary_restrictions": [],
        "raw_item_requests": [],
        "calculated_items": [],
        "mcp_products": [],
        "total_price": 0.0,
        "attempts": 0,
        "max_attempts": 3,
        "is_budget_exceeded": False,
        "cart_url": None,
        "summary_message": "",
        "audio_url": None,
        "messages": [],
    }
    base.update(overrides)  # type: ignore[typeddict-item]
    return base


def test_get_domain_planner_instances() -> None:
    assert isinstance(get_domain_planner(IntentEnum.PARTY), PartyDomainPlanner)
    assert isinstance(get_domain_planner(IntentEnum.BUDGET), BudgetDomainPlanner)
    assert isinstance(get_domain_planner(IntentEnum.OFFICE), OfficeDomainPlanner)
    assert isinstance(get_domain_planner(IntentEnum.GOURMET), GourmetDomainPlanner)
    assert isinstance(get_domain_planner(None), GeneralDomainPlanner)


def test_budget_planner_plan_and_summary() -> None:
    planner = BudgetDomainPlanner()
    state = _make_state(
        IntentEnum.BUDGET,
        budget=500.0,
        mcp_products=[{"id": "1", "title": "Хліб", "price": 28.5, "quantity": 1}],
        total_price=28.5,
    )
    items = planner.plan(state)
    assert len(items) == 3
    summary = planner.format_summary(28.5, state)
    assert "економний кошик" in summary


# ── OFFICE ────────────────────────────────────────────────────────────────────


def test_office_planner_returns_items() -> None:
    planner = OfficeDomainPlanner()
    state = _make_state(IntentEnum.OFFICE, people_count=10)
    items = planner.plan(state)
    assert len(items) >= 1


def test_office_planner_items_have_required_keys() -> None:
    planner = OfficeDomainPlanner()
    state = _make_state(IntentEnum.OFFICE, people_count=5)
    for item in planner.plan(state):
        assert "query" in item
        assert "quantity" in item
        assert "category" in item
        assert "prefer_private_label" in item


def test_office_planner_prefers_private_label() -> None:
    """Office planner always targets cost-efficient private label items."""
    planner = OfficeDomainPlanner()
    state = _make_state(IntentEnum.OFFICE)
    items = planner.plan(state)
    assert all(item["prefer_private_label"] for item in items)


def test_office_planner_scales_quantity_with_people() -> None:
    planner = OfficeDomainPlanner()
    small = planner.plan(_make_state(IntentEnum.OFFICE, people_count=5))
    large = planner.plan(_make_state(IntentEnum.OFFICE, people_count=20))
    small_total = sum(i["quantity"] for i in small)
    large_total = sum(i["quantity"] for i in large)
    assert large_total > small_total


def test_office_planner_reduces_on_retry() -> None:
    planner = OfficeDomainPlanner()
    normal = planner.plan(_make_state(IntentEnum.OFFICE, people_count=10))
    retry = planner.plan(_make_state(IntentEnum.OFFICE, people_count=10, is_budget_exceeded=True, attempts=1))
    assert sum(i["quantity"] for i in retry) <= sum(i["quantity"] for i in normal)


def test_office_planner_format_summary() -> None:
    planner = OfficeDomainPlanner()
    state = _make_state(
        IntentEnum.OFFICE,
        mcp_products=[{"id": "1", "title": "Кава", "price": 120.0}],
        total_price=350.0,
    )
    summary = planner.format_summary(350.0, state)
    assert "офіс" in summary.lower()
    assert "350" in summary


# ── GOURMET ───────────────────────────────────────────────────────────────────


def test_gourmet_planner_returns_items() -> None:
    planner = GourmetDomainPlanner()
    state = _make_state(IntentEnum.GOURMET)
    items = planner.plan(state)
    assert len(items) >= 1


def test_gourmet_planner_items_have_required_keys() -> None:
    planner = GourmetDomainPlanner()
    state = _make_state(IntentEnum.GOURMET)
    for item in planner.plan(state):
        assert "query" in item
        assert "quantity" in item
        assert "category" in item
        assert "prefer_private_label" in item


def test_gourmet_planner_does_not_prefer_private_label() -> None:
    """Gourmet planner targets premium artisanal products, not private label."""
    planner = GourmetDomainPlanner()
    state = _make_state(IntentEnum.GOURMET)
    items = planner.plan(state)
    assert all(not item["prefer_private_label"] for item in items)


def test_gourmet_planner_includes_cheese_and_wine() -> None:
    planner = GourmetDomainPlanner()
    state = _make_state(IntentEnum.GOURMET)
    items = planner.plan(state)
    categories = {i["category"] for i in items}
    assert "cheese" in categories
    assert "wine" in categories


def test_gourmet_planner_uses_raw_requests_as_hints() -> None:
    """When raw_item_requests contains a specific item, it appears in the plan."""
    planner = GourmetDomainPlanner()
    state = _make_state(IntentEnum.GOURMET, raw_item_requests=["камамбер"])
    items = planner.plan(state)
    queries = [i["query"].lower() for i in items]
    assert any("камамбер" in q for q in queries)


def test_gourmet_planner_reduces_on_retry() -> None:
    planner = GourmetDomainPlanner()
    normal = planner.plan(_make_state(IntentEnum.GOURMET))
    retry = planner.plan(_make_state(IntentEnum.GOURMET, is_budget_exceeded=True, attempts=1))
    assert sum(i["quantity"] for i in retry) <= sum(i["quantity"] for i in normal)


def test_gourmet_planner_format_summary() -> None:
    planner = GourmetDomainPlanner()
    state = _make_state(
        IntentEnum.GOURMET,
        mcp_products=[{"id": "1", "title": "Камамбер", "price": 220.0}],
        total_price=680.0,
    )
    summary = planner.format_summary(680.0, state)
    assert "680" in summary
    assert any(kw in summary.lower() for kw in ("гурман", "сир", "вин", "паруван", "підбір"))
