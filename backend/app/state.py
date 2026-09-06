from typing import Annotated, Any, NotRequired

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from .enums import IntentEnum


class SilpoAgentState(TypedDict, total=False):
    """Shared state for the explicit LangGraph workflow."""

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
    delivery_address: NotRequired[str | None]
    fulfillment: NotRequired[dict[str, Any] | None]
    remaining_budget: NotRequired[float]
    unfulfilled_requests: NotRequired[list[str]]
    is_requirements_met: NotRequired[bool]
    picker_trace: NotRequired[list[dict[str, Any]]]
    picker_accepted: NotRequired[int]
    shopping_context: NotRequired[dict[str, str] | None]
    checkout_url: NotRequired[str | None]
    cart_validations: NotRequired[list[dict[str, Any]]]
    loyalty_hint: NotRequired[str | None]
    current_step: NotRequired[str]
    messages: Annotated[list[BaseMessage], add_messages]
