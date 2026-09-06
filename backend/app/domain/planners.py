import math
from typing import Any, ClassVar, Protocol

from ..enums import IntentEnum
from ..state import SilpoAgentState


class DomainPlanner(Protocol):
    def plan(self, state: SilpoAgentState) -> list[dict[str, Any]]:
        """Generates calculated item requests with quantities and preferences."""
        ...

    def format_summary(self, total_price: float, state: SilpoAgentState) -> str:
        """Formats Ukrainian summary text for the created cart."""
        ...


class PartyDomainPlanner:
    def plan(self, state: SilpoAgentState) -> list[dict[str, Any]]:
        people_count = state.get("people_count") or 1
        dietary = state.get("dietary_restrictions") or []
        is_retry = state.get("is_budget_exceeded", False)
        attempts = state.get("attempts", 0)

        is_vegetarian = "vegetarian" in dietary or "vegan" in dietary
        veg_count = 1 if is_vegetarian else 0
        non_veg_count = max(0, people_count - veg_count)

        calculated_items: list[dict[str, Any]] = []

        # Meat portion calculation
        if non_veg_count > 0:
            meat_qty = max(1, math.ceil(non_veg_count * 0.4))
            if is_retry and attempts > 0:
                meat_qty = max(1, meat_qty - attempts)
            calculated_items.append(
                {
                    "query": "Ошийник свинячий",
                    "category": "meat",
                    "quantity": meat_qty,
                    "prefer_private_label": is_retry,
                }
            )

        # Vegetables portion calculation (additional if vegetarians present)
        veg_qty = max(1, math.ceil((people_count + veg_count) * 0.3))
        if is_retry and attempts > 0:
            veg_qty = max(1, veg_qty - attempts)
        calculated_items.append(
            {
                "query": "Овочі для гриля Премія",
                "category": "vegetables",
                "quantity": veg_qty,
                "prefer_private_label": True,
            }
        )

        # Mineral water & beverages
        drinks_qty = max(1, math.ceil(people_count * 0.25))
        if is_retry and attempts > 0:
            drinks_qty = max(1, drinks_qty - attempts)
        calculated_items.append(
            {
                "query": "Вода мінеральна",
                "category": "drinks",
                "quantity": drinks_qty,
                "prefer_private_label": is_retry,
            }
        )

        # Coal accessories
        if not is_retry or attempts == 0:
            calculated_items.append(
                {
                    "query": "Вугілля деревне",
                    "category": "accessories",
                    "quantity": 1,
                    "prefer_private_label": is_retry,
                }
            )

        return calculated_items

    def format_summary(self, total_price: float, state: SilpoAgentState) -> str:
        people_count = state.get("people_count") or 1
        return f"Я зібрала кошик для пікніка на {people_count} осіб на суму {int(total_price)} гривень."


class BudgetDomainPlanner:
    def plan(self, state: SilpoAgentState) -> list[dict[str, Any]]:
        return [
            {
                "query": "Молоко Премія 2.5%",
                "category": "dairy",
                "quantity": 1,
                "prefer_private_label": True,
            },
            {
                "query": "Хліб український нарізний",
                "category": "bakery",
                "quantity": 1,
                "prefer_private_label": True,
            },
            {
                "query": "Яйця курячі С1, 10 шт",
                "category": "grocery",
                "quantity": 1,
                "prefer_private_label": True,
            },
        ]

    def format_summary(self, total_price: float, state: SilpoAgentState) -> str:
        products_count = len(state.get("mcp_products", []))
        return f"Я підібрала економний кошик із {products_count} товарів на суму {int(total_price)} гривень."


class OfficeDomainPlanner:
    """B2B office snack procurement planner.

    Calculates a weekly snack and beverage set for a team, always targeting
    private-label SKUs to minimise cost per head.  Quantities scale linearly
    with *people_count* and shrink on budget-exceeded retries.
    """

    # Base weekly quantities per person (fractional; rounded up)
    _PER_PERSON: ClassVar[list[tuple[str, str, float]]] = [
        ("Кава розчинна Премія", "coffee", 0.15),
        ("Чай чорний пакетований Премія", "tea", 0.15),
        ("Цукор Премія 1 кг", "grocery", 0.10),
        ("Печиво вівсяне Премія", "snacks", 0.20),
        ("Вода питна негазована 1.5 л Премія", "drinks", 0.30),
    ]

    def plan(self, state: SilpoAgentState) -> list[dict[str, Any]]:
        people_count = state.get("people_count") or 5  # default office of 5
        is_retry = state.get("is_budget_exceeded", False)
        attempts = state.get("attempts", 0)

        items: list[dict[str, Any]] = []
        for query, category, per_person_rate in self._PER_PERSON:
            qty = max(1, math.ceil(people_count * per_person_rate))
            if is_retry and attempts > 0:
                qty = max(1, qty - attempts)
            items.append(
                {
                    "query": query,
                    "category": category,
                    "quantity": qty,
                    "prefer_private_label": True,
                }
            )

        return items

    def format_summary(self, total_price: float, state: SilpoAgentState) -> str:
        products_count = len(state.get("mcp_products", []))
        return f"Я сформувала офісний кошик із {products_count} товарів на суму {int(total_price)} гривень."


