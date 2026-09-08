"""Nearby-branch retry: assortment misses are re-searched in close branches."""

from typing import Any

import pytest
from app.domain.picker import PickerService
from app.enums import IntentEnum
from app.state import SilpoAgentState

PRIMARY_CTX = {
    "branch_id": "bran-1",
    "delivery_type": "SelfPickup",
    "timeslot_start": "2026-09-06T10:00:00",
    "timeslot_end": "2026-09-06T12:00:00",
}

NEARBY_CTX = {
    "branch_id": "bran-2",
    "delivery_type": "SelfPickup",
    "timeslot_start": "2026-09-06T10:00:00",
    "timeslot_end": "2026-09-06T12:00:00",
    "distance_km": 1.2,
}


class MultiBranchFakeService:
    """Primary branch misses milk; a nearby branch stocks it."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    async def resolve_shopping_context(self, delivery_address: str | None) -> dict[str, str]:
        self.calls.append(("resolve_shopping_context", delivery_address))
        return dict(PRIMARY_CTX)

    async def find_nearby_contexts(
        self, delivery_address: str | None, primary: dict[str, str] | None, limit: int | None = None
    ) -> list[dict[str, Any]]:
        self.calls.append(("find_nearby_contexts", delivery_address))
        return [dict(NEARBY_CTX)]

    def _catalog(self, context: dict[str, str] | None) -> dict[str, dict[str, Any]]:
        if context is not None and context.get("branch_id") == "bran-2":
            return {
                "молоко": {
                    "id": "m2",
                    "productId": "m2",
                    "title": "Молоко",
                    "price": 36.9,
                    "is_private_label": True,
                    "category": "dairy",
                },
            }
        return {
            "хліб": {
                "id": "b1",
                "productId": "b1",
                "title": "Хліб",
                "price": 28.5,
                "is_private_label": False,
                "category": "bakery",
            },
            "крупа гречана": {
                "id": "g1",
                "productId": "g1",
                "title": "Крупа гречана",
                "price": 36.99,
                "is_private_label": True,
                "category": "grocery",
            },
            "курка": {
                "id": "c1",
                "productId": "c1",
                "title": "Курка",
                "price": 180.0,
                "is_private_label": False,
                "category": "meat",
            },
            "пиво": {
                "id": "p1",
                "productId": "p1",
                "title": "Пиво світле",
                "price": 45.0,
                "is_private_label": False,
                "category": "drinks",
            },
        }

    async def search_one(
        self,
        query: str,
        quantity: int = 1,
        prefer_private_label: bool = False,
        max_price: float | None = None,
        category: str | None = None,
        context: dict[str, str] | None = None,
    ) -> dict[str, Any] | None:
        branch = (context or {}).get("branch_id", "bran-1")
        self.calls.append(("search_one", query, branch))
        template = self._catalog(context).get(query.lower())
        if template is None:
            return None
        if max_price is not None and float(template["price"]) * quantity > max_price:
            return None
        return {**template, "quantity": quantity, "category": category or template.get("category", "general")}

    async def fetch_promo_products(
        self, context: dict[str, str] | None, max_price: float | None = None, limit: int = 10
    ) -> list[dict[str, Any]]:
        return []

    async def fetch_similar(self, slug: str, context: dict[str, str] | None) -> list[dict[str, Any]]:
        return []

    async def fetch_product_details(self, slug: str, context: dict[str, str] | None) -> dict[str, Any] | None:
        return None

    async def fetch_replacements(
        self, ref_product: dict[str, Any], context: dict[str, str] | None
    ) -> list[dict[str, Any]]:
        return []


def _make_state(**overrides: Any) -> SilpoAgentState:
    base: SilpoAgentState = {
        "intent": IntentEnum.BUDGET,
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
        "delivery_address": "Київ, вул. Мишуги, 4",
        "messages": [],
    }
    base.update(overrides)  # type: ignore[typeddict-item]
    return base


def _weekly_seed() -> list[dict[str, Any]]:
    return [
        {"query": "Молоко", "category": "dairy", "quantity": 2, "prefer_private_label": True},
        {"query": "Хліб", "category": "bakery", "quantity": 2, "prefer_private_label": True},
        {"query": "Крупа гречана", "category": "grocery", "quantity": 1, "prefer_private_label": True},
        {"query": "Курка", "category": "meat", "quantity": 1, "prefer_private_label": True},
    ]


@pytest.mark.asyncio
async def test_nearby_retry_picks_assortment_miss_from_close_branch() -> None:
    service = PickerService(product_service=MultiBranchFakeService())  # type: ignore[arg-type]
    result = await service.run(_make_state(calculated_items=_weekly_seed()))
    titles = [str(p.get("title", "")) for p in result["mcp_products"]]
    assert "Молоко" in titles
    assert "Молоко" not in result["unfulfilled_requests"]
    nearby_hits = [e for e in result["picker_trace"] if e.get("status") == "accepted_nearby"]
    assert len(nearby_hits) == 1
    assert nearby_hits[0]["branch_id"] == "bran-2"
    assert result["is_requirements_met"] is True


@pytest.mark.asyncio
async def test_nearby_retry_skipped_when_service_has_no_branch_finder() -> None:
    from .test_picker_service import FakeProductService, _party_catalog

    service = PickerService(product_service=FakeProductService(_party_catalog()))
    result = await service.run(_make_state(calculated_items=_weekly_seed(), delivery_address="Київ, вул. Мишуги, 4"))
    assert "Молоко" not in [str(p.get("title", "")) for p in result["mcp_products"]]
    assert "Молоко" in result["unfulfilled_requests"]


@pytest.mark.asyncio
async def test_nearby_retry_respects_step_budget() -> None:
    fake = MultiBranchFakeService()
    service = PickerService(product_service=fake, max_steps=4)  # type: ignore[arg-type]
    result = await service.run(_make_state(calculated_items=_weekly_seed()))
    assert ("find_nearby_contexts", "Київ, вул. Мишуги, 4") not in fake.calls
    assert "Молоко" in result["unfulfilled_requests"]


@pytest.mark.asyncio
async def test_judge_skipped_when_deterministically_irrelevant() -> None:
    """Quota: no LLM judge call for items the deterministic gate already rejects."""

    class RecordingJudge:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        async def judge(self, query: str, candidate: dict[str, Any], goal: str) -> dict[str, Any]:
            self.calls.append((query, str(candidate.get("title", ""))))
            return {"verdict": "accept", "reason": "", "suggested_query": None}

    class PorkCatalogService(MultiBranchFakeService):
        def _catalog(self, context: dict[str, str] | None) -> dict[str, dict[str, Any]]:
            return {
                "курка для гриля": {
                    "id": "c1",
                    "productId": "c1",
                    "title": "Ошийник свинячий",
                    "price": 240.0,
                    "is_private_label": False,
                    "category": "meat",
                },
            }

    judge = RecordingJudge()
    service = PickerService(product_service=PorkCatalogService(), judge=judge)  # type: ignore[arg-type]
    result = await service.run(
        _make_state(
            calculated_items=[
                {"query": "Курка для гриля", "category": "meat", "quantity": 1, "prefer_private_label": False}
            ]
        )
    )
    assert judge.calls == []
    assert result["unfulfilled_requests"] == ["Курка для гриля"]
    assert any(e.get("status") == "rejected_irrelevant" for e in result["picker_trace"])
    assert not any(e.get("status") == "llm_rejected" for e in result["picker_trace"])


@pytest.mark.asyncio
async def test_rejection_info_log_behind_flag(monkeypatch, caplog) -> None:
    import logging

    from app.domain import picker as picker_module

    monkeypatch.setattr(picker_module.settings, "LOG_PICKER_REJECTIONS", True)
    service = PickerService(product_service=MultiBranchFakeService())  # type: ignore[arg-type]
    with caplog.at_level(logging.INFO, logger="app.domain.picker"):
        await service.run(
            _make_state(
                calculated_items=[
                    {"query": "Молоко", "category": "dairy", "quantity": 1, "prefer_private_label": True}
                ],
                delivery_address=None,
            )
        )
    assert "Молоко" in caplog.text


@pytest.mark.asyncio
async def test_nearby_skip_is_logged(caplog) -> None:
    import logging

    service = PickerService(product_service=MultiBranchFakeService())  # type: ignore[arg-type]
    with caplog.at_level(logging.INFO, logger="app.domain.picker"):
        await service.run(
            _make_state(
                user_text="хочу безалкогольне пиво",
                raw_item_requests=["пиво безалкогольне"],
                calculated_items=[
                    {"query": "Пиво", "category": "drinks", "quantity": 1, "prefer_private_label": False}
                ],
            )
        )
    assert "nearby retry skipped" in caplog.text
    assert "no_retryable_misses" in caplog.text


@pytest.mark.asyncio
async def test_find_nearby_contexts_empty_in_mock_mode(monkeypatch) -> None:
    from app.services import mcp_service as mcp_module

    monkeypatch.setattr(mcp_module.settings, "MCP_MOCK_MODE", True)
    result = await mcp_module.MCPProductService().find_nearby_contexts("Київ, вул. Мишуги, 4", dict(PRIMARY_CTX))
    assert result == []


@pytest.mark.asyncio
async def test_find_nearby_contexts_ranks_and_validates_slots(monkeypatch) -> None:
    from app.services import mcp_service as mcp_module

    branches = [
        {"branch_id": "bran-1", "latitude": 50.40, "longitude": 30.62, "is_open": True},
        {"branch_id": "bran-2", "latitude": 50.41, "longitude": 30.63, "is_open": True},
        {"branch_id": "bran-3", "latitude": 50.405, "longitude": 30.625, "is_open": True},
        {"branch_id": "bran-9", "latitude": 51.50, "longitude": 31.50, "is_open": True},
    ]
    slots = {
        "bran-2": [{"startsAt": "2026-09-06T10:00:00", "endsAt": "2026-09-06T12:00:00", "isAvailable": True}],
        "bran-3": [],
    }

    class StubClient:
        async def __aenter__(self) -> "StubClient":  # noqa: PYI034 - test stub, not a typeshed protocol
            return self

        async def __aexit__(self, *args: object) -> bool:
            return False

        async def find_address(self, text: str) -> dict[str, float]:
            return {"latitude": 50.40, "longitude": 30.62}

        async def list_branches(self, limit: int = 500) -> list[dict[str, object]]:
            return branches

        async def get_time_slots(
            self, branch_id: str, delivery_types: list[str] | None = None
        ) -> list[dict[str, object]]:
            return slots.get(branch_id, [])

    monkeypatch.setattr(mcp_module.settings, "MCP_MOCK_MODE", False)
    monkeypatch.setattr(mcp_module.SilpoClient, "for_real_server", staticmethod(lambda: StubClient()))
    result = await mcp_module.MCPProductService().find_nearby_contexts("Київ, вул. Мишуги, 4", dict(PRIMARY_CTX))
    assert [ctx["branch_id"] for ctx in result] == ["bran-2"]
    assert result[0]["timeslot_start"] == "2026-09-06T10:00:00"
    assert result[0]["distance_km"] < 10.0


@pytest.mark.asyncio
async def test_constraint_rejections_are_not_retried_nearby() -> None:
    fake = MultiBranchFakeService()
    service = PickerService(product_service=fake)  # type: ignore[arg-type]
    state = _make_state(
        user_text="хочу безалкогольне пиво",
        raw_item_requests=["пиво безалкогольне"],
        calculated_items=[{"query": "Пиво", "category": "drinks", "quantity": 1, "prefer_private_label": False}],
    )
    await service.run(state)
    assert not [c for c in fake.calls if c[0] == "search_one" and c[2] == "bran-2"]
