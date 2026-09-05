import pytest
from app.enums import IntentEnum
from app.nodes.parse_intent import parse_intent_node
from app.state import SilpoAgentState


@pytest.mark.asyncio
async def test_parse_intent_contract_fixture() -> None:
    initial_state: SilpoAgentState = {
        "audio_bytes": None,
        "user_text": "Збери кошик для пікніка на 6 людей до 2500 грн, один вегетаріанець",
        "intent": None,
        "budget": 0.0,
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
    result = await parse_intent_node(initial_state)

    assert result["intent"] == IntentEnum.PARTY
    assert result["budget"] == 2500.0
    assert result["people_count"] == 6
    assert "vegetarian" in result["dietary_restrictions"]
    assert len(result["raw_item_requests"]) > 0


@pytest.mark.asyncio
async def test_parse_intent_budget() -> None:
    initial_state: SilpoAgentState = {
        "audio_bytes": None,
        "user_text": "Економний кошик продуктів до 1000 грн",
        "intent": None,
        "budget": 0.0,
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
    result = await parse_intent_node(initial_state)

    assert result["intent"] == IntentEnum.BUDGET
    assert result["budget"] == 1000.0


@pytest.mark.asyncio
async def test_parse_intent_empty_text() -> None:
    initial_state: SilpoAgentState = {
        "audio_bytes": None,
        "user_text": None,
        "intent": None,
        "budget": 0.0,
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
    result = await parse_intent_node(initial_state)

    assert result["intent"] in (IntentEnum.PARTY, IntentEnum.BUDGET, None)
    assert result["budget"] == 0.0


@pytest.mark.asyncio
async def test_parse_intent_marks_unsupported_text() -> None:
    initial_state: SilpoAgentState = {
        "audio_bytes": None,
        "user_text": "Привіт, як справи? бла-бла-бла",
        "intent": None,
        "budget": 0.0,
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

    result = await parse_intent_node(initial_state)

    assert result["intent"] == IntentEnum.UNSUPPORTED
    assert result["raw_item_requests"] == []
