"""Shared iterative picker: greedy policy-driven ReAct loop with an LLM advisor hook."""

import logging
import math
from typing import Any, Protocol

from ..config import settings
from ..services import gemini_service
from ..services.mcp_service import mcp_product_service
from ..state import SilpoAgentState
from .planners import get_domain_planner

logger = logging.getLogger(__name__)


class PickerAdvisor(Protocol):
    async def choose(self, candidates: list[dict[str, Any]], remaining: float, goal: str) -> int | None:
        """Returns the chosen candidate index, or None to abstain (greedy scoring decides)."""
        ...


class GreedyAdvisor:
    async def choose(self, candidates: list[dict[str, Any]], remaining: float, goal: str) -> int | None:
        return None


class GeminiPickerAdvisor:
    async def choose(self, candidates: list[dict[str, Any]], remaining: float, goal: str) -> int | None:
        return await gemini_service.choose_picker_candidate(candidates, remaining, goal)


class PickerService:
    """Iteratively picks priced products until budget/requirements resolve or steps run out."""

    def __init__(
        self,
        product_service: Any | None = None,
        advisor: PickerAdvisor | None = None,
        max_steps: int | None = None,
    ) -> None:
        self._products = product_service if product_service is not None else mcp_product_service
        self._advisor = advisor if advisor is not None else GreedyAdvisor()
        self._max_steps = max_steps if max_steps is not None else settings.MAX_PICKER_STEPS

    async def _choose_index(self, shortlist: list[dict[str, Any]], remaining: float, goal: str) -> int:
        try:
            index = await self._advisor.choose(shortlist, remaining, goal)
        except Exception as exc:  # noqa: BLE001 - advisor failure falls back to greedy
            logger.debug("Picker advisor failed, using greedy fallback: %s", exc)
            return 0
        if index is None or not 0 <= index < len(shortlist):
            return 0
        return index

    async def _enrich_details(
        self,
        product: dict[str, Any],
        allowlist: set[str],
        trace: list[dict[str, Any]],
        context: dict[str, str] | None,
    ) -> dict[str, Any]:
        if "get_product_details" not in allowlist:
            return product
        slug = product.get("slug")
        if not slug:
            return product
        try:
            details = await self._products.fetch_product_details(str(slug), context)
        except Exception as exc:  # noqa: BLE001 - enrichment never blocks picking
            logger.debug("Picker details enrichment failed: %s", exc)
            return product
        if details:
            product = {**product, "details": details}
            trace.append({"tool": "get_product_details", "query": str(slug), "status": "enriched"})
        return product

    async def _substitute(
        self,
        query: str,
        quantity: int,
        ceiling: float | None,
        category: str | None,
        allowlist: set[str],
        trace: list[dict[str, Any]],
        context: dict[str, str] | None,
    ) -> dict[str, Any] | None:
        reference: dict[str, Any] | None = None
        if "search_products" in allowlist:
            try:
                reference = await self._products.search_one(query, quantity, False, None, category, context)
            except Exception as exc:  # noqa: BLE001 - substitution is best-effort
                logger.debug("Picker reference search failed for '%s': %s", query, exc)
        if "get_replacements" in allowlist and ceiling is not None and reference is not None:
            try:
                for candidate in await self._products.fetch_replacements(reference, context):
                    line_total = float(candidate.get("price", 0.0)) * quantity
                    if line_total <= ceiling:
                        candidate = {
                            **candidate,
                            "quantity": quantity,
                            "category": category or candidate.get("category", "general"),
                        }
                        trace.append(
                            {
                                "tool": "get_replacements",
                                "query": query,
                                "status": "substituted",
                                "product_id": candidate.get("id"),
                            }
                        )
                        return candidate
            except Exception as exc:  # noqa: BLE001 - substitution is best-effort
                logger.debug("Picker replacement substitute failed for '%s': %s", query, exc)
        if "get_similar_products" in allowlist and reference is not None and reference.get("slug"):
            try:
                for candidate in await self._products.fetch_similar(str(reference["slug"]), context):
                    line_total = float(candidate.get("price", 0.0)) * quantity
                    if ceiling is None or line_total <= ceiling:
                        candidate = {
                            **candidate,
                            "quantity": quantity,
                            "category": category or candidate.get("category", "general"),
                        }
                        trace.append(
                            {
                                "tool": "get_similar_products",
                                "query": query,
                                "status": "substituted",
                                "product_id": candidate.get("id"),
                            }
                        )
                        return candidate
            except Exception as exc:  # noqa: BLE001 - substitution is best-effort
                logger.debug("Picker similar substitute failed for '%s': %s", query, exc)
        return None

    async def run(self, state: SilpoAgentState) -> dict[str, Any]:
        planner = get_domain_planner(state.get("intent"))
        budget = state.get("budget", 0.0) or 0.0
        hard = planner.budget_mode() == "hard_fill"
        allowlist = set(planner.tool_allowlist())
        remaining = budget if budget > 0 else math.inf
        goal = f"intent={state.get('intent')} budget={budget} people={state.get('people_count')}"

        def ceiling() -> float | None:
            return remaining if hard and budget > 0 else None

        context = state.get("shopping_context") or await self._products.resolve_shopping_context(
            state.get("delivery_address")
        )

        seed = planner.plan(state)
        accepted: list[dict[str, Any]] = []
        trace: list[dict[str, Any]] = []
        unfulfilled: list[str] = []
        steps = 0

        # On retry without over-budget, keep verified picks and only re-attempt
        # previous misses instead of re-searching everything identically.
        if not state.get("is_budget_exceeded", False):
            previous = list(state.get("mcp_products", []))
            outstanding = set(state.get("unfulfilled_requests", []) or [])
            if previous and outstanding:
                seed = [item for item in seed if str(item.get("query", "")) in outstanding]
                accepted = previous
                if remaining != math.inf:
                    previous_total = sum(
                        float(p.get("price", 0.0) or 0.0) * int(p.get("quantity", 1) or 1) for p in previous
                    )
                    remaining = round(remaining - previous_total, 2)

        for item in seed:
            query = str(item.get("query", ""))
            quantity = int(item.get("quantity", 1) or 1)
            category = item.get("category")
            if steps >= self._max_steps:
                unfulfilled.append(query)
                continue
            steps += 1
            product: dict[str, Any] | None = None
            if "search_products" in allowlist:
                product = await self._products.search_one(
                    query, quantity, bool(item.get("prefer_private_label", False)), ceiling(), category, context
                )
                if product is None:
                    simplified = query.split()[0] if query.split() else query
                    if simplified.lower() != query.lower():
                        product = await self._products.search_one(
                            simplified, quantity, False, ceiling(), category, context
                        )
                        if product is not None:
                            trace.append(
                                {
                                    "tool": "search_products",
                                    "query": simplified,
                                    "status": "simplified",
                                    "product_id": product.get("id"),
                                }
                            )
            if product is None:
                product = await self._substitute(query, quantity, ceiling(), category, allowlist, trace, context)
            if product is None:
                unfulfilled.append(query)
                trace.append({"tool": "search_products", "query": query, "status": "not_found"})
                continue
            index = await self._choose_index([product], remaining if remaining != math.inf else budget, goal)
            chosen = [product][index]
            score = planner.score(chosen, remaining if remaining != math.inf else 10**12)
            if score < 0:
                unfulfilled.append(query)
                trace.append({"tool": "search_products", "query": query, "status": "rejected_over_budget"})
                continue
            chosen = await self._enrich_details(chosen, allowlist, trace, context)
            accepted.append(chosen)
            if remaining != math.inf:
                remaining = round(remaining - float(chosen.get("price", 0.0)) * quantity, 2)
            trace.append(
                {"tool": "search_products", "query": query, "status": "accepted", "product_id": chosen.get("id")}
            )

        categories = {str(p.get("category")) for p in accepted if p.get("category")}
        coverage_ok = all(req in categories for req in planner.min_coverage())
        is_met = bool(accepted) and coverage_ok and not unfulfilled

        if hard and budget > 0 and is_met and remaining != math.inf:
            floor = settings.MIN_ITEM_PRICE_FLOOR
            if "get_promotions" in allowlist and steps < self._max_steps and remaining >= floor:
                steps += 1
                try:
                    promos = await self._products.fetch_promo_products(context, remaining, 5)
                except Exception as exc:  # noqa: BLE001 - promos are best-effort
                    logger.debug("Picker promotions failed: %s", exc)
                    promos = []
                for promo in promos:
                    line_total = float(promo.get("price", 0.0)) * int(promo.get("quantity", 1) or 1)
                    if line_total <= remaining and planner.score(promo, remaining) >= 0:
                        accepted.append(promo)
                        remaining = round(remaining - line_total, 2)
                        trace.append(
                            {
                                "tool": "get_promotions",
                                "query": promo.get("title", ""),
                                "status": "promo_accepted",
                                "product_id": promo.get("id"),
                            }
                        )
                        if remaining < floor:
                            break
            for filler_query in planner.filler_queries():
                if steps >= self._max_steps or remaining < floor:
                    break
                steps += 1
                filler = await self._products.search_one(filler_query, 1, True, remaining, None, context)
                if filler is not None and planner.score(filler, remaining) >= 0:
                    accepted.append(filler)
                    remaining = round(remaining - float(filler.get("price", 0.0)), 2)
                    trace.append(
                        {
                            "tool": "search_products",
                            "query": filler_query,
                            "status": "filler_accepted",
                            "product_id": filler.get("id"),
                        }
                    )

        logger.info(
            "picker done intent=%s accepted=%d unfulfilled=%d met=%s remaining=%s",
            state.get("intent"),
            len(accepted),
            len(unfulfilled),
            is_met,
            remaining if remaining != math.inf else "unlimited",
        )
        return {
            "calculated_items": seed,
            "mcp_products": accepted,
            "remaining_budget": 0.0 if remaining == math.inf else round(remaining, 2),
            "unfulfilled_requests": unfulfilled,
            "is_requirements_met": is_met,
            "picker_trace": trace,
            "picker_accepted": len(accepted),
            "shopping_context": context,
        }
