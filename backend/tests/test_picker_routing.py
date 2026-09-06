"""Phase 3: constraint fill/exit routing (remaining budget, requirements, progress guard)."""

import pytest
from app.enums import IntentEnum
from app.graph import route_constraints
from app.nodes.check_constraints import check_constraints_node
from app.state import SilpoAgentState


def _make_state(**overrides: object) -> SilpoAgentState:
    base: SilpoAgentState = {
        "intent": IntentEnum.PARTY,
        "budget": 1000.0,
        "people_count": 4,
        "dietary_restrictions": [],
        "raw_item_requests": [],
        "calculated_items": [],
        "mcp_products": [],
        "total_price": 0.0,
        "attempts": 0,
        "max_attempts": 3,
        "is_budget_exceeded": False,
        "remaining_budget": 0.0,
        "unfulfilled_requests": [],
        "is_requirements_met": True,
        "picker_trace": [],
        "picker_accepted": 0,
        "messages": [],
    }
    base.update(overrides)  # type: ignore[typeddict-item]
    return base


def _product(price: float, category: str, qty: int = 1) -> dict:
    return {
        "id": f"{category}-{price}",
        "title": category,
        "price": price,
        "is_private_label": False,
        "quantity": qty,
        "category": category,
    }


@pytest.mark.asyncio
async def test_check_constraints_computes_remaining_and_coverage() -> None:
    state = _make_state(
        budget=1000.0,
        mcp_products=[_product(240.0, "meat"), _product(85.0, "vegetables"), _product(22.0, "drinks")],
    )
    result = await check_constraints_node(state)
    assert result["total_price"] == 347.0
    assert result["remaining_budget"] == pytest.approx(653.0)
    assert result["is_budget_exceeded"] is False
    assert result["is_requirements_met"] is True


@pytest.mark.asyncio
async def test_check_constraints_flags_unmet_coverage() -> None:
    state = _make_state(
        budget=1000.0,
        mcp_products=[_product(22.0, "drinks")],
    )
    result = await check_constraints_node(state)
    assert result["is_requirements_met"] is False


@pytest.mark.asyncio
async def test_check_constraints_gourmet_soft_never_exceeds() -> None:
    state = _make_state(
        intent=IntentEnum.GOURMET,
        budget=100.0,
        mcp_products=[_product(400.0, "cheese"), _product(300.0, "wine")],
    )
    result = await check_constraints_node(state)
    assert result["is_budget_exceeded"] is False
    assert result["is_requirements_met"] is True


@pytest.mark.asyncio
async def test_check_constraints_legacy_products_assume_met() -> None:
    state = _make_state(
        budget=1000.0,
        mcp_products=[{"id": "sku-1", "title": "Ошийник", "price": 240.0, "quantity": 1}],
    )
    result = await check_constraints_node(state)
    assert result["is_requirements_met"] is True


def test_route_loops_to_picker_while_exceeded() -> None:
    state = _make_state(is_budget_exceeded=True, attempts=1, max_attempts=3)
    assert route_constraints(state) == "picker"


def test_route_loops_to_picker_when_requirements_unmet() -> None:
    state = _make_state(
        is_budget_exceeded=False, is_requirements_met=False, picker_accepted=2, attempts=1, max_attempts=3
    )
    assert route_constraints(state) == "picker"


def test_route_exits_when_picker_made_no_progress() -> None:
    state = _make_state(
        is_budget_exceeded=False, is_requirements_met=False, picker_accepted=0, attempts=1, max_attempts=3
    )
    assert route_constraints(state) == "create_cart"


def test_route_exits_when_met_and_within_budget() -> None:
    state = _make_state(is_budget_exceeded=False, is_requirements_met=True, attempts=1)
    assert route_constraints(state) == "create_cart"


def test_route_exits_when_attempts_exhausted() -> None:
    state = _make_state(is_budget_exceeded=True, is_requirements_met=False, attempts=3, max_attempts=3)
    assert route_constraints(state) == "create_cart"
