"""Phase 2: iterative picker service + node (greedy core, advisor fallback, allowlists)."""

from typing import Any, ClassVar

import pytest
from app.domain.picker import PickerService
from app.enums import IntentEnum
from app.state import SilpoAgentState


class FakeProductService:
    CTX: ClassVar[dict[str, str]] = {
        "branch_id": "bran-1",
        "delivery_type": "SelfPickup",
        "timeslot_start": "2026-09-06T10:00:00",
        "timeslot_end": "2026-09-06T12:00:00",
    }

    def __init__(self, catalog: dict[str, dict[str, Any]]) -> None:
        self.catalog = catalog
        self.calls: list[tuple[str, Any]] = []

    async def resolve_shopping_context(self, delivery_address: str | None) -> dict[str, str]:
        self.calls.append(("resolve_shopping_context", delivery_address))
        return dict(self.CTX)

    async def search_one(
        self,
        query: str,
        quantity: int = 1,
        prefer_private_label: bool = False,
        max_price: float | None = None,
        category: str | None = None,
        context: dict[str, str] | None = None,
    ) -> dict[str, Any] | None:
        self.calls.append(("search_one", query))
        template = self.catalog.get(query.lower())
        if template is None:
            return None
        line_total = float(template["price"]) * quantity
        if max_price is not None and line_total > max_price:
            return None
        return {**template, "quantity": quantity, "category": category or template.get("category", "general")}

    async def fetch_promo_products(
        self, context: dict[str, str] | None, max_price: float | None = None, limit: int = 10
    ) -> list[dict[str, Any]]:
        self.calls.append(("fetch_promo_products", max_price))
        return []

    async def fetch_similar(self, slug: str, context: dict[str, str] | None) -> list[dict[str, Any]]:
        self.calls.append(("fetch_similar", slug))
        return []

    async def fetch_product_details(self, slug: str, context: dict[str, str] | None) -> dict[str, Any] | None:
        self.calls.append(("fetch_product_details", slug))
        return None

    async def fetch_replacements(
        self, ref_product: dict[str, Any], context: dict[str, str] | None
    ) -> list[dict[str, Any]]:
        self.calls.append(("fetch_replacements", ref_product.get("productId")))
        return []


def _party_catalog() -> dict[str, dict[str, Any]]:
    return {
        "ошийник свинячий": {
            "id": "m1",
            "productId": "m1",
            "title": "Ошийник",
            "price": 240.0,
            "is_private_label": False,
            "category": "meat",
        },
        "овочі для гриля премія": {
            "id": "v1",
            "productId": "v1",
            "title": "Овочі",
            "price": 85.0,
            "is_private_label": True,
            "category": "vegetables",
        },
        "вода мінеральна": {
            "id": "d1",
            "productId": "d1",
            "title": "Вода",
            "price": 22.0,
            "is_private_label": False,
            "category": "drinks",
        },
        "вугілля деревне": {
            "id": "a1",
            "productId": "a1",
            "title": "Вугілля",
            "price": 120.0,
            "is_private_label": True,
            "category": "accessories",
        },
        "вода питна премія": {
            "id": "f1",
            "productId": "f1",
            "title": "Вода Премія",
            "price": 15.0,
            "is_private_label": True,
            "category": "drinks",
        },
        "хліб український": {
            "id": "f2",
            "productId": "f2",
            "title": "Хліб",
            "price": 28.0,
            "is_private_label": False,
            "category": "bakery",
        },
        "ціна тижня акційні": {
            "id": "f3",
            "productId": "f3",
            "title": "Акція",
            "price": 10.0,
            "is_private_label": True,
            "category": "promo",
        },
    }


