"""Reproduces weekly cart failure: fish/veg/cereal request yields 38x manna + hake."""

from typing import ClassVar

import pytest
from app.domain.picker import PickerService, is_relevant
from app.domain.planners import BudgetDomainPlanner
from app.enums import IntentEnum
from app.intent_schema import extract_intent_fallback
from app.state import SilpoAgentState


def _make_state(intent: IntentEnum, **overrides) -> SilpoAgentState:
    base: SilpoAgentState = {
        "intent": intent,
        "budget": 2000.0,
        "people_count": 2,
        "dietary_restrictions": [],
        "raw_item_requests": [],
        "calculated_items": [],
        "mcp_products": [],
        "total_price": 0.0,
        "attempts": 0,
        "max_attempts": 3,
        "is_budget_exceeded": False,
        "messages": [],
    }
    base.update(overrides)  # type: ignore[typeddict-item]
    return base


def test_weekly_query_extracts_fish_veg_cereal() -> None:
    parsed = extract_intent_fallback(
        "Склади мені, будь ласка, продукти на тиждень до 2000 гривень з рибою, овочами і якоюсь крупою"
    )
    lowered = [item.lower() for item in parsed.raw_item_requests]
    assert any("риб" in item or "хек" in item for item in lowered), f"got {lowered}"
    assert any("овоч" in item for item in lowered), f"got {lowered}"
    assert any("крупа" in item or "греч" in item or "рис" in item for item in lowered), f"got {lowered}"


def test_budget_planner_honors_fish_veg_cereal_requests() -> None:
    planner = BudgetDomainPlanner()
    state = _make_state(IntentEnum.BUDGET, people_count=2, raw_item_requests=["риба", "овочі", "крупа"])
    items = planner.plan(state)
    queries = [str(item["query"]).lower() for item in items]
    assert any("риб" in q or "хек" in q for q in queries), f"got {queries}"
    assert any("овоч" in q or "картопл" in q for q in queries), f"got {queries}"
    assert any("крупа" in q or "греч" in q or "рис" in q for q in queries), f"got {queries}"
    assert not any("курка" in q for q in queries), f"fish request must not yield chicken: {queries}"


def test_grechana_rejects_manna() -> None:
    relevant, _ = is_relevant("Крупа гречана", "Крупа Такі Справи манна 800 г")
    assert relevant is False


def test_ryba_accepts_hek() -> None:
    relevant, _ = is_relevant("Риба", "Хек північноамериканський свіжоморожений")
    assert relevant is True


class _FakeProducts:
    CTX: ClassVar[dict[str, str]] = {
        "branch_id": "bran-1",
        "delivery_type": "SelfPickup",
        "timeslot_start": "2026-09-06T10:00:00",
        "timeslot_end": "2026-09-06T12:00:00",
    }

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def resolve_shopping_context(self, delivery_address: str | None) -> dict[str, str]:
        return dict(self.CTX)

    async def search_one(
        self, query, quantity=1, prefer_private_label=False, max_price=None, category=None, context=None
    ):
        self.calls.append(query)
        catalog = {
            "риба": {"id": "f1", "productId": "f1", "title": "Хек свіжоморожений", "price": 294.0},
            "овочі": {"id": "v1", "productId": "v1", "title": "Овочі сезонні", "price": 85.0},
            "крупа": {"id": "g1", "productId": "g1", "title": "Крупа гречана", "price": 36.99},
        }
        key = query.strip().lower()
        template = None
        for marker, prod in catalog.items():
            if marker in key:
                template = prod
                break
        if template is None:
            return None
        if max_price is not None and template["price"] * quantity > max_price:
            return None
        return {**template, "quantity": quantity, "category": category or "general"}

    async def fetch_promo_products(self, context=None, max_price=None, limit=10):
        return []

    async def fetch_similar(self, slug, context):
        return []

    async def fetch_product_details(self, slug, context):
        return None

    async def fetch_replacements(self, ref_product, context):
        return []


@pytest.mark.asyncio
async def test_picker_top_up_caps_per_sku() -> None:
    service = PickerService(product_service=_FakeProducts())  # type: ignore[arg-type]
    state = _make_state(
        IntentEnum.BUDGET,
        budget=2000.0,
        people_count=2,
        calculated_items=[
            {"query": "Риба", "category": "meat", "quantity": 1, "prefer_private_label": True},
            {"query": "Овочі", "category": "vegetables", "quantity": 1, "prefer_private_label": True},
            {"query": "Крупа", "category": "grocery", "quantity": 1, "prefer_private_label": True},
        ],
    )
    result = await service.run(state)
    quantities = [int(p["quantity"]) for p in result["mcp_products"]]
    assert max(quantities) <= 6, f"top-up must not inflate single SKU: {result['mcp_products']}"
    assert len(result["mcp_products"]) >= 3, f"weekly cart must stay diverse: {result['mcp_products']}"
