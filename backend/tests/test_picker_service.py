"""Phase 2: iterative picker service + node (greedy core, advisor fallback, allowlists)."""

from typing import Any, ClassVar

import pytest
from app.domain.picker import PickerService, is_relevant, violates_hard_constraints
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
        async def choose(
            self, candidates: list[dict[str, Any]], remaining: float, goal: str, query: str = ""
        ) -> int | None:
            raise RuntimeError("llm down")

    service = PickerService(product_service=FakeProductService(_party_catalog()), advisor=ExplodingAdvisor())  # type: ignore[arg-type]
    result = await service.run(_make_state(IntentEnum.PARTY, budget=2000.0))
    assert result["picker_accepted"] >= 3


@pytest.mark.asyncio
async def test_picker_uses_advisor_choice() -> None:
    class FirstChoiceAdvisor:
        def __init__(self) -> None:
            self.calls = 0

        async def choose(
            self, candidates: list[dict[str, Any]], remaining: float, goal: str, query: str = ""
        ) -> int | None:
            self.calls += 1
            return 0

    advisor = FirstChoiceAdvisor()
    service = PickerService(product_service=FakeProductService(_party_catalog()), advisor=advisor)  # type: ignore[arg-type]
    result = await service.run(_make_state(IntentEnum.PARTY, budget=2000.0))
    assert advisor.calls > 0
    assert result["picker_accepted"] >= 3


@pytest.mark.asyncio
async def test_picker_advisor_receives_original_query() -> None:
    class RecordingAdvisor:
        def __init__(self) -> None:
            self.seen: list[str] = []

        async def choose(
            self, candidates: list[dict[str, Any]], remaining: float, goal: str, query: str = ""
        ) -> int | None:
            self.seen.append(query)
            return 0

    advisor = RecordingAdvisor()
    service = PickerService(product_service=FakeProductService(_party_catalog()), advisor=advisor)  # type: ignore[arg-type]
    await service.run(_make_state(IntentEnum.PARTY, budget=2000.0, people_count=1))
    assert advisor.seen
    assert advisor.seen[0] == "Ошийник свинячий"
    assert all(query for query in advisor.seen)


@pytest.mark.asyncio
async def test_picker_advisor_veto_rejects_candidate() -> None:
    from app.services.gemini_service import ADVISOR_VETO

    class VetoAdvisor:
        async def choose(
            self, candidates: list[dict[str, Any]], remaining: float, goal: str, query: str = ""
        ) -> int | None:
            return ADVISOR_VETO

    service = PickerService(product_service=FakeProductService(_party_catalog()), advisor=VetoAdvisor())  # type: ignore[arg-type]
    result = await service.run(_make_state(IntentEnum.PARTY, budget=5000.0, people_count=1))
    assert result["picker_accepted"] == 0
    assert len(result["unfulfilled_requests"]) > 0
    assert any(entry.get("status") == "advisor_veto" for entry in result["picker_trace"])


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


def _mismatch_catalog() -> dict[str, dict[str, Any]]:
    return {
        "вугілля деревне": {
            "id": "t1",
            "productId": "t1",
            "title": "Щітка зубна Colgate «Зиг Заг» деревне вугілля",
            "price": 66.49,
            "is_private_label": False,
            "category": "accessories",
        },
    }


def _bad_filler_catalog() -> dict[str, dict[str, Any]]:
    catalog = dict(_party_catalog())
    catalog["хліб український"] = {
        "id": "f-bad",
        "productId": "f-bad",
        "title": "Крем-сир Philadelphia Оригінальний 61%",
        "price": 219.0,
        "is_private_label": False,
        "category": "bakery",
    }
    return catalog


def test_is_relevant_accepts_matching_charcoal() -> None:
    relevant, _ = is_relevant("Вугілля деревне", "Вугілля деревне Премія 2.5 кг")
    assert relevant is True


def test_is_relevant_rejects_toothbrush_for_charcoal() -> None:
    relevant, reason = is_relevant("Вугілля деревне", "Щітка зубна Colgate «Зиг Заг» деревне вугілля")
    assert relevant is False
    assert reason


def test_is_relevant_rejects_pork_for_chicken() -> None:
    relevant, _ = is_relevant("Курка для гриля", "Ошийник свинячий")
    assert relevant is False