def _make_state(intent: IntentEnum, **overrides: Any) -> SilpoAgentState:
    base: SilpoAgentState = {
        "intent": intent,
        "budget": 1000.0,
        "people_count": 4,
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


@pytest.mark.asyncio
async def test_picker_accepts_seed_within_budget() -> None:
    service = PickerService(product_service=FakeProductService(_party_catalog()))
    result = await service.run(_make_state(IntentEnum.PARTY, budget=2000.0))
    assert result["picker_accepted"] >= 3
    assert result["is_requirements_met"] is True
    assert result["unfulfilled_requests"] == []
    total = sum(p["price"] * p["quantity"] for p in result["mcp_products"])
    assert total <= 2000.0
    assert result["remaining_budget"] == pytest.approx(2000.0 - total)
    assert len(result["picker_trace"]) > 0
    assert result["shopping_context"] == FakeProductService.CTX


@pytest.mark.asyncio
async def test_picker_rejects_over_budget_seed_as_unfulfilled() -> None:
    service = PickerService(product_service=FakeProductService(_party_catalog()))
    result = await service.run(_make_state(IntentEnum.PARTY, budget=50.0, people_count=8))
    assert result["picker_accepted"] >= 0
    assert len(result["unfulfilled_requests"]) > 0
    total = sum(p["price"] * p["quantity"] for p in result["mcp_products"])
    assert total <= 50.0


@pytest.mark.asyncio
async def test_picker_adds_fillers_on_leftover_budget() -> None:
    service = PickerService(product_service=FakeProductService(_party_catalog()))
    result = await service.run(_make_state(IntentEnum.PARTY, budget=2000.0, people_count=1))
    titles = [p["title"] for p in result["mcp_products"]]
    assert any(t in ("Вода Премія", "Хліб", "Акція") for t in titles)


@pytest.mark.asyncio
async def test_picker_respects_tool_allowlist() -> None:
    fake = FakeProductService(_party_catalog())
    service = PickerService(product_service=fake)
    await service.run(_make_state(IntentEnum.BUDGET, budget=500.0))
    tools_used = {call[0] for call in fake.calls}
    assert "fetch_product_details" not in tools_used
    assert "fetch_similar" not in tools_used


@pytest.mark.asyncio
async def test_picker_respects_max_steps() -> None:
    fake = FakeProductService(_party_catalog())
    service = PickerService(product_service=fake, max_steps=1)
    result = await service.run(_make_state(IntentEnum.PARTY, budget=5000.0))
    assert result["picker_accepted"] <= 2  # 1 seed + possible fillers share the step budget
    assert len(result["unfulfilled_requests"]) > 0


@pytest.mark.asyncio
async def test_picker_falls_back_to_greedy_when_advisor_fails() -> None:
    class ExplodingAdvisor:
        async def choose(self, candidates: list[dict[str, Any]], remaining: float, goal: str) -> int | None:
            raise RuntimeError("llm down")

    service = PickerService(product_service=FakeProductService(_party_catalog()), advisor=ExplodingAdvisor())  # type: ignore[arg-type]
    result = await service.run(_make_state(IntentEnum.PARTY, budget=2000.0))
    assert result["picker_accepted"] >= 3


@pytest.mark.asyncio
async def test_picker_uses_advisor_choice() -> None:
    class FirstChoiceAdvisor:
        def __init__(self) -> None:
            self.calls = 0

        async def choose(self, candidates: list[dict[str, Any]], remaining: float, goal: str) -> int | None:
            self.calls += 1
            return 0

    advisor = FirstChoiceAdvisor()
    service = PickerService(product_service=FakeProductService(_party_catalog()), advisor=advisor)  # type: ignore[arg-type]
    result = await service.run(_make_state(IntentEnum.PARTY, budget=2000.0))
    assert advisor.calls > 0
    assert result["picker_accepted"] >= 3


@pytest.mark.asyncio
async def test_gourmet_soft_mode_accepts_over_explicit_budget() -> None:
    catalog = {
        "камамбер": {
            "id": "g1",
            "productId": "g1",
            "title": "Камамбер",
            "price": 400.0,
            "is_private_label": False,
            "category": "cheese",
        },
    }

    class GourmetFake(FakeProductService):
        async def search_one(
            self,
            query: str,
            quantity: int = 1,
            prefer_private_label: bool = False,
            max_price: float | None = None,
            category: str | None = None,
            context: dict[str, str] | None = None,
        ) -> dict[str, Any] | None:
            self.calls.append(("search_one", query))
            return {
                "id": "g1",
                "productId": "g1",
                "title": "Камамбер",
                "price": 400.0,
                "is_private_label": False,
                "quantity": quantity,
                "category": category or "cheese",
            }

    service = PickerService(product_service=GourmetFake(catalog))
    result = await service.run(_make_state(IntentEnum.GOURMET, budget=100.0, raw_item_requests=["камамбер"]))
    assert result["picker_accepted"] >= 1


@pytest.mark.asyncio
async def test_picker_retry_keeps_hits_and_retries_only_misses() -> None:
    catalog = dict(_party_catalog())
    del catalog["овочі для гриля премія"]
    fake = FakeProductService(catalog)
    service = PickerService(product_service=fake)
    first = await service.run(_make_state(IntentEnum.PARTY, budget=5000.0, people_count=1))
    assert first["unfulfilled_requests"] == ["Овочі для гриля Премія"]
    before = len([c for c in fake.calls if c[0] == "search_one"])

    retry_state = _make_state(
        IntentEnum.PARTY,
        budget=5000.0,
        people_count=1,
        attempts=1,
        mcp_products=first["mcp_products"],
        unfulfilled_requests=first["unfulfilled_requests"],
    )
    second = await service.run(retry_state)
    retried = [c for c in fake.calls if c[0] == "search_one"][before:]
    assert retried and all(query.split()[0] == "Овочі" for _, query in retried)
    assert second["picker_accepted"] == first["picker_accepted"]
    assert all(p in second["mcp_products"] for p in first["mcp_products"])


@pytest.mark.asyncio
async def test_picker_rebuilds_from_scratch_when_budget_exceeded() -> None:
    fake = FakeProductService(_party_catalog())
    service = PickerService(product_service=fake)
    state = _make_state(
        IntentEnum.PARTY,
        budget=2000.0,
        attempts=1,
        is_budget_exceeded=True,
        mcp_products=[{"id": "old", "title": "old", "price": 1.0, "quantity": 1, "category": "meat"}],
        unfulfilled_requests=["Овочі для гриля Премія"],
    )
    result = await service.run(state)
    assert all(p["id"] != "old" for p in result["mcp_products"])


@pytest.mark.asyncio
async def test_picker_retries_miss_with_simplified_query(monkeypatch) -> None:
    from app.domain import picker as picker_module

    class StubPlanner:
        def plan(self, state):
            return [
                {
                    "query": "Крекери до вина елітні",
                    "category": "snacks",
                    "quantity": 1,
                    "prefer_private_label": False,
                }
            ]

        def budget_mode(self):
            return "hard_fill"

        def tool_allowlist(self):
            return ["search_products"]

        def min_coverage(self):
            return ["snacks"]

        def filler_queries(self):
            return []

        def score(self, candidate, remaining):
            return 1.0

    catalog = {
        "крекери": {
            "id": "c1",
            "productId": "c1",
            "title": "Крекери",
            "price": 30.0,
            "is_private_label": False,
            "category": "snacks",
        }
    }
    monkeypatch.setattr(picker_module, "get_domain_planner", lambda intent: StubPlanner())
    service = PickerService(product_service=FakeProductService(catalog))
    result = await service.run(_make_state(IntentEnum.BUDGET, budget=500.0))
    assert result["picker_accepted"] == 1
    assert result["unfulfilled_requests"] == []


@pytest.mark.asyncio
async def test_picker_forwards_delivery_address_to_context_resolution() -> None:
    fake = FakeProductService(_party_catalog())
    service = PickerService(product_service=fake)
    await service.run(_make_state(IntentEnum.PARTY, budget=2000.0, delivery_address="Київ, вул. Мишуги, 4"))
    assert ("resolve_shopping_context", "Київ, вул. Мишуги, 4") in fake.calls


@pytest.mark.asyncio
async def test_picker_node_returns_tracking_fields(monkeypatch) -> None:
    from app.nodes import picker as picker_module

    fake = FakeProductService(_party_catalog())
    monkeypatch.setattr(picker_module, "mcp_product_service", fake)
    monkeypatch.setattr(picker_module, "_default_advisor", lambda: None)
    result = await picker_module.picker_node(_make_state(IntentEnum.PARTY, budget=2000.0))
    for key in (
        "mcp_products",
        "remaining_budget",
        "unfulfilled_requests",
        "is_requirements_met",
        "picker_trace",
        "picker_accepted",
        "shopping_context",
    ):
        assert key in result
