import re

from pydantic import BaseModel, Field

from .enums import IntentEnum


class ParsedIntentSchema(BaseModel):
    intent: IntentEnum = Field(default=IntentEnum.PARTY)
    budget: float = Field(default=0.0)
    people_count: int | None = Field(default=None)
    dietary_restrictions: list[str] = Field(default_factory=list)
    raw_item_requests: list[str] = Field(default_factory=list)


def extract_intent_fallback(text: str) -> ParsedIntentSchema:
    text_lower = text.lower()

    if any(keyword in text_lower for keyword in ["бюджет", "дешев", "економ"]):
        intent = IntentEnum.BUDGET
    elif any(keyword in text_lower for keyword in ["офіс", "office", "снет"]):
        intent = IntentEnum.OFFICE
    elif any(keyword in text_lower for keyword in ["гурман", "вино", "сир", "gourmet"]):
        intent = IntentEnum.GOURMET
    else:
        intent = IntentEnum.PARTY

    budget = 0.0
    budget_match = re.search(r"(?:до\s*)?(\d+(?:[.,]\d+)?)\s*(?:грн|гривень|гривні|₴)", text_lower)
    if budget_match:
        budget = float(budget_match.group(1).replace(",", "."))

    people_count = None
    people_match = re.search(r"(?:на\s*)?(\d+)\s*(?:людей|осіб|чоловік|людини)", text_lower)
    if people_match:
        people_count = int(people_match.group(1))

    dietary_restrictions: list[str] = []
    if "вегетаріан" in text_lower:
        dietary_restrictions.append("vegetarian")
    if "веган" in text_lower:
        dietary_restrictions.append("vegan")
    if "безлактоз" in text_lower:
        dietary_restrictions.append("lactose_free")
    if "безглютен" in text_lower:
        dietary_restrictions.append("gluten_free")

    raw_item_requests = {
        IntentEnum.PARTY: ["м'ясо", "овочі", "напої", "вугілля"],
        IntentEnum.BUDGET: ["молоко", "хліб", "яйця", "масло", "крупа"],
        IntentEnum.OFFICE: ["кава", "чай", "печиво", "вода", "фрукти"],
        IntentEnum.GOURMET: ["сир", "вино", "прошуто", "оливки"],
    }[intent]

    return ParsedIntentSchema(
        intent=intent,
        budget=budget,
        people_count=people_count,
        dietary_restrictions=dietary_restrictions,
        raw_item_requests=raw_item_requests,
    )
