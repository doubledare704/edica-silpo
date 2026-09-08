"""Gated live Gemini smoke tests. Run only with real credentials in the shell env.

Requires GEMINI_API_KEY (GEMINI_MOCK_MODE is forced off inside the tests).
Without the key the whole module skips, so default/CI runs stay offline.
Live calls are throttled (free-tier per-minute quota) and fail-soft Nones are
re-checked with a quota ping, so exhausted quota reads as "skipped", not as a
product failure.
"""

import asyncio
import os
import time

import pytest
from app.enums import IntentEnum
from app.services import gemini_service
from google.genai import types

_REAL_KEY = os.getenv("GEMINI_API_KEY")

pytestmark = pytest.mark.skipif(
    not _REAL_KEY,
    reason="Set GEMINI_API_KEY to run the live Gemini smoke test",
)

_GRILL_TEXT = (
    "Хочу зібрати друзів на гриль: курка, свіжі печериці та овочі, "
    "безалкогольне пиво й одноразовий посуд, 5 людей до 5000 грн"
)

_THROTTLE_SECONDS = 25.0

_shared_state: dict[str, float | bool] = {}


def _live_settings(monkeypatch) -> None:
    assert _REAL_KEY, "live smoke test requires GEMINI_API_KEY"
    monkeypatch.setattr(gemini_service.settings, "GEMINI_API_KEY", _REAL_KEY)
    monkeypatch.setattr(gemini_service.settings, "GEMINI_MOCK_MODE", False)


async def _throttle() -> None:
    now = time.monotonic()
    wait = _THROTTLE_SECONDS - (now - _shared_state.get("last_call", 0.0))
    if wait > 0:
        await asyncio.sleep(wait)
    _shared_state["last_call"] = time.monotonic()


async def _ping() -> None:
    await gemini_service._agenerate(
        model=gemini_service.settings.GEMINI_MODEL,
        contents=["ping"],
        config=types.GenerateContentConfig(
            temperature=0.0,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        ),
    )


async def _require_quota(monkeypatch) -> None:
    """Forces live settings; skips the session when the key has no quota left."""
    _live_settings(monkeypatch)
    if "quota_ok" not in _shared_state:
        await _throttle()
        try:
            await _ping()
        except Exception as exc:
            if "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc):
                _shared_state["quota_ok"] = False
            else:
                raise
        else:
            _shared_state["quota_ok"] = True
    if not _shared_state["quota_ok"]:
        pytest.skip("Gemini quota exhausted, cannot run live smoke")


async def _assert_or_quota_skip(condition: bool) -> None:
    """Fails loudly on genuine mismatch, skips when quota died mid-smoke."""
    if condition:
        return
    await _throttle()
    try:
        await _ping()
    except Exception as exc:
        if "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc):
            pytest.skip("Gemini quota exhausted mid-smoke")
        raise
    assert condition


@pytest.mark.asyncio
async def test_live_parse_grill_request_extracts_items(monkeypatch) -> None:
    await _require_quota(monkeypatch)
    await _throttle()
    parsed = await gemini_service.parse_intent_multimodal(user_text=_GRILL_TEXT, audio_bytes=None)
    assert parsed.intent == IntentEnum.PARTY
    assert parsed.budget == 5000.0
    assert parsed.people_count == 5
    joined = " ".join(parsed.raw_item_requests).lower()
    assert "кур" in joined
    assert "печериц" in joined or "гриб" in joined
    assert "безалкогольн" in joined


@pytest.mark.asyncio
async def test_live_formulate_picker_queries_smoke(monkeypatch) -> None:
    await _require_quota(monkeypatch)
    await _throttle()
    goal = f"intent=party budget=5000 people=5 request={_GRILL_TEXT} items=курка,печериці"
    fallback = [{"query": "Ошийник свинячий", "category": "meat", "quantity": 2}]
    seed = await gemini_service.formulate_picker_queries(goal, fallback)
    await _assert_or_quota_skip(seed is not None and len(seed) >= 2)
    assert seed is not None
    assert all(item.get("query") and item.get("category") for item in seed)


@pytest.mark.asyncio
async def test_live_judge_picker_candidate_smoke(monkeypatch) -> None:
    await _require_quota(monkeypatch)
    goal = "request=гриль з куркою items=курка"
    await _throttle()
    good = await gemini_service.judge_picker_candidate(
        "Курка для гриля", {"title": "Куряче філе для гриля", "price": 180.0, "quantity": 1}, goal
    )
    assert good["verdict"] == "accept"
    await _throttle()
    bad = await gemini_service.judge_picker_candidate(
        "Курка для гриля", {"title": "Ошийник свинячий", "price": 240.0, "quantity": 1}, goal
    )
    await _assert_or_quota_skip(bad["verdict"] == "reject")


@pytest.mark.asyncio
async def test_live_plan_weekly_meals_smoke(monkeypatch) -> None:
    await _require_quota(monkeypatch)
    await _throttle()
    goal = "intent=budget budget=2000 people=2 request=продукти на тиждень з рибою, овочами і крупою items=риба,овочі,крупа"
    seed = await gemini_service.plan_weekly_meals(goal)
    await _assert_or_quota_skip(seed is not None and 2 <= len(seed) <= 10)
    assert seed is not None
    assert all(item.get("query") and item.get("category") for item in seed)
    joined = " ".join(str(item.get("query", "")) for item in seed).lower()
    assert "хек" in joined or "риб" in joined


@pytest.mark.asyncio
async def test_live_research_menu_smoke(monkeypatch) -> None:
    await _require_quota(monkeypatch)
    await _throttle()
    goal = f"intent=party budget=5000 people=5 request={_GRILL_TEXT} items=курка,печериці"
    menu = await gemini_service.research_menu(goal)
    await _assert_or_quota_skip(menu is not None and 2 <= len(menu) <= 10)
    assert menu is not None
    assert all(item.get("query") and item.get("category") for item in menu)
