from typing import Any

import pytest
from app.enums import IntentEnum
from app.nodes.plan_domain_logic import plan_domain_logic_node
from app.state import SilpoAgentState


@pytest.mark.asyncio
async def test_plan_domain_logic_party_intent() -> None:
    state: SilpoAgentState = {
        "audio_bytes": None,
        "user_text": "Збери кошик для пікніка на 6 людей до 2500 грн, один вегетаріанець",
        "intent": IntentEnum.PARTY,
        "budget": 2500.0,
        "people_count": 6,
        "dietary_restrictions": ["vegetarian"],
        "raw_item_requests": ["м'ясо", "овочі", "напої", "вугілля"],
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
    result = await plan_domain_logic_node(state)
    assert "calculated_items" in result
    items = result["calculated_items"]
    assert len(items) > 0
    item_names = [i["query"].lower() for i in items]
    assert any("м'ясо" in name or "ошийник" in name for name in item_names)
    assert any("овочі" in name or "гриль" in name for name in item_names)


@pytest.mark.asyncio
async def test_plan_domain_logic_budget_reduction_on_retry() -> None:
    state: SilpoAgentState = {
        "audio_bytes": None,
        "user_text": "Пікнік",
        "intent": IntentEnum.PARTY,
        "budget": 500.0,
        "people_count": 6,
        "dietary_restrictions": [],
        "raw_item_requests": ["м'ясо", "овочі", "напої", "вугілля"],
        "calculated_items": [
            {"query": "Ошийник свинячий", "quantity": 4, "target_type": "standard"},
            {"query": "Овочі для гриля", "quantity": 3, "target_type": "standard"},
        ],
        "mcp_products": [],
        "total_price": 1200.0,
        "attempts": 1,
        "max_attempts": 3,
        "is_budget_exceeded": True,
        "cart_url": None,
        "summary_message": "",
        "audio_url": None,
        "messages": [],
    }
    result = await plan_domain_logic_node(state)
    items = result["calculated_items"]
    assert len(items) > 0
    quantities = [i["quantity"] for i in items]
    assert sum(quantities) <= 5


@pytest.mark.asyncio
async def test_plan_domain_logic_uses_researched_menu(monkeypatch) -> None:
    from app.services import gemini_service

    menu = [
        {"query": "Курка для гриля", "category": "meat", "quantity": 2, "dish": "Курка-гриль"},
        {"query": "Печериці свіжі", "category": "vegetables", "quantity": 1, "dish": "Печериці на грилі"},
    ]

    async def _researched(goal: str) -> list[dict[str, Any]] | None:
        assert "гриль" in goal.lower()
        return menu

    monkeypatch.setattr(gemini_service, "research_menu", _researched)
    state: SilpoAgentState = {
        "audio_bytes": None,
        "user_text": "Збери друзів на гриль: курка та печериці",
        "intent": IntentEnum.PARTY,
        "budget": 5000.0,
        "people_count": 5,
        "dietary_restrictions": [],
        "raw_item_requests": ["курка", "печериці"],
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
    result = await plan_domain_logic_node(state)
    assert result["calculated_items"] == menu
