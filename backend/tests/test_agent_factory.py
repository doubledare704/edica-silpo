"""Phase H4: enum-routed structured output + per-intent prompts + create_agent factory."""

import pytest
from pydantic import ValidationError


def test_intent_route_parses_str_enums() -> None:
    from app.enums import IntentEnum
    from app.router_schema import IntentRoute

    for value in ["party", "budget", "office", "gourmet"]:
        route = IntentRoute.model_validate({"intent": value, "budget": 100.0})
        assert route.intent == IntentEnum(value)
        assert route.intent.value == value
    with pytest.raises(ValidationError):
        IntentRoute.model_validate({"intent": "invalid_intent"})


def test_intent_prompts_cover_all_enums_ukrainian() -> None:
    from app.enums import IntentEnum
    from app.prompts import BASE_PROMPT, INTENT_PROMPTS

    assert len(BASE_PROMPT) > 20
    for intent in IntentEnum:
        assert intent in INTENT_PROMPTS, f"missing prompt for {intent}"
        assert len(INTENT_PROMPTS[intent]) > 20


def test_dynamic_prompt_routes_by_intent() -> None:
    from app.enums import IntentEnum
    from app.middleware import prompt_for_intent
    from app.prompts import INTENT_PROMPTS

    for intent in IntentEnum:
        assert prompt_for_intent(intent) == INTENT_PROMPTS[intent]
    # Fallback for unknown/None -> party prompt
    assert prompt_for_intent(None) == INTENT_PROMPTS[IntentEnum.PARTY]


def test_budget_guard_jumps_to_end_at_limit() -> None:
    from app.middleware import budget_guard

    over = budget_guard.before_model({"is_budget_exceeded": True, "attempts": 3, "max_attempts": 3}, None)
    assert over is not None and over.get("jump_to") == "end"

    retry = budget_guard.before_model({"is_budget_exceeded": True, "attempts": 1, "max_attempts": 3}, None)
    assert retry is None

    ok = budget_guard.before_model({"is_budget_exceeded": False, "attempts": 3, "max_attempts": 3}, None)
    assert ok is None


def test_create_shopper_agent_returns_compiled_graph() -> None:
    from app.agent_factory import create_shopper_agent
    from app.agent_tools import check_budget, create_cart, fetch_products, plan_items

    agent = create_shopper_agent()
    assert agent is not None
    node_names = set(agent.nodes.keys())
    # create_agent internal topology: model/agent loop + tools
    assert len(node_names) >= 2
    tool_names = {t.name for t in [plan_items, fetch_products, check_budget, create_cart]}
    assert tool_names == {"plan_items", "fetch_products", "check_budget", "create_cart"}


def test_structured_response_schema_is_intent_route() -> None:
    from app.agent_factory import INTENT_RESPONSE_FORMAT
    from app.router_schema import IntentRoute

    assert INTENT_RESPONSE_FORMAT is not None
    schema = getattr(INTENT_RESPONSE_FORMAT, "schema", INTENT_RESPONSE_FORMAT)
    assert schema is IntentRoute


def test_tools_bind_to_gemini_without_schema_error() -> None:
    """Regression: bind_tools raised PydanticInvalidForJsonSchema (CallableSchema).

    Root cause was runtime: ToolRuntime | None = None leaking into args_schema.
    Uses a placeholder key; conversion is fully local, no network.
    """
    from app.agent_tools import check_budget, create_cart, fetch_products, plan_items
    from langchain_google_genai import ChatGoogleGenerativeAI

    model = ChatGoogleGenerativeAI(model="gemini-3.7-flash", google_api_key="test-placeholder", temperature=0.1)
    bound = model.bind_tools([plan_items, fetch_products, check_budget, create_cart])
    assert bound is not None
