import re

from pydantic import BaseModel, Field

from .enums import IntentEnum


class ParsedIntentSchema(BaseModel):
    intent: IntentEnum = Field(default=IntentEnum.PARTY)
    budget: float = Field(default=0.0)
    people_count: int | None = Field(default=None)
    dietary_restrictions: list[str] = Field(default_factory=list)
    raw_item_requests: list[str] = Field(default_factory=list)


# Ordered (item, text markers): first match wins per row, max 5 items kept.
_ITEM_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("курка", ("курк", "курятин", "курча")),
    ("печериці", ("печериц", "шампіньйон", "глив", "гриб")),
    ("овочі", ("овоч", "помідор", "огір", "перець", "кукурудз")),
    ("пиво", ("пиво", "пива")),
    ("вода", ("вода", "води", "воду")),
    ("хліб", ("хліб",)),
    ("сир", ("сир",)),
    ("вино", ("вино", "вина")),
    ("кава", ("кава", "кави")),
    ("чай", ("чай", "чаю")),
    ("молоко", ("молоко", "молока")),
    ("яйця", ("яйц",)),
    ("м'ясо", ("м'яс", "мяс")),
    ("вугілля", ("вугілл",)),
    ("посуд", ("посуд", "стакан", "таріл")),
)

_NON_ALCOHOLIC_ITEMS = ("пиво", "вино", "сидр")
_FRESH_ITEMS = ("печериці", "овочі")
_DISPOSABLE_ITEMS = ("посуд",)


def _extract_item_requests(text_lower: str) -> list[str]:
    """Pulls concrete item names from free text so offline parsing keeps qualifiers."""
    wants_free = "безалкогольн" in text_lower
    wants_fresh = "свіж" in text_lower
    wants_disposable = "одноразов" in text_lower
    items: list[str] = []
    for item, markers in _ITEM_KEYWORDS:
        if any(marker in text_lower for marker in markers):
            if wants_free and item in _NON_ALCOHOLIC_ITEMS:
                item += " безалкогольне"
            elif wants_fresh and item in _FRESH_ITEMS:
                item += " свіжі"
            elif wants_disposable and item in _DISPOSABLE_ITEMS:
                item += " одноразовий"
            items.append(item)
        if len(items) >= 5:
            break
    return items


def extract_intent_fallback(text: str) -> ParsedIntentSchema:
    text_lower = text.lower()

    if any(keyword in text_lower for keyword in ["бюджет", "дешев", "економ"]):
        intent = IntentEnum.BUDGET
    elif any(keyword in text_lower for keyword in ["офіс", "office", "снет"]):
        intent = IntentEnum.OFFICE
    elif any(keyword in text_lower for keyword in ["гурман", "вино", "сир", "gourmet"]):
        intent = IntentEnum.GOURMET
    elif any(
        keyword in text_lower
        for keyword in [
            "кошик",
            "зібрати",
            "збери",
            "продукт",
            "пікнік",
            "свят",
            "вечір",
            "гостей",
            "людей",
            "осіб",
            "м'ясо",
            "овоч",
            "напої",
            "вугілля",
        ]
    ):
        intent = IntentEnum.PARTY
    else:
        intent = IntentEnum.UNSUPPORTED

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

    raw_item_requests = (
        _extract_item_requests(text_lower)
        or {
            IntentEnum.PARTY: ["м'ясо", "овочі", "напої", "вугілля"],
            IntentEnum.BUDGET: ["молоко", "хліб", "яйця", "масло", "крупа"],
            IntentEnum.OFFICE: ["кава", "чай", "печиво", "вода", "фрукти"],
            IntentEnum.GOURMET: ["сир", "вино", "прошуто", "оливки"],
            IntentEnum.UNSUPPORTED: [],
        }[intent]
    )

    return ParsedIntentSchema(
        intent=intent,
        budget=budget,
        people_count=people_count,
        dietary_restrictions=dietary_restrictions,
        raw_item_requests=raw_item_requests,
    )
