from typing import Any, NotRequired

from langchain.agents import AgentState as LangChainAgentState
from langchain_core.messages import BaseMessage
from typing_extensions import TypedDict

from .enums import IntentEnum


class AgentState(TypedDict):
    audio_bytes: bytes | None
    user_text: str | None
    intent: IntentEnum | None
    budget: float
    people_count: int | None
    dietary_restrictions: list[str]
    raw_item_requests: list[str]
    calculated_items: list[dict[str, Any]]
    mcp_products: list[dict[str, Any]]
    total_price: float
    attempts: int
    max_attempts: int
    is_budget_exceeded: bool
    cart_url: str | None
    summary_message: str
    audio_url: str | None
    messages: list[BaseMessage]


class SilpoAgentState(LangChainAgentState):
    """Hybrid create_agent state: inherits messages (add_messages reducer) + domain fields."""

    audio_bytes: NotRequired[bytes | None]
    user_text: NotRequired[str | None]
    intent: NotRequired[IntentEnum | None]
    budget: NotRequired[float]
    people_count: NotRequired[int | None]
    dietary_restrictions: NotRequired[list[str]]
    raw_item_requests: NotRequired[list[str]]
    calculated_items: NotRequired[list[dict[str, Any]]]
    mcp_products: NotRequired[list[dict[str, Any]]]
    total_price: NotRequired[float]
    attempts: NotRequired[int]
    max_attempts: NotRequired[int]
    is_budget_exceeded: NotRequired[bool]
    cart_url: NotRequired[str | None]
    summary_message: NotRequired[str]
    audio_url: NotRequired[str | None]
    current_step: NotRequired[str]
