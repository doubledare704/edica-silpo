"""Phase H5: hybrid 3-node wrapper — deterministic fallback offline, create_agent in prod."""

import pytest
from app.enums import IntentEnum
from langchain_core.messages import HumanMessage


def _base_state(**overrides):
    state = {
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
        "messages": [HumanMessage(content="Збери кошик")],
    }
    state.update(overrides)
    return state


@pytest.mark.asyncio
async def test_shopper_node_fallback_no_network(monkeypatch) -> None:
    """Mock mode / missing key must never touch the network."""
    import app.shopper_node as node

    monkeypatch.setattr(node.settings, "GEMINI_MOCK_MODE", True)
    monkeypatch.setattr(node.settings, "GEMINI_API_KEY", "")
    node.reset_shopper_agent()

    from app.shopper_node import shopper_agent_node

    update = await shopper_agent_node(_base_state())
    assert update["intent"] == IntentEnum.PARTY
    assert update["budget"] == 2500.0
    assert len(update["calculated_items"]) > 0
    assert len(update["mcp_products"]) > 0
    assert update["total_price"] > 0
    assert update["cart_url"].startswith("https://silpo.ua/cart")
    assert len(update["summary_message"]) > 0


@pytest.mark.asyncio
async def test_shopper_node_falls_back_on_agent_error(monkeypatch) -> None:
    import app.shopper_node as node

    monkeypatch.setattr(node.settings, "GEMINI_MOCK_MODE", False)
    monkeypatch.setattr(node.settings, "GEMINI_API_KEY", "fake-key")

    class _Boom:
        async def ainvoke(self, *args, **kwargs):
            raise RuntimeError("LLM down")

    monkeypatch.setattr(node, "_AGENT", _Boom())
    from app.shopper_node import shopper_agent_node

    update = await shopper_agent_node(_base_state())
    # Pipeline never breaks: deterministic fallback still delivers a cart
    assert update["cart_url"].startswith("https://silpo.ua/cart")

    node.reset_shopper_agent()


def test_inner_to_legacy_covers_all_node_names() -> None:
    from app.enums import NodeName
    from app.graph import INNER_TO_LEGACY

    covered = set(INNER_TO_LEGACY.values())
    for legacy in [
        NodeName.PARSE_INTENT,
        NodeName.PLAN_DOMAIN_LOGIC,
        NodeName.MCP_FETCH,
        NodeName.CHECK_CONSTRAINTS,
        NodeName.CREATE_CART,
    ]:
        assert legacy in covered, f"mapper must emit legacy step {legacy}"
