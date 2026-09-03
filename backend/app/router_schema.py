"""Typed router decision: parsed to StrEnum values, drives prompt/tool selection."""

from pydantic import BaseModel, Field

from .enums import IntentEnum


class IntentRoute(BaseModel):
    """Structured router output. intent is a strict StrEnum — invalid values raise."""

    intent: IntentEnum = Field(description="Router decision: party, budget, office, or gourmet")
    budget: float = Field(default=0.0, description="Budget in UAH")
    people_count: int | None = Field(default=None, description="Number of people")
    dietary_restrictions: list[str] = Field(
        default_factory=list,
        description="Subset of vegetarian, vegan, lactose_free, gluten_free",
    )
    raw_item_requests: list[str] = Field(
        default_factory=list,
        description="Ukrainian product names, 2-5 items",
    )
