"""Hybrid create_agent tools: pure-async domain wrappers returning Command state updates."""

import uuid
from typing import Any

from langchain.messages import ToolMessage
from langchain.tools import ToolRuntime, tool
from langgraph.types import Command

from .domain.planners import get_domain_planner
from .enums import IntentEnum, NodeName
from .services.mcp_service import mcp_product_service
from .state import SilpoAgentState


def _tool_message(runtime: ToolRuntime[None, SilpoAgentState], content: str) -> ToolMessage:
    return ToolMessage(content=content, tool_call_id=runtime.tool_call_id)


@tool
async def plan_items(
    runtime: ToolRuntime[None, SilpoAgentState],
    intent: str = "party",
    budget: float = 0.0,
    people_count: int | None = None,
    dietary_restrictions: list[str] | None = None,
) -> Command:
    """Plans shopping items and quantities for the given intent and budget."""
    try:
        parsed_intent = IntentEnum(intent)
    except ValueError:
        parsed_intent = IntentEnum.PARTY
    dietary = dietary_restrictions or []
    state = runtime.state or {}
    # Explicit args win; fall back to agent state for missing values
    if budget == 0.0:
        budget = float(state.get("budget", 0.0) or 0.0)
    if people_count is None:
        people_count = state.get("people_count")
    if not dietary:
        dietary = list(state.get("dietary_restrictions", []) or [])
    planner_state: dict[str, Any] = {
        "intent": parsed_intent,
        "budget": budget,
        "people_count": people_count,
        "dietary_restrictions": dietary,
        "attempts": state.get("attempts", 0),
        "is_budget_exceeded": state.get("is_budget_exceeded", False),
    }
    planner = get_domain_planner(parsed_intent)
    calculated = planner.plan(planner_state)  # type: ignore[arg-type]
    content = f"Planned {len(calculated)} items for intent={parsed_intent.value}"
    return Command(
        update={
            "intent": parsed_intent,
            "budget": budget,
            "people_count": people_count,
            "dietary_restrictions": dietary,
            "calculated_items": calculated,
            "current_step": NodeName.MCP_FETCH.value,
            "messages": [_tool_message(runtime, content)],
        }
    )


@tool
async def fetch_products(
    runtime: ToolRuntime[None, SilpoAgentState],
    calculated_items: list[dict[str, Any]] | None = None,
) -> Command:
    """Fetches SKU details, prices, and promotion flags via silpo-py-mcp."""
    items = calculated_items or []
    if not items:
        items = list((runtime.state or {}).get("calculated_items", []) or [])
    products = await mcp_product_service.fetch_products(items)
    content = f"Fetched {len(products)} products"
    return Command(
        update={
            "mcp_products": products,
            "current_step": NodeName.CHECK_CONSTRAINTS.value,
            "messages": [_tool_message(runtime, content)],
        }
    )


@tool
async def check_budget(
    runtime: ToolRuntime[None, SilpoAgentState],
    mcp_products: list[dict[str, Any]] | None = None,
    budget: float | None = None,
    attempts: int | None = None,
) -> Command:
    """Calculates total cart cost and checks it against the user budget."""
    state = runtime.state or {}
    products = mcp_products or []
    if not products:
        products = list(state.get("mcp_products", []) or [])
    if budget is None:
        budget = float(state.get("budget", 0.0) or 0.0)
    if attempts is None:
        attempts = int(state.get("attempts", 0) or 0)
    budget = float(budget or 0.0)
    attempts = int(attempts or 0) + 1
    total = round(sum(float(p.get("price", 0.0)) * int(p.get("quantity", 1)) for p in products), 2)
    exceeded = budget > 0 and total > budget
    next_step = NodeName.PLAN_DOMAIN_LOGIC.value if exceeded else NodeName.CREATE_CART.value
    content = f"Total {total}, budget {budget}, exceeded={exceeded}"
    return Command(
        update={
            "total_price": total,
            "attempts": attempts,
            "is_budget_exceeded": exceeded,
            "current_step": next_step,
            "messages": [_tool_message(runtime, content)],
        }
    )


@tool
async def create_cart(
    runtime: ToolRuntime[None, SilpoAgentState],
    intent: str | None = None,
    total_price: float | None = None,
    people_count: int | None = None,
    mcp_products: list[dict[str, Any]] | None = None,
) -> Command:
    """Generates the shareable Silpo cart link and summarizes the order."""
    state = runtime.state or {}
    raw_intent = intent or state.get("intent", IntentEnum.PARTY)
    try:
        parsed_intent = raw_intent if isinstance(raw_intent, IntentEnum) else IntentEnum(str(raw_intent))
    except ValueError:
        parsed_intent = IntentEnum.PARTY
    total = float(total_price) if total_price is not None else float(state.get("total_price", 0.0) or 0.0)
    people = people_count if people_count is not None else state.get("people_count", None)
    products = mcp_products if mcp_products is not None else list(state.get("mcp_products", []) or [])
    cart_id = uuid.uuid4().hex[:8]
    cart_url = f"https://silpo.ua/cart/share/mock_{cart_id}"
    planner = get_domain_planner(parsed_intent)
    planner_state: dict[str, Any] = {
        "intent": parsed_intent,
        "people_count": people,
        "mcp_products": products,
        "total_price": total,
    }
    summary = planner.format_summary(total, planner_state)  # type: ignore[arg-type]
    content = f"Cart {cart_url}: {summary}"
    return Command(
        update={
            "cart_url": cart_url,
            "summary_message": summary,
            "current_step": NodeName.TTS.value,
            "messages": [_tool_message(runtime, content)],
        }
    )
