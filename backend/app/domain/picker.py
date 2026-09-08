"""Shared iterative picker: greedy policy-driven ReAct loop with an LLM advisor hook."""

import logging
import math
import re
from typing import Any, Protocol

from ..config import settings
from ..services import gemini_service
from ..services.mcp_service import mcp_product_service
from ..state import SilpoAgentState
from .planners import get_domain_planner

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[\w']+", re.UNICODE)

_STOP_TOKENS = frozenset(
    {
        "для",
        "до",
        "на",
        "по",
        "зі",
        "із",
        "з",
        "і",
        "та",
        "в",
        "у",
        "не",
        "гриль",
        "гриля",
        "грилю",
        "грилем",
        "грилі",
        "премія",
        "преміум",
        "супер",
        "new",
    }
)

_SYNONYM_GROUPS: tuple[frozenset[str], ...] = (
    frozenset({"гриб", "печериц", "шампіньйон", "глив"}),
    frozenset({"курк", "куря", "курча", "chicken"}),
)

_RELEVANCE_BLOCKS: tuple[tuple[tuple[str, ...], tuple[str, ...], str], ...] = (
    (
        ("вугілл", "вугільн"),
        ("щітк", "щетк", "зубн", "colgate", "паст", "ополіскув"),
        "засіб гігієни не є деревним вугіллям",
    ),
    (
        ("курк", "куря", "курча", "chicken"),
        (
            "свин",
            "ошийок",
            "ошийник",
            "бекон",
            "сало",
            "ялович",
            "телятин",
            "баранин",
            "тунец",
            "тунець",
            "лосос",
            "пельмен",
            "ковбас",
            "сосиск",
        ),
        "інше м'ясо замість курки",
    ),
)

_NON_ALCOHOLIC_QUERY_MARKERS = ("безалкогольн", "non-alcoholic", "non alcoholic", "zero alcohol")
_NON_ALCOHOLIC_TITLE_MARKERS = ("безалкогольн", "б/а", "0.0", "0,0", "0%", "zero")

_DISPOSABLE_GOAL_MARKERS = ("одноразов", "disposable", "паперов", "пластик")
_REUSABLE_TITLE_MARKERS = ("термочашка", "термокружка", "термостакан", "термос", "багаторазов", "reusable", "екочашка")
_DISPOSABLE_TITLE_MARKERS = ("одноразов", "паперов", "пластик", "disposable")

_BUDGET_FILL_LOW = 0.70
_MAX_TOP_UP_QTY = 6

_FISH_MARKERS = (
    "риб",
    "хек",
    "минтай",
    "лосось",
    "тунец",
    "тунець",
    "короп",
    "дорадо",
    "пангасіус",
)

_CEREAL_SUBTYPES = (
    "греч",
    "рис",
    "вівсян",
    "манн",
    "пшон",
    "макарон",
    "булгур",
    "кускус",
)

_ALCOHOLIC_TITLE_MARKERS = (
    "віскі",
    "whisky",
    "whiskey",
    "горілк",
    "vodka",
    "коньяк",
    "cognac",
    "бренді",
    "текіл",
    "tequila",
    "лікер",
    "вермут",
    "шампанськ",
    "вино",
    "wine",
    "пиво",
    "beer",
    "сидр",
    "cider",
    "слабоалкогольн",
)


def _content_tokens(text: str) -> list[str]:
    return [token for token in _TOKEN_RE.findall(text.lower()) if token not in _STOP_TOKENS]


def _token_key(token: str) -> str:
    for group in _SYNONYM_GROUPS:
        if any(len(token) >= 4 and token[:4] == member[:4] for member in group):
            return "group:" + min(group)
    return token


def _tokens_shared(query_token: str, title_token: str) -> bool:
    if query_token == title_token:
        return True
    if query_token.startswith("group:") or title_token.startswith("group:"):
        return False
    return len(query_token) >= 4 and len(title_token) >= 4 and query_token[:4] == title_token[:4]


def is_relevant(query: str, title: str) -> tuple[bool, str]:
    """Strict deterministic check that a found product title matches the search query.

    Returns (True, "") when the title may be accepted, otherwise (False, reason).
    Blocklist constraints run first so shared filler words (e.g. "деревне вугілля"
    in a toothbrush name) can never override a category mismatch. Preparation words
    such as "гриля" are stop-words: they describe cooking, not the product itself.
    """
    query_norm = query.lower()
    title_norm = title.lower()
    for query_markers, forbidden_markers, reason in _RELEVANCE_BLOCKS:
        if any(marker in query_norm for marker in query_markers) and any(
            marker in title_norm for marker in forbidden_markers
        ):
            return False, reason
    if any(marker in query_norm for marker in _NON_ALCOHOLIC_QUERY_MARKERS) and not any(
        marker in title_norm for marker in _NON_ALCOHOLIC_TITLE_MARKERS
    ):
        return False, "алкогольний товар замість безалкогольного"
    if "риб" in query_norm and any(marker in title_norm for marker in _FISH_MARKERS):
        return True, ""
    query_subtypes = [sub for sub in _CEREAL_SUBTYPES if sub in query_norm]
    title_subtypes = [sub for sub in _CEREAL_SUBTYPES if sub in title_norm]
    if query_subtypes and title_subtypes and not set(query_subtypes) & set(title_subtypes):
        return False, f"інший вид крупи: «{title}» не відповідає запиту «{query}»"
    query_tokens = [_token_key(token) for token in _content_tokens(query_norm)]
    title_tokens = [_token_key(token) for token in _content_tokens(title_norm)]
    if any(_tokens_shared(query_token, title_token) for query_token in query_tokens for title_token in title_tokens):
        return True, ""
    return False, f"«{title}» не відповідає запиту «{query}»"


def violates_hard_constraints(title: str, goal: str) -> tuple[bool, str]:
    """Goal-level backstop: rejects titles that break explicit goal demands.

    Unlike is_relevant (query-level), this fires even when the query itself is
    loose (e.g. a formulated "Пиво" under a non-alcoholic goal) and on query-less
    promo candidates that otherwise bypass every check.
    """
    title_norm = title.lower().replace("виноград", "")
    goal_norm = goal.lower()
    goal_demands_free = any(marker in goal_norm for marker in _NON_ALCOHOLIC_QUERY_MARKERS)
    title_is_free = any(marker in title_norm for marker in _NON_ALCOHOLIC_TITLE_MARKERS)
    title_is_alcoholic = any(marker in title_norm for marker in _ALCOHOLIC_TITLE_MARKERS)
    if goal_demands_free and not title_is_free and title_is_alcoholic:
        return True, "алкогольний товар при безалкогольній цілі"
    goal_disposable = any(marker in goal_norm for marker in _DISPOSABLE_GOAL_MARKERS)
    title_reusable = any(marker in title_norm for marker in _REUSABLE_TITLE_MARKERS)
    title_disposable = any(marker in title_norm for marker in _DISPOSABLE_TITLE_MARKERS)
    if goal_disposable and title_reusable and not title_disposable:
        return True, "багаторазовий посуд замість одноразового"
    return False, ""


class PickerAdvisor(Protocol):
    async def choose(
        self, candidates: list[dict[str, Any]], remaining: float, goal: str, query: str = ""
    ) -> int | None:
        """Returns the chosen candidate index, ADVISOR_VETO to reject all, or None to abstain."""
        ...


class GreedyAdvisor:
    async def choose(
        self, candidates: list[dict[str, Any]], remaining: float, goal: str, query: str = ""
    ) -> int | None:
        return None


class GeminiPickerAdvisor:
    async def choose(
        self, candidates: list[dict[str, Any]], remaining: float, goal: str, query: str = ""
    ) -> int | None:
        return await gemini_service.choose_picker_candidate(candidates, remaining, goal, query)


class PickerQueryFormulator(Protocol):
    async def formulate(self, goal: str, fallback_seed: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Returns goal-derived seed queries, or the fallback seed when unsure."""
        ...


class PassthroughFormulator:
    async def formulate(self, goal: str, fallback_seed: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return fallback_seed


class GeminiQueryFormulator:
    async def formulate(self, goal: str, fallback_seed: list[dict[str, Any]]) -> list[dict[str, Any]]:
        formulated = await gemini_service.formulate_picker_queries(goal, fallback_seed)
        return formulated if formulated is not None else fallback_seed


class PickerJudge(Protocol):
    async def judge(self, query: str, candidate: dict[str, Any], goal: str) -> dict[str, Any]:
        """Returns {"verdict": "accept"|"reject", "reason": str, "suggested_query": str|None}."""
        ...


class GreedyJudge:
    async def judge(self, query: str, candidate: dict[str, Any], goal: str) -> dict[str, Any]:
        return {"verdict": "accept", "reason": "", "suggested_query": None}


class GeminiPickerJudge:
    async def judge(self, query: str, candidate: dict[str, Any], goal: str) -> dict[str, Any]:
        return await gemini_service.judge_picker_candidate(query, candidate, goal)


class PickerService:
    """Iteratively picks priced products until budget/requirements resolve or steps run out."""

    def __init__(
        self,
        product_service: Any | None = None,
        advisor: PickerAdvisor | None = None,
        max_steps: int | None = None,
        query_formulator: PickerQueryFormulator | None = None,
        judge: PickerJudge | None = None,
    ) -> None:
        self._products = product_service if product_service is not None else mcp_product_service
        self._advisor = advisor if advisor is not None else GreedyAdvisor()
        self._max_steps = max_steps if max_steps is not None else settings.MAX_PICKER_STEPS
        self._formulator = query_formulator if query_formulator is not None else PassthroughFormulator()
        self._judge = judge if judge is not None else GreedyJudge()

    async def _choose_index(self, shortlist: list[dict[str, Any]], remaining: float, goal: str, query: str) -> int:
        try:
            index = await self._advisor.choose(shortlist, remaining, goal, query)
        except Exception as exc:  # noqa: BLE001 - advisor failure falls back to greedy
            logger.debug("Picker advisor failed, using greedy fallback: %s", exc)
            return 0
        if index == gemini_service.ADVISOR_VETO:
            return index
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

    @staticmethod
    def _build_goal(state: SilpoAgentState) -> str:
        user_text = (state.get("user_text") or "").strip()[:300]
        raw_requests = list(state.get("raw_item_requests") or [])
        goal = (
            f"intent={state.get('intent')} budget={state.get('budget', 0.0) or 0.0} "
            f"people={state.get('people_count')} request={user_text} items={','.join(raw_requests)}"
        )
        outstanding = list(state.get("unfulfilled_requests") or [])
        if outstanding:
            goal += f" misses={','.join(outstanding)}"
            reasons = [
                str(entry.get("reason", ""))
                for entry in (state.get("picker_trace") or [])
                if entry.get("status") in ("rejected_irrelevant", "llm_rejected") and entry.get("reason")
            ][:5]
            if reasons:
                goal += f" feedback={'; '.join(reasons)}"
        return goal

    async def _resolve_candidate(
        self,
        query: str,
        quantity: int,
        prefer_private_label: bool,
        max_price: float | None,
        category: str | None,
        allowlist: set[str],
        trace: list[dict[str, Any]],
        context: dict[str, str] | None,
    ) -> dict[str, Any] | None:
        product: dict[str, Any] | None = None
        if "search_products" in allowlist:
            product = await self._products.search_one(
                query, quantity, prefer_private_label, max_price, category, context
            )
            if product is None:
                simplified = query.split()[0] if query.split() else query
                if simplified.lower() != query.lower():
                    product = await self._products.search_one(simplified, quantity, False, max_price, category, context)
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
            product = await self._substitute(query, quantity, max_price, category, allowlist, trace, context)
        if product is None:
            trace.append({"tool": "search_products", "query": query, "status": "not_found"})
        return product

    @staticmethod
    def _top_up_to_band(
        accepted: list[dict[str, Any]], budget: float, remaining: float, trace: list[dict[str, Any]]
    ) -> float:
        """Raises core food quantities round-robin until the cart reaches the fill band.

        Never exceeds the hard budget ceiling and needs no extra searches: it only
        grows quantities of already accepted products. Charcoal and promos are out
        of scope — nobody needs four bags of coal for a bigger budget.
        Each SKU is capped at _MAX_TOP_UP_QTY so a cheap staple cannot inflate
        to 30+ units for a weekly budget.
        """
        target = round(budget * _BUDGET_FILL_LOW, 2)
        total = round(budget - remaining, 2)
        if total >= target:
            return remaining
        core = [product for product in accepted if str(product.get("category", "")) not in ("promo", "accessories")]
        if not core:
            return remaining
        while total < target:
            progressed = False
            for product in core:
                try:
                    unit = float(product.get("price", 0.0) or 0.0)
                except (TypeError, ValueError):
                    continue
                if unit <= 0 or unit > remaining or total + unit > budget:
                    continue
                try:
                    quantity = int(product.get("quantity", 1) or 1)
                except (TypeError, ValueError):
                    quantity = 1
                if quantity >= _MAX_TOP_UP_QTY:
                    continue
                product["quantity"] = quantity + 1
                total = round(total + unit, 2)
                remaining = round(remaining - unit, 2)
                progressed = True
                trace.append(
                    {
                        "tool": "search_products",
                        "query": str(product.get("title", "")),
                        "status": "topped_up",
                        "product_id": product.get("id"),
                    }
                )
                if total >= target:
                    break
            if not progressed:
                break
        return remaining

    async def run(self, state: SilpoAgentState) -> dict[str, Any]:
        planner = get_domain_planner(state.get("intent"))
        budget = state.get("budget", 0.0) or 0.0
        hard = planner.budget_mode() == "hard_fill"
        allowlist = set(planner.tool_allowlist())
        remaining = budget if budget > 0 else math.inf
        goal = self._build_goal(state)

        def ceiling() -> float | None:
            return remaining if hard and budget > 0 else None

        context = state.get("shopping_context") or await self._products.resolve_shopping_context(
            state.get("delivery_address")
        )

        seed = list(state.get("calculated_items") or []) or planner.plan(state)
        try:
            formulated = await self._formulator.formulate(goal, seed)
        except Exception as exc:  # noqa: BLE001 - formulation failure keeps the planner seed
            logger.debug("Picker query formulation failed, using planner seed: %s", exc)
            formulated = seed
        seed = formulated or seed
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
                accepted = [dict(product) for product in previous]
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
            product = await self._resolve_candidate(
                query,
                quantity,
                bool(item.get("prefer_private_label", False)),
                ceiling(),
                category,
                allowlist,
                trace,
                context,
            )
            if product is None:
                unfulfilled.append(query)
                continue
            violated, violation = violates_hard_constraints(str(product.get("title", "")), goal)
            if violated:
                unfulfilled.append(query)
                trace.append(
                    {
                        "tool": "search_products",
                        "query": query,
                        "status": "rejected_constraint",
                        "reason": violation,
                        "product_id": product.get("id"),
                    }
                )
                continue
            effective_query = query
            try:
                verdict = await self._judge.judge(query, product, goal)
            except Exception as exc:  # noqa: BLE001 - judge failure falls back to greedy accept
                logger.debug("Picker judge failed, accepting greedily: %s", exc)
                verdict = {"verdict": "accept", "reason": "", "suggested_query": None}
            if verdict.get("verdict") == "reject":
                suggested = verdict.get("suggested_query")
                trace.append(
                    {
                        "tool": "choose_picker_candidate",
                        "query": query,
                        "status": "llm_rejected",
                        "reason": str(verdict.get("reason", "")),
                        "product_id": product.get("id"),
                    }
                )
                product = None
                if isinstance(suggested, str) and suggested.strip() and steps < self._max_steps:
                    steps += 1
                    product = await self._resolve_candidate(
                        suggested.strip(), quantity, False, ceiling(), category, allowlist, trace, context
                    )
                    if product is not None:
                        effective_query = suggested.strip()
                        trace.append(
                            {
                                "tool": "search_products",
                                "query": effective_query,
                                "status": "llm_reformulated",
                                "product_id": product.get("id"),
                            }
                        )
                if product is None:
                    unfulfilled.append(query)
                    continue
            relevant, reason = is_relevant(effective_query, str(product.get("title", "")))
            if not relevant:
                unfulfilled.append(query)
                trace.append(
                    {
                        "tool": "search_products",
                        "query": query,
                        "status": "rejected_irrelevant",
                        "reason": reason,
                        "product_id": product.get("id"),
                    }
                )
                continue
            index = await self._choose_index([product], remaining if remaining != math.inf else budget, goal, query)
            if index == gemini_service.ADVISOR_VETO:
                unfulfilled.append(query)
                trace.append(
                    {
                        "tool": "choose_picker_candidate",
                        "query": query,
                        "status": "advisor_veto",
                        "reason": "advisor rejected every candidate for the query",
                        "product_id": product.get("id"),
                    }
                )
                continue
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

        if hard and budget > 0 and remaining != math.inf and accepted and is_met:
            remaining = self._top_up_to_band(accepted, budget, remaining, trace)

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
                        promo_title = str(promo.get("title", ""))
                        violated, violation = violates_hard_constraints(promo_title, goal)
                        if violated:
                            trace.append(
                                {
                                    "tool": "get_promotions",
                                    "query": promo_title,
                                    "status": "rejected_constraint",
                                    "reason": violation,
                                    "product_id": promo.get("id"),
                                }
                            )
                            continue
                        try:
                            promo_verdict = await self._judge.judge("", promo, goal)
                        except Exception as exc:  # noqa: BLE001 - judge failure keeps greedy behavior
                            logger.debug("Picker promo judge failed, accepting greedily: %s", exc)
                            promo_verdict = {"verdict": "accept", "reason": "", "suggested_query": None}
                        if promo_verdict.get("verdict") == "reject":
                            trace.append(
                                {
                                    "tool": "get_promotions",
                                    "query": promo_title,
                                    "status": "llm_rejected",
                                    "reason": str(promo_verdict.get("reason", "")),
                                    "product_id": promo.get("id"),
                                }
                            )
                            continue
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
                if filler is None:
                    continue
                filler_title = str(filler.get("title", ""))
                violated, violation = violates_hard_constraints(filler_title, goal)
                if violated:
                    trace.append(
                        {
                            "tool": "search_products",
                            "query": filler_query,
                            "status": "rejected_constraint",
                            "reason": violation,
                            "product_id": filler.get("id"),
                        }
                    )
                    continue
                filler_relevant, filler_reason = is_relevant(filler_query, filler_title)
                if not filler_relevant:
                    trace.append(
                        {
                            "tool": "search_products",
                            "query": filler_query,
                            "status": "rejected_irrelevant",
                            "reason": filler_reason,
                            "product_id": filler.get("id"),
                        }
                    )
                    continue
                if planner.score(filler, remaining) >= 0:
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