def test_is_relevant_rejects_alcoholic_for_non_alcoholic() -> None:
    relevant, _ = is_relevant("Пиво безалкогольне", "Віскі Jameson")
    assert relevant is False
    relevant, _ = is_relevant("Вино безалкогольне", "Вино червоне сухе Chianti")
    assert relevant is False


def test_is_relevant_accepts_matching_titles() -> None:
    assert is_relevant("Ошийник свинячий", "Ошийник свинячий")[0] is True
    assert is_relevant("Печериці", "Печериці свіжі 500 г")[0] is True


def test_is_relevant_rejects_grill_vegetables_for_chicken_query() -> None:
    relevant, _ = is_relevant("Курка для гриля", "Овочі для гриля")
    assert relevant is False


def test_is_relevant_accepts_non_alcoholic_match() -> None:
    relevant, _ = is_relevant("Пиво безалкогольне", "Пиво безалкогольне Kronenbourg 0.0%")
    assert relevant is True


def test_is_relevant_accepts_chicken_synonym() -> None:
    relevant, _ = is_relevant("Курка", "Філе куряче охолоджене")
    assert relevant is True


def test_is_relevant_accepts_tomato_synonym() -> None:
    relevant, _ = is_relevant("помідори", "Томат")
    assert relevant is True
    relevant, _ = is_relevant("Томати свіжі", "Помідор червоний")
    assert relevant is True


def test_is_relevant_accepts_short_stem_plural() -> None:
    relevant, _ = is_relevant("Сири крафтові", "Сир ЛТ Мукко Бринза з пажитником 36,2%")
    assert relevant is True


def test_is_relevant_short_tokens_still_need_prefix_or_match() -> None:
    relevant, _ = is_relevant("Рис", "Риба свіжа")
    assert relevant is False


@pytest.mark.asyncio
async def test_picker_rejects_toothbrush_for_charcoal_query() -> None:
    service = PickerService(product_service=FakeProductService(_mismatch_catalog()))
    result = await service.run(_make_state(IntentEnum.PARTY, budget=2000.0, people_count=1))
    titles = [str(p.get("title", "")) for p in result["mcp_products"]]
    assert not any("Щітка" in title for title in titles)
    assert "Вугілля деревне" in result["unfulfilled_requests"]
    assert any(entry.get("status") == "rejected_irrelevant" for entry in result["picker_trace"])


@pytest.mark.asyncio
async def test_picker_rejects_irrelevant_filler() -> None:
    service = PickerService(product_service=FakeProductService(_bad_filler_catalog()))
    result = await service.run(_make_state(IntentEnum.PARTY, budget=2000.0, people_count=1))
    titles = [str(p.get("title", "")) for p in result["mcp_products"]]
    assert "Крем-сир Philadelphia Оригінальний 61%" not in titles
    assert any(entry.get("status") == "rejected_irrelevant" for entry in result["picker_trace"])


def _grill_catalog() -> dict[str, dict[str, Any]]:
    return {
        "курка для гриля": {
            "id": "c1",
            "productId": "c1",
            "title": "Куряче філе для гриля",
            "price": 180.0,
            "is_private_label": False,
            "category": "meat",
        },
        "печериці": {
            "id": "m1",
            "productId": "m1",
            "title": "Печериці свіжі 500 г",
            "price": 65.0,
            "is_private_label": False,
            "category": "vegetables",
        },
        "овочі для гриля": {
            "id": "v1",
            "productId": "v1",
            "title": "Овочі для гриля",
            "price": 95.0,
            "is_private_label": False,
            "category": "vegetables",
        },
    }


class MappingFormulator:
    """Test double returning a fixed goal-derived seed regardless of fallback."""

    def __init__(self, seed: list[dict[str, Any]]) -> None:
        self._seed = seed
        self.goals: list[str] = []

    async def formulate(self, goal: str, fallback_seed: list[dict[str, Any]]) -> list[dict[str, Any]]:
        self.goals.append(goal)
        return self._seed


