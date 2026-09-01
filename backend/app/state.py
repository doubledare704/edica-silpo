from typing import Any, TypedDict

from langchain_core.messages import BaseMessage

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