class GourmetDomainPlanner:
    """Gourmet sommelier pairing planner.

    Builds a curated selection of artisanal cheeses and wines.  Never uses
    private-label items — quality is the primary constraint.  When
    *raw_item_requests* is provided, the first item is treated as the anchor
    ingredient and placed first in the plan.  Quantities reduce on retry.
    """

    _DEFAULT_PAIRINGS: ClassVar[list[tuple[str, str]]] = [
        ("Сир брі", "cheese"),
        ("Вино біле сухе El Maestro", "wine"),
        ("Сир горгонзола", "cheese"),
        ("Вино червоне сухе Chianti", "wine"),
        ("Крекери до вина", "crackers"),
        ("Виноград кишмиш", "fruit"),
    ]

    def plan(self, state: SilpoAgentState) -> list[dict[str, Any]]:
        raw_requests = state.get("raw_item_requests") or []
        is_retry = state.get("is_budget_exceeded", False)
        attempts = state.get("attempts", 0)

        items: list[dict[str, Any]] = []

        # Honour explicit customer requests as cheese anchors
        for req in raw_requests:
            items.append(
                {
                    "query": req,
                    "category": "cheese",
                    "quantity": 1,
                    "prefer_private_label": False,
                }
            )

        # Fill with curated default pairings (skip duplication with requests)
        request_lower = {r.lower() for r in raw_requests}
        for query, category in self._DEFAULT_PAIRINGS:
            if query.lower() not in request_lower:
                qty = 1
                if is_retry and attempts > 0 and category not in {"cheese", "wine"}:
                    # On retry, trim accompanying items first
                    continue
                items.append(
                    {
                        "query": query,
                        "category": category,
                        "quantity": qty,
                        "prefer_private_label": False,
                    }
                )

        # Ensure at least one cheese + one wine even on retry
        categories_present = {i["category"] for i in items}
        if "cheese" not in categories_present:
            items.insert(0, {"query": "Сир брі", "category": "cheese", "quantity": 1, "prefer_private_label": False})
        if "wine" not in categories_present:
            items.append(
                {"query": "Вино біле сухе El Maestro", "category": "wine", "quantity": 1, "prefer_private_label": False}
            )

        return items

    def format_summary(self, total_price: float, state: SilpoAgentState) -> str:
        products_count = len(state.get("mcp_products", []))
        return f"Я підібрала гурманський кошик із {products_count} сирів та вин на суму {int(total_price)} гривень."


class GeneralDomainPlanner:
    def plan(self, state: SilpoAgentState) -> list[dict[str, Any]]:
        raw_items = state.get("raw_item_requests") or ["продукти"]
        is_retry = state.get("is_budget_exceeded", False)
        return [
            {
                "query": item,
                "category": "general",
                "quantity": 1,
                "prefer_private_label": is_retry,
            }
            for item in raw_items
        ]

    def format_summary(self, total_price: float, state: SilpoAgentState) -> str:
        products_count = len(state.get("mcp_products", []))
        return f"Я сформувала кошик із {products_count} товарів на суму {int(total_price)} гривень."


_PLANNERS: dict[IntentEnum, DomainPlanner] = {
    IntentEnum.PARTY: PartyDomainPlanner(),
    IntentEnum.BUDGET: BudgetDomainPlanner(),
    IntentEnum.OFFICE: OfficeDomainPlanner(),
    IntentEnum.GOURMET: GourmetDomainPlanner(),
}


def get_domain_planner(intent: IntentEnum | None) -> DomainPlanner:
    """Returns domain planner strategy for given intent with general fallback."""
    if intent and intent in _PLANNERS:
        return _PLANNERS[intent]
    return GeneralDomainPlanner()
