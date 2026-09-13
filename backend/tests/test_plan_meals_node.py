"""TDD for the dedicated plan_meals node (weekly menu for a specific budget)."""

import pytest
from app.enums import IntentEnum
from app.state import SilpoAgentState


def _make_state(**overrides) -> SilpoAgentState:
    base: SilpoAgentState = {
        "audio_bytes": None,
        "user_text": "Склади продукти на тиждень до 2000 гривень з рибою, овочами і крупою",
        "intent": IntentEnum.BUDGET,
        "budget": 2000.0,
        "people_count": 2,
        "dietary_restrictions": [],
        "raw_item_requests": ["риба", "овочі", "крупа"],
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


@pytest.mark.asyncio
async def test_weekly_budget_triggers_meal_plan() -> None:
    from app.nodes.plan_meals import plan_meals_node

    result = await plan_meals_node(_make_state())
    assert result.get("meal_plan") is not None
    seed = result.get("calculated_items", [])
    queries = [str(item["query"]).lower() for item in seed]
    assert any("хек" in q or "риб" in q for q in queries)
    assert any("овоч" in q for q in queries)
    assert any("крупа" in q or "греч" in q for q in queries)
    assert all(int(item["quantity"]) <= 6 for item in seed)
    days = result["meal_plan"].get("days", [])
    assert len(days) == 7


@pytest.mark.asyncio
async def test_non_weekly_passthrough() -> None:
    from app.nodes.plan_meals import plan_meals_node

    state = _make_state(
        intent=IntentEnum.PARTY,
        budget=2500.0,
        user_text="Збери кошик для пікніка",
        raw_item_requests=["м'ясо", "овочі"],
    )
    result = await plan_meals_node(state)
    assert result.get("meal_plan") is None
    assert result.get("calculated_items", []) == []


@pytest.mark.asyncio
async def test_meal_plan_fallback_when_llm_fails(monkeypatch) -> None:
    from app.nodes import plan_meals as plan_meals_module

    async def _boom(_goal: str):
        raise RuntimeError("llm down")

    monkeypatch.setattr(plan_meals_module.gemini_service, "plan_weekly_meals", _boom)
    from app.nodes.plan_meals import plan_meals_node

    result = await plan_meals_node(_make_state())
    assert result.get("meal_plan") is not None
    assert len(result.get("calculated_items", [])) >= 3


@pytest.mark.asyncio
async def test_meal_plan_backfills_missing_coverage_from_llm_seed(monkeypatch) -> None:
    from app.nodes import plan_meals as plan_meals_module
    from app.nodes.plan_meals import plan_meals_node

    async def _thin_seed(_goal: str):
        return [
            {"query": "Хек свіжоморожений", "category": "meat", "quantity": 2},
            {"query": "Крупа гречана", "category": "grocery", "quantity": 1},
        ]

    monkeypatch.setattr(plan_meals_module.gemini_service, "plan_weekly_meals", _thin_seed)
    result = await plan_meals_node(_make_state())
    seed = result.get("calculated_items", [])
    categories = {str(item.get("category")) for item in seed}
    assert {"grocery", "dairy", "bakery", "meat"} <= categories
    queries = [str(item["query"]).lower() for item in seed]
    assert any("хек" in q for q in queries)
    assert any("греч" in q or "крупа" in q for q in queries)
    assert sum("хек" in q for q in queries) == 1
    assert all(int(item["quantity"]) <= 6 for item in seed)


@pytest.mark.asyncio
async def test_plan_domain_logic_prefers_meal_plan_seed(monkeypatch) -> None:
    from app.nodes.plan_domain_logic import plan_domain_logic_node
    from app.services import gemini_service

    async def _researched(_goal: str):
        return [{"query": "Курка", "category": "meat", "quantity": 5}]

    monkeypatch.setattr(gemini_service, "research_menu", _researched)
    state = _make_state()
    state["meal_plan"] = {
        "days": [],
        "shopping_seed": [{"query": "Хек свіжоморожений", "category": "meat", "quantity": 2}],
    }  # type: ignore[typeddict-item]
    result = await plan_domain_logic_node(state)
    queries = [str(item["query"]).lower() for item in result["calculated_items"]]
    assert any("хек" in q for q in queries)
    assert not any(q == "курка" for q in queries)


@pytest.mark.asyncio
async def test_plan_domain_logic_ignores_meal_plan_seed_for_non_budget(monkeypatch) -> None:
    from app.nodes.plan_domain_logic import plan_domain_logic_node
    from app.services import gemini_service

    async def _researched(_goal: str):
        return [{"query": "Курка", "category": "meat", "quantity": 5}]

    monkeypatch.setattr(gemini_service, "research_menu", _researched)
    state = _make_state(
        intent=IntentEnum.PARTY,
        budget=2500.0,
        user_text="Збери кошик для пікніка",
        raw_item_requests=["м'ясо", "овочі"],
    )
    state["meal_plan"] = {
        "days": [{"day": "День 1", "dishes": ["Хек з гречкою"]}],
        "shopping_seed": [{"query": "Хек свіжоморожений", "category": "meat", "quantity": 2}],
    }  # type: ignore[typeddict-item]
    result = await plan_domain_logic_node(state)
    queries = [str(item["query"]).lower() for item in result["calculated_items"]]
    assert not any("хек" in q for q in queries)
    assert any(q == "курка" for q in queries)


def test_graph_orders_plan_meals() -> None:
    from app.graph import create_silpo_agent_graph

    graph = create_silpo_agent_graph()
    nodes = set(graph.nodes.keys())
    assert "plan_meals" in nodes
