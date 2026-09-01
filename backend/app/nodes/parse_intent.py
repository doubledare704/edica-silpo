import re
from typing import Any

from pydantic import BaseModel, Field

from ..enums import IntentEnum
from ..state import AgentState


class ParsedIntentSchema(BaseModel):
    intent: IntentEnum = Field(default=IntentEnum.PARTY)
    budget: float = Field(default=0.0)
    people_count: int | None = Field(default=None)
    dietary_restrictions: list[str] = Field(default_factory=list)
    raw_item_requests: list[str] = Field(default_factory=list)


def _extract_intent_fallback(text: str) -> ParsedIntentSchema:
    text_lower = text.lower()

    # Intent detection
    if any(k in text_lower for k in ["бюджет", "дешев", "економ"]):
        intent = IntentEnum.BUDGET
    elif any(k in text_lower for k in ["офіс", "office", "снет"]):
        intent = IntentEnum.OFFICE
    elif any(k in text_lower for k in ["гурман", "вино", "сир", "gourmet"]):
        intent = IntentEnum.GOURMET
    else:
        intent = IntentEnum.PARTY

    # Budget extraction (e.g. "до 2500 грн", "2500 грн", "2500₴")
    budget = 0.0
    budget_match = re.search(r"(?:до\s*)?(\d+(?:[.,]\d+)?)\s*(?:грн|гривень|гривні|₴)", text_lower)
    if budget_match:
        budget = float(budget_match.group(1).replace(",", "."))

    # People count extraction (e.g. "на 6 людей", "6 осіб")
    people_count = None
    people_match = re.search(r"(?:на\s*)?(\d+)\s*(?:людей|осіб|чоловік|людини)", text_lower)
    if people_match:
        people_count = int(people_match.group(1))

    # Dietary restrictions
    dietary_restrictions: list[str] = []
    if "вегетаріан" in text_lower:
        dietary_restrictions.append("vegetarian")
    if "веган" in text_lower:
        dietary_restrictions.append("vegan")
    if "безлактоз" in text_lower:
        dietary_restrictions.append("lactose_free")
    if "безглютен" in text_lower:
        dietary_restrictions.append("gluten_free")

    # Raw item requests
    raw_item_requests: list[str] = []
    if intent == IntentEnum.PARTY:
        raw_item_requests = ["м'ясо", "овочі", "напої", "вугілля"]
    elif intent == IntentEnum.BUDGET:
        raw_item_requests = ["молоко", "хліб", "яйця", "масло", "крупа"]
    elif intent == IntentEnum.OFFICE:
        raw_item_requests = ["кава", "чай", "печиво", "вода", "фрукти"]
    elif intent == IntentEnum.GOURMET:
        raw_item_requests = ["сир", "вино", "прошуто", "оливки"]

    return ParsedIntentSchema(
        intent=intent,
        budget=budget,
        people_count=people_count,
        dietary_restrictions=dietary_restrictions,
        raw_item_requests=raw_item_requests,
    )


def parse_intent_node(state: AgentState) -> dict[str, Any]:
    """Extracts structured intent, budget, party size, and dietary restrictions."""
    user_text = state.get("user_text") or ""
    if not user_text.strip():
        return {
            "intent": state.get("intent") or IntentEnum.PARTY,
            "budget": state.get("budget", 0.0),
            "people_count": state.get("people_count"),
            "dietary_restrictions": state.get("dietary_restrictions", []),
            "raw_item_requests": state.get("raw_item_requests", []),
        }

    parsed = _extract_intent_fallback(user_text)
    return {
        "intent": parsed.intent,
        "budget": parsed.budget,
        "people_count": parsed.people_count,
        "dietary_restrictions": parsed.dietary_restrictions,
        "raw_item_requests": parsed.raw_item_requests,
    }
