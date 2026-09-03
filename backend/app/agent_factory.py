"""Hybrid shopper_agent: create_agent subgraph with enum-routed structured output."""

from typing import Any

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langgraph.graph.state import CompiledStateGraph

from .agent_tools import check_budget, create_cart, fetch_products, plan_items
from .middleware import budget_guard, intent_router
from .prompts import BASE_PROMPT
from .router_schema import IntentRoute
from .state import SilpoAgentState

INTENT_RESPONSE_FORMAT = ToolStrategy(IntentRoute)

_SHOPPER_TOOLS: list[Any] = [plan_items, fetch_products, check_budget, create_cart]
_SHOPPER_MIDDLEWARE: list[Any] = [intent_router, budget_guard]


def create_shopper_agent(
    model: Any = None,
    checkpointer: Any | None = None,
    debug: bool = False,
) -> CompiledStateGraph:
    """Creates the ReAct sub-agent. Pure-async model calls; no sync fallback."""
    if model is None:
        from langchain_google_genai import ChatGoogleGenerativeAI

        from .config import settings

        model = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            google_api_key=settings.GEMINI_API_KEY or "test-placeholder-key",
            temperature=0.1,
        )
    return create_agent(
        model=model,
        tools=list(_SHOPPER_TOOLS),
        system_prompt=BASE_PROMPT,
        state_schema=SilpoAgentState,
        response_format=INTENT_RESPONSE_FORMAT,
        middleware=list(_SHOPPER_MIDDLEWARE),
        checkpointer=checkpointer,
        debug=debug,
        name="shopper_agent",
    )
