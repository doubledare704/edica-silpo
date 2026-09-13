"""Weekly meal_plan must reach the client via SSE node_complete and the summary."""

import json

import pytest
from app.api.agent import _serialize_meal_plan
from app.domain.planners import BudgetDomainPlanner
from app.enums import IntentEnum
from app.main import app
from app.state import SilpoAgentState
from httpx import ASGITransport, AsyncClient


def _make_state(**overrides) -> SilpoAgentState:
    base: SilpoAgentState = {
        "intent": IntentEnum.BUDGET,
        "budget": 2000.0,
        "people_count": 2,
        "dietary_restrictions": [],
        "raw_item_requests": ["риба", "овочі", "крупа"],
        "calculated_items": [],
        "mcp_products": [{"id": "1", "title": "Хек", "price": 294.0, "quantity": 1}],
        "total_price": 294.0,
        "attempts": 0,
        "max_attempts": 3,
        "is_budget_exceeded": False,
        "messages": [],
    }
    base.update(overrides)  # type: ignore[typeddict-item]
    return base


def test_serialize_meal_plan_keeps_days() -> None:
    payload = _serialize_meal_plan(
        {"days": [{"day": "День 1", "dishes": ["Хек з гречкою"]}], "budget": 2000.0, "people_count": 2},
        IntentEnum.BUDGET,
    )
    assert payload is not None
    assert payload["days"] == [{"day": "День 1", "dishes": ["Хек з гречкою"]}]


def test_serialize_meal_plan_none_when_absent() -> None:
    assert _serialize_meal_plan(None, IntentEnum.BUDGET) is None
    assert _serialize_meal_plan({}, IntentEnum.BUDGET) is None


def test_serialize_meal_plan_none_for_non_budget_intent() -> None:
    payload = _serialize_meal_plan(
        {"days": [{"day": "День 1", "dishes": ["Хек з гречкою"]}], "budget": 2000.0, "people_count": 2},
        IntentEnum.PARTY,
    )
    assert payload is None


def test_budget_summary_mentions_week_with_meal_plan() -> None:
    planner = BudgetDomainPlanner()
    state = _make_state(meal_plan={"days": [{"day": "День 1", "dishes": ["Хек"]}]})  # type: ignore[typeddict-item]
    assert "тиждень" in planner.format_summary(294.0, state).lower()


def test_budget_summary_unchanged_without_meal_plan() -> None:
    planner = BudgetDomainPlanner()
    assert "тиждень" not in planner.format_summary(294.0, _make_state()).lower()


def test_budget_summary_weekly_wording_requires_budget_intent() -> None:
    planner = BudgetDomainPlanner()
    state = _make_state(
        intent=IntentEnum.PARTY,
        meal_plan={"days": [{"day": "День 1", "dishes": ["Хек"]}]},  # type: ignore[typeddict-item]
    )
    assert "тиждень" not in planner.format_summary(294.0, state).lower()


@pytest.mark.asyncio
async def test_stream_node_complete_carries_meal_plan() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "user_text": "Склади продукти на тиждень до 2000 гривень з рибою, овочами і крупою",
            "thread_id": "test-weekly-surface",
        }
        async with client.stream("POST", "/api/agent/stream", json=payload) as response:
            assert response.status_code == 200
            lines = [line.strip() async for line in response.aiter_lines() if line.strip()]
            data_lines = [line.replace("data: ", "") for line in lines if line.startswith("data: ")]
            thinking = [
                json.loads(lines[i + 1].replace("data: ", ""))
                for i, line in enumerate(lines[:-1])
                if line == "event: thinking_step"
            ]
            assert "plan_meals" in {item["node"] for item in thinking}
            last_data = json.loads(data_lines[-1])
            assert last_data["meal_plan"] is not None
            assert len(last_data["meal_plan"]["days"]) == 7
            assert "тиждень" in str(last_data["summary"]).lower()
