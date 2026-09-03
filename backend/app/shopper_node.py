"""Hybrid shopper_agent node: create_agent in prod, deterministic fallback offline.

Mock mode or missing key (tests/CI) runs the original deterministic nodes so the
pipeline never touches the network. Production (key present) delegates to the
compiled create_agent subgraph; any LLM failure falls back the same way.
"""

import logging
from typing import Any

from langchain_core.messages import HumanMessage

from .config import settings
from .enums import NodeName
from .state import SilpoAgentState

logger = logging.getLogger(__name__)

_AGENT: Any | None = None


def reset_shopper_agent() -> None:
    """Reset cached sub-agent (testing)."""
    global _AGENT
    _AGENT = None


def _get_agent() -> Any:
    global _AGENT
    if _AGENT is None:
        from .agent_factory import create_shopper_agent

        _AGENT = create_shopper_agent()
    return _AGENT


async def _deterministic_shopper(state: SilpoAgentState) -> dict[str, Any]:
    """Offline path: original nodes in legacy order with the budget retry loop."""
    from .nodes.check_constraints import check_constraints_node
    from .nodes.create_cart import create_cart_node
    from .nodes.mcp_fetch import mcp_fetch_node
    from .nodes.parse_intent import parse_intent_node
    from .nodes.plan_domain_logic import plan_domain_logic_node

    merged: dict[str, Any] = dict(state)
    update = await parse_intent_node(state)  # type: ignore[arg-type]
    merged.update(update)

    max_attempts = int(merged.get("max_attempts", 3) or 3)
    for _ in range(max_attempts):
        update = plan_domain_logic_node(merged)  # type: ignore[arg-type]
        merged.update(update)
        update = await mcp_fetch_node(merged)  # type: ignore[arg-type]
        merged.update(update)
        update = check_constraints_node(merged)  # type: ignore[arg-type]
        merged.update(update)
        is_exceeded = bool(merged.get("is_budget_exceeded", False))
        attempts = int(merged.get("attempts", 0) or 0)
        if not (is_exceeded and attempts < max_attempts):
            break

    update = create_cart_node(merged)  # type: ignore[arg-type]
    merged.update(update)
    return {
        "intent": merged.get("intent"),
        "budget": merged.get("budget", 0.0),
        "people_count": merged.get("people_count"),
        "dietary_restrictions": merged.get("dietary_restrictions", []),
        "raw_item_requests": merged.get("raw_item_requests", []),
        "calculated_items": merged.get("calculated_items", []),
        "mcp_products": merged.get("mcp_products", []),
        "total_price": merged.get("total_price", 0.0),
        "attempts": merged.get("attempts", 0),
        "max_attempts": merged.get("max_attempts", 3),
        "is_budget_exceeded": merged.get("is_budget_exceeded", False),
        "cart_url": merged.get("cart_url"),
        "summary_message": merged.get("summary_message", ""),
        "current_step": NodeName.TTS.value,
    }


async def shopper_agent_node(state: SilpoAgentState) -> dict[str, Any]:
    """Hybrid node: ReAct sub-agent in prod, deterministic fallback offline/on error."""
    if settings.GEMINI_MOCK_MODE or not settings.GEMINI_API_KEY:
        return await _deterministic_shopper(state)

    try:
        agent = _get_agent()
        messages = list(state.get("messages", []) or [])
        if not messages and state.get("user_text"):
            messages = [HumanMessage(content=state.get("user_text", ""))]
        result = await agent.ainvoke(
            {
                "messages": messages,
                "user_text": state.get("user_text"),
                "audio_bytes": state.get("audio_bytes"),
                "intent": state.get("intent"),
                "budget": state.get("budget", 0.0),
                "people_count": state.get("people_count"),
                "dietary_restrictions": state.get("dietary_restrictions", []),
                "raw_item_requests": state.get("raw_item_requests", []),
                "attempts": state.get("attempts", 0),
                "max_attempts": state.get("max_attempts", 3),
            }
        )
        update: dict[str, Any] = {
            "messages": result.get("messages", messages),
            "current_step": NodeName.TTS.value,
        }
        for key in (
            "intent",
            "budget",
            "people_count",
            "dietary_restrictions",
            "raw_item_requests",
            "calculated_items",
            "mcp_products",
            "total_price",
            "attempts",
            "is_budget_exceeded",
            "cart_url",
            "summary_message",
        ):
            if key in result:
                update[key] = result[key]
        structured = result.get("structured_response")
        if structured is not None and "intent" not in update:
            intent = getattr(structured, "intent", None)
            if intent is not None:
                update["intent"] = intent
        return update
    except Exception as exc:  # noqa: BLE001 - pipeline never breaks on LLM errors
        logger.warning("shopper_agent LLM path failed (%s), using deterministic fallback", exc)
        return await _deterministic_shopper(state)
