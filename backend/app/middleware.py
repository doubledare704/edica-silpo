"""Middleware: enum-driven dynamic prompt + budget retry guard."""

from typing import Any

from langchain.agents.middleware import ModelRequest, before_model, dynamic_prompt
from langgraph.runtime import Runtime

from .enums import IntentEnum
from .prompts import INTENT_PROMPTS
from .state import SilpoAgentState


def prompt_for_intent(intent: Any) -> str:
    """Pure helper (unit-testable): resolves per-intent system prompt."""
    try:
        parsed = intent if isinstance(intent, IntentEnum) else IntentEnum(str(intent)) if intent else IntentEnum.PARTY
    except ValueError:
        parsed = IntentEnum.PARTY
    return INTENT_PROMPTS.get(parsed, INTENT_PROMPTS[IntentEnum.PARTY])


@dynamic_prompt
def intent_router(request: ModelRequest) -> str:
    """Selects system prompt from router state intent (StrEnum, not strings)."""
    state = request.state or {}
    return prompt_for_intent(state.get("intent"))


def check_budget_limit(state: SilpoAgentState) -> dict[str, Any] | None:
    """Pure helper: jump to end only when exceeded AND attempts exhausted."""
    attempts = int(state.get("attempts", 0) or 0)
    max_attempts = int(state.get("max_attempts", 3) or 3)
    if bool(state.get("is_budget_exceeded", False)) and attempts >= max_attempts:
        return {"jump_to": "end"}
    return None


@before_model(state_schema=SilpoAgentState, can_jump_to=["end"])
def budget_guard(state: SilpoAgentState, runtime: Runtime[Any]) -> dict[str, Any] | None:
    """Stops the ReAct loop when the budget loop is exhausted (replaces _route_constraints)."""
    return check_budget_limit(state)
