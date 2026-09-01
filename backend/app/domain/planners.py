import math
from typing import Any, Protocol

from ..enums import IntentEnum
from ..state import AgentState


class DomainPlanner(Protocol):
    def plan(self, state: AgentState) -> list[dict[str, Any]]:
        """Generates calculated item requests with quantities and preferences."""
        ...

    def format_summary(self, total_price: float, state: AgentState) -> str:
        """Formats Ukrainian summary text for the created cart."""
        ...


class PartyDomainPlanner:
    def plan(self, state: AgentState) -> list[dict[str, Any]]:
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

    def format_summary(self, total_price: float, state: AgentState) -> str:
        people_count = state.get("people_count") or 1
        return (
            f"Я зібрав кошик для пікніка на {people_count} осіб на суму {int(total_price)} гривень."
        )


class BudgetDomainPlanner:
    def plan(self, state: AgentState) -> list[dict[str, Any]]:
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

    def format_summary(self, total_price: float, state: AgentState) -> str:
        products_count = len(state.get("mcp_products", []))
        return f"Я підібрав економний кошик із {products_count} товарів на суму {int(total_price)} гривень."


class GeneralDomainPlanner:
    def plan(self, state: AgentState) -> list[dict[str, Any]]:
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

    def format_summary(self, total_price: float, state: AgentState) -> str:
        products_count = len(state.get("mcp_products", []))
        return f"Я сформував кошик із {products_count} товарів на суму {int(total_price)} гривень."


_PLANNERS: dict[IntentEnum, DomainPlanner] = {
    IntentEnum.PARTY: PartyDomainPlanner(),
    IntentEnum.BUDGET: BudgetDomainPlanner(),
}


def get_domain_planner(intent: IntentEnum | None) -> DomainPlanner:
    """Returns domain planner strategy for given intent with general fallback."""
    if intent and intent in _PLANNERS:
        return _PLANNERS[intent]
    return GeneralDomainPlanner()