class RejectPorkJudge:
    """Test double rejecting pork titles with a chicken reformulation."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def judge(self, query: str, candidate: dict[str, Any], goal: str) -> dict[str, Any]:
        title = str(candidate.get("title", ""))
        self.calls.append((query, title))
        if "свин" in title.lower() or "ошийник" in title.lower():
            return {"verdict": "reject", "reason": "pork instead of chicken", "suggested_query": "Курка для гриля"}
        return {"verdict": "accept", "reason": "", "suggested_query": None}


class ExplodingJudge:
    async def judge(self, query: str, candidate: dict[str, Any], goal: str) -> dict[str, Any]:
        raise RuntimeError("llm down")


class ExplodingFormulator:
    async def formulate(self, goal: str, fallback_seed: list[dict[str, Any]]) -> list[dict[str, Any]]:
        raise RuntimeError("llm down")


@pytest.mark.asyncio
async def test_picker_uses_formulated_queries_for_grill_request() -> None:
    seed = [
        {"query": "Курка для гриля", "category": "meat", "quantity": 2, "prefer_private_label": False},
        {"query": "Печериці", "category": "vegetables", "quantity": 1, "prefer_private_label": False},
        {"query": "Овочі для гриля", "category": "vegetables", "quantity": 2, "prefer_private_label": False},
    ]
    formulator = MappingFormulator(seed)
    service = PickerService(product_service=FakeProductService(_grill_catalog()), query_formulator=formulator)
    result = await service.run(
        _make_state(
            IntentEnum.PARTY,
            budget=5000.0,
            people_count=5,
            user_text="Збери друзів на гриль: курка, печериці та овочі",
            raw_item_requests=["курка", "печериці", "овочі"],
        )
    )
    titles = [str(p.get("title", "")) for p in result["mcp_products"]]
    assert any("Куряче" in title for title in titles)
    assert any("Печериці" in title for title in titles)
    assert not any("Ошийник" in title for title in titles)
    assert len(formulator.goals) == 1
    assert "курка" in formulator.goals[0].lower()


@pytest.mark.asyncio
async def test_picker_skips_formulation_for_meal_plan_seed() -> None:
    decoy = [
        {"query": "Ошийник свинячий", "category": "meat", "quantity": 2, "prefer_private_label": False},
    ]
    formulator = MappingFormulator(decoy)
    service = PickerService(product_service=FakeProductService(_grill_catalog()), query_formulator=formulator)
    meal_seed = [
        {"query": "Курка для гриля", "category": "meat", "quantity": 2, "prefer_private_label": False},
        {"query": "Печериці", "category": "vegetables", "quantity": 1, "prefer_private_label": False},
    ]
    result = await service.run(
        _make_state(
            IntentEnum.BUDGET,
            budget=2000.0,
            people_count=2,
            calculated_items=meal_seed,
            meal_plan={"days": [{"day": "День 1", "dishes": ["Курка-гриль"]}], "shopping_seed": meal_seed},
        )
    )
    assert formulator.goals == []
    titles = [str(p.get("title", "")) for p in result["mcp_products"]]
    assert any("Куряче" in title for title in titles)
    assert not any("Ошийник" in title for title in titles)


@pytest.mark.asyncio
async def test_picker_ignores_stale_meal_plan_seed_for_non_budget() -> None:
    decoy = [
        {"query": "Курка для гриля", "category": "meat", "quantity": 2, "prefer_private_label": False},
        {"query": "Печериці", "category": "vegetables", "quantity": 1, "prefer_private_label": False},
    ]
    formulator = MappingFormulator(decoy)
    service = PickerService(product_service=FakeProductService(_grill_catalog()), query_formulator=formulator)
    stale_seed = [
        {"query": "Хек свіжоморожений", "category": "meat", "quantity": 2, "prefer_private_label": False},
    ]
    result = await service.run(
        _make_state(
            IntentEnum.PARTY,
            budget=5000.0,
            people_count=5,
            calculated_items=stale_seed,
            meal_plan={"days": [{"day": "День 1", "dishes": ["Хек з гречкою"]}], "shopping_seed": stale_seed},
        )
    )
    assert len(formulator.goals) == 1
    titles = [str(p.get("title", "")) for p in result["mcp_products"]]
    assert any("Куряче" in title for title in titles)
    assert not any("Хек" in title for title in titles)


@pytest.mark.asyncio
async def test_picker_judge_rejects_pork_and_researches_chicken() -> None:
    catalog = dict(_party_catalog())
    catalog["курка для гриля"] = {
        "id": "c1",
        "productId": "c1",
        "title": "Куряче філе для гриля",
        "price": 180.0,
        "is_private_label": False,
        "category": "meat",
    }
    judge = RejectPorkJudge()
    service = PickerService(product_service=FakeProductService(catalog), judge=judge)
    result = await service.run(_make_state(IntentEnum.PARTY, budget=5000.0, people_count=5))
    titles = [str(p.get("title", "")) for p in result["mcp_products"]]
    assert not any("Ошийник" in title for title in titles)
    assert any("Куряче" in title for title in titles)
    assert any(entry.get("status") == "llm_rejected" for entry in result["picker_trace"])
    assert any(entry.get("status") == "llm_reformulated" for entry in result["picker_trace"])
    assert judge.calls


@pytest.mark.asyncio
async def test_picker_falls_back_to_greedy_when_judge_fails() -> None:
    service = PickerService(product_service=FakeProductService(_party_catalog()), judge=ExplodingJudge())
    result = await service.run(_make_state(IntentEnum.PARTY, budget=2000.0))
    assert result["picker_accepted"] >= 3


@pytest.mark.asyncio
async def test_picker_falls_back_to_planner_seed_when_formulator_fails() -> None:
    service = PickerService(
        product_service=FakeProductService(_party_catalog()), query_formulator=ExplodingFormulator()
    )
    result = await service.run(_make_state(IntentEnum.PARTY, budget=2000.0))
    assert result["picker_accepted"] >= 3
    assert result["is_requirements_met"] is True


@pytest.mark.asyncio
async def test_picker_default_path_makes_no_llm_calls(monkeypatch) -> None:
    from app.services import gemini_service

    async def _boom(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("must not be called")

    monkeypatch.setattr(gemini_service, "formulate_picker_queries", _boom)
    monkeypatch.setattr(gemini_service, "judge_picker_candidate", _boom)
    service = PickerService(product_service=FakeProductService(_party_catalog()))
    result = await service.run(_make_state(IntentEnum.PARTY, budget=2000.0))
    assert result["picker_accepted"] >= 3


class PromoFake(FakeProductService):
    """Test double serving a fixed promo list on top of the search catalog."""

    def __init__(self, catalog: dict[str, dict[str, Any]], promos: list[dict[str, Any]]) -> None:
        super().__init__(catalog)
        self._promos = promos

    async def fetch_promo_products(
        self, context: dict[str, str] | None, max_price: float | None = None, limit: int = 10
    ) -> list[dict[str, Any]]:
        self.calls.append(("fetch_promo_products", max_price))
        return [dict(promo) for promo in self._promos]


def _promo_mix() -> list[dict[str, Any]]:
    return [
        {
            "id": "w1",
            "productId": "w1",
            "title": "Віскі Jameson",
            "price": 629.0,
            "is_private_label": False,
            "quantity": 1,
            "category": "promo",
        },
        {
            "id": "t1",
            "productId": "t1",
            "title": "Тунець стейк свіжоморожений",
            "price": 399.0,
            "is_private_label": False,
            "quantity": 1,
            "category": "promo",
        },
        {
            "id": "w2",
            "productId": "w2",
            "title": "Вода мінеральна акційна",
            "price": 20.0,
            "is_private_label": False,
            "quantity": 1,
            "category": "promo",
        },
    ]


class RejectFishJudge:
    """Test double rejecting fish promos while accepting everything else."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def judge(self, query: str, candidate: dict[str, Any], goal: str) -> dict[str, Any]:
        title = str(candidate.get("title", ""))
        self.calls.append((query, title))
        if "тунец" in title.lower() or "тунець" in title.lower():
            return {"verdict": "reject", "reason": "fish not requested", "suggested_query": None}
        return {"verdict": "accept", "reason": "", "suggested_query": None}


class RejectMarinatedJudge:
    """Test double rejecting marinated mushrooms with a fresh reformulation."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def judge(self, query: str, candidate: dict[str, Any], goal: str) -> dict[str, Any]:
        title = str(candidate.get("title", ""))
        self.calls.append((query, title))
        if "маринован" in title.lower():
            return {"verdict": "reject", "reason": "wanted fresh, not marinated", "suggested_query": "Печериці свіжі"}
        return {"verdict": "accept", "reason": "", "suggested_query": None}


def test_violates_hard_constraints_blocks_alcohol_for_non_alcoholic_goal() -> None:
    violated, reason = violates_hard_constraints("Віскі Jameson", "request=хочу безалкогольне пиво")
    assert violated is True
    assert reason


def test_violates_hard_constraints_allows_matching_non_alcoholic_title() -> None:
    assert violates_hard_constraints("Пиво Stella Artois світле безалкогольне", "request=безалкогольне")[0] is False
    assert violates_hard_constraints("Виноград кишмиш", "request=безалкогольне")[0] is False


def test_violates_hard_constraints_ignores_alcohol_without_goal_demand() -> None:
    assert violates_hard_constraints("Віскі Jameson", "request=вечірка з друзями")[0] is False


@pytest.mark.asyncio
async def test_picker_rejects_whiskey_promo_under_non_alcoholic_goal() -> None:
    catalog = dict(_party_catalog())
    catalog["пиво безалкогольне"] = {
        "id": "b1",
        "productId": "b1",
        "title": "Пиво безалкогольне 0.0%",
        "price": 120.0,
        "is_private_label": False,
        "category": "drinks",
    }
    catalog["курка для гриля"] = {
        "id": "c1",
        "productId": "c1",
        "title": "Куряче філе для гриля",
        "price": 180.0,
        "is_private_label": False,
        "category": "meat",
    }
    catalog["вода"] = {
        "id": "d1",
        "productId": "d1",
        "title": "Вода",
        "price": 22.0,
        "is_private_label": False,
        "category": "drinks",
    }
    service = PickerService(product_service=PromoFake(catalog, _promo_mix()))
    result = await service.run(
        _make_state(
            IntentEnum.PARTY,
            budget=5000.0,
            people_count=1,
            user_text="хочу безалкогольне пиво і воду",
            raw_item_requests=["пиво безалкогольне", "вода"],
        )
    )
    titles = [str(p.get("title", "")) for p in result["mcp_products"]]
    assert not any("Jameson" in title for title in titles)
    assert any("Вода мінеральна акційна" in title for title in titles)
    assert any(entry.get("status") == "rejected_constraint" for entry in result["picker_trace"])


@pytest.mark.asyncio
async def test_picker_judge_rejects_fish_promo() -> None:
    service = PickerService(product_service=PromoFake(_party_catalog(), _promo_mix()), judge=RejectFishJudge())
    result = await service.run(_make_state(IntentEnum.PARTY, budget=5000.0, people_count=1))
    titles = [str(p.get("title", "")) for p in result["mcp_products"]]
    assert not any("Тунець" in title for title in titles)
    assert any("Вода мінеральна акційна" in title for title in titles)
    assert any(entry.get("status") == "llm_rejected" for entry in result["picker_trace"])


@pytest.mark.asyncio
async def test_picker_judge_reformulates_marinated_mushrooms_to_fresh() -> None:
    catalog = {
        "печериці": {
            "id": "m1",
            "productId": "m1",
            "title": "Печериці мариновані",
            "price": 109.0,
            "is_private_label": False,
            "category": "vegetables",
        },
        "печериці свіжі": {
            "id": "m2",
            "productId": "m2",
            "title": "Печериці свіжі 400 г",
            "price": 85.0,
            "is_private_label": False,
            "category": "vegetables",
        },
    }
    seed = [{"query": "Печериці", "category": "vegetables", "quantity": 1, "prefer_private_label": False}]
    judge = RejectMarinatedJudge()
    service = PickerService(
        product_service=FakeProductService(catalog), query_formulator=MappingFormulator(seed), judge=judge
    )
    result = await service.run(_make_state(IntentEnum.PARTY, budget=2000.0, people_count=1))
    titles = [str(p.get("title", "")) for p in result["mcp_products"]]
    assert any("Печериці свіжі" in title for title in titles)
    assert not any("мариновані" in title for title in titles)
    assert any(entry.get("status") == "llm_reformulated" for entry in result["picker_trace"])
    assert len(judge.calls) == 1


@pytest.mark.asyncio
async def test_picker_prefers_calculated_items_seed() -> None:
    items = [
        {"query": "Курка для гриля", "category": "meat", "quantity": 2, "dish": "Курка-гриль"},
        {"query": "Печериці свіжі", "category": "vegetables", "quantity": 1, "dish": "Печериці на грилі"},
    ]
    catalog = {
        "курка для гриля": {
            "id": "c1",
            "productId": "c1",
            "title": "Куряче філе для гриля",
            "price": 180.0,
            "is_private_label": False,
            "category": "meat",
        },
        "печериці свіжі": {
            "id": "m2",
            "productId": "m2",
            "title": "Печериці свіжі 400 г",
            "price": 85.0,
            "is_private_label": False,
            "category": "vegetables",
        },
    }
    service = PickerService(product_service=FakeProductService(catalog))
    result = await service.run(_make_state(IntentEnum.PARTY, budget=5000.0, people_count=5, calculated_items=items))
    titles = [str(p.get("title", "")) for p in result["mcp_products"]]
    assert any("Куряче" in title for title in titles)
    assert any("Печериці свіжі" in title for title in titles)
    assert not any("Ошийник" in title for title in titles)


@pytest.mark.asyncio
async def test_picker_tops_up_core_quantities_into_budget_band() -> None:
    service = PickerService(product_service=FakeProductService(_party_catalog()))
    result = await service.run(_make_state(IntentEnum.PARTY, budget=3000.0, people_count=5))
    total = sum(float(p["price"]) * int(p["quantity"]) for p in result["mcp_products"])
    assert 2100.0 <= total <= 3000.0
    assert any(entry.get("status") == "topped_up" for entry in result["picker_trace"])


def test_violates_hard_constraints_blocks_reusable_cup_for_disposable_goal() -> None:
    violated, reason = violates_hard_constraints(
        "Термочашка Eat&Drink 500 мл", "request=одноразові стаканчики для пікніка"
    )
    assert violated is True
    assert reason


def test_violates_hard_constraints_allows_disposable_cups() -> None:
    assert (
        violates_hard_constraints("Стаканчики паперові одноразові 50 шт", "request=одноразові стаканчики")[0] is False
    )


def test_violates_hard_constraints_ignores_cups_without_goal_demand() -> None:
    assert violates_hard_constraints("Термочашка Eat&Drink 500 мл", "request=пікнік")[0] is False


@pytest.mark.asyncio
async def test_picker_rejects_reusable_cup_promo_for_picnic() -> None:
    catalog = dict(_party_catalog())
    catalog["одноразові стаканчики"] = {
        "id": "s1",
        "productId": "s1",
        "title": "Стаканчики паперові одноразові 50 шт",
        "price": 45.0,
        "is_private_label": False,
        "category": "accessories",
    }
    catalog["курка для гриля"] = {
        "id": "c1",
        "productId": "c1",
        "title": "Куряче філе для гриля",
        "price": 180.0,
        "is_private_label": False,
        "category": "meat",
    }
    catalog["вода"] = {
        "id": "d1",
        "productId": "d1",
        "title": "Вода",
        "price": 22.0,
        "is_private_label": False,
        "category": "drinks",
    }
    promos = [
        {
            "id": "c1",
            "productId": "c1",
            "title": "Термочашка Eat&Drink 500 мл",
            "price": 199.0,
            "is_private_label": False,
            "quantity": 1,
            "category": "promo",
        },
        {
            "id": "w2",
            "productId": "w2",
            "title": "Вода мінеральна акційна",
            "price": 20.0,
            "is_private_label": False,
            "quantity": 1,
            "category": "promo",
        },
    ]
    service = PickerService(product_service=PromoFake(catalog, promos))
    result = await service.run(
        _make_state(
            IntentEnum.PARTY,
            budget=5000.0,
            people_count=1,
            user_text="пікнік, потрібні одноразові стаканчики",
            raw_item_requests=["одноразові стаканчики", "вода"],
        )
    )
    titles = [str(p.get("title", "")) for p in result["mcp_products"]]
    assert not any("Термочашка" in title for title in titles)
    assert any("Вода мінеральна акційна" in title for title in titles)
    assert any(entry.get("status") == "rejected_constraint" for entry in result["picker_trace"])
