from unittest.mock import AsyncMock, patch

import pytest
from app.enums import IntentEnum
from app.nodes.parse_intent import ParsedIntentSchema
from app.state import SilpoAgentState


def _make_state(
    *,
    user_text: str | None = None,
    audio_bytes: bytes | None = None,
    intent: IntentEnum | None = None,
) -> SilpoAgentState:
    return {
        "audio_bytes": audio_bytes,
        "user_text": user_text,
        "intent": intent,
        "budget": 0.0,
        "people_count": None,
        "dietary_restrictions": [],
        "raw_item_requests": [],
        "calculated_items": [],
        "mcp_products": [],
        "total_price": 0.0,
        "attempts": 0,
        "max_attempts": 3,
        "is_budget_exceeded": False,
        "cart_url": None,
        "summary_message": "",
        "audio_url": None,
        "messages": [],
    }


@pytest.mark.asyncio
async def test_parse_intent_uses_gemini_structured_output(monkeypatch) -> None:
    import app.services.gemini_service as svc

    monkeypatch.setattr(svc.settings, "GEMINI_MOCK_MODE", False)
    monkeypatch.setattr(svc.settings, "GEMINI_API_KEY", "fake-key")
    svc._client = None  # type: ignore[attr-defined]

    gemini_result = ParsedIntentSchema(
        intent=IntentEnum.GOURMET,
        budget=0.0,
        people_count=2,
        dietary_restrictions=[],
        raw_item_requests=["сир", "вино", "прошуто"],
    )
    mock_parse = AsyncMock(return_value=gemini_result)
    with patch("app.services.gemini_service.parse_intent_multimodal", mock_parse):
        from app.nodes.parse_intent import parse_intent_node

        state = _make_state(user_text="Підбери сир і вино для гурман вечері на 2")
        result = await parse_intent_node(state)
        assert result["intent"] == IntentEnum.GOURMET
        assert "сир" in result["raw_item_requests"]
        mock_parse.assert_called_once()
        call_kwargs = mock_parse.call_args
        assert call_kwargs is not None
        # Should pass user_text, audio_bytes
        _args, kwargs = call_kwargs
        assert kwargs.get("user_text") == "Підбери сир і вино для гурман вечері на 2"


@pytest.mark.asyncio
async def test_parse_intent_multimodal_audio_path(monkeypatch) -> None:
    import app.services.gemini_service as svc

    monkeypatch.setattr(svc.settings, "GEMINI_MOCK_MODE", False)
    monkeypatch.setattr(svc.settings, "GEMINI_API_KEY", "fake-key")
    svc._client = None  # type: ignore[attr-defined]

    gemini_result = ParsedIntentSchema(
        intent=IntentEnum.OFFICE,
        budget=1500.0,
        people_count=10,
        dietary_restrictions=[],
        raw_item_requests=["кава", "чай", "печиво", "вода", "фрукти"],
    )
    mock_parse = AsyncMock(return_value=gemini_result)
    with patch("app.services.gemini_service.parse_intent_multimodal", mock_parse):
        from app.nodes.parse_intent import parse_intent_node

        state = _make_state(user_text="Офісний кошик на 10 людей до 1500 грн", audio_bytes=b"\x1a\x45\xdf\xa3 webm")
        result = await parse_intent_node(state)
        assert result["intent"] == IntentEnum.OFFICE
        assert result["budget"] == 1500.0
        assert result["people_count"] == 10
        # Should forward audio_bytes
        assert mock_parse.call_args[1].get("audio_bytes") == b"\x1a\x45\xdf\xa3 webm"


@pytest.mark.asyncio
async def test_parse_intent_handles_office_gourmet_via_llm(monkeypatch) -> None:
    import app.services.gemini_service as svc

    monkeypatch.setattr(svc.settings, "GEMINI_MOCK_MODE", False)
    monkeypatch.setattr(svc.settings, "GEMINI_API_KEY", "fake-key")
    svc._client = None  # type: ignore[attr-defined]

    # Office
    office_result = ParsedIntentSchema(
        intent=IntentEnum.OFFICE,
        budget=0.0,
        people_count=None,
        dietary_restrictions=[],
        raw_item_requests=["кава", "чай", "печиво"],
    )
    mock_parse = AsyncMock(return_value=office_result)
    with patch("app.services.gemini_service.parse_intent_multimodal", mock_parse):
        from app.nodes.parse_intent import parse_intent_node

        state = _make_state(user_text="Офіс сніданок кава чай")
        result = await parse_intent_node(state)
        assert result["intent"] == IntentEnum.OFFICE

    # Gourmet
    gourmet_result = ParsedIntentSchema(
        intent=IntentEnum.GOURMET,
        budget=2000.0,
        people_count=None,
        dietary_restrictions=[],
        raw_item_requests=["сир", "вино"],
    )
    mock_parse2 = AsyncMock(return_value=gourmet_result)
    with patch("app.services.gemini_service.parse_intent_multimodal", mock_parse2):
        from app.nodes.parse_intent import parse_intent_node

        state = _make_state(user_text="Гурман вечеря сир вино до 2000 грн")
        result = await parse_intent_node(state)
        assert result["intent"] == IntentEnum.GOURMET
        assert result["budget"] == 2000.0


@pytest.mark.asyncio
async def test_parse_intent_empty_still_returns_defaults() -> None:
    from app.nodes.parse_intent import parse_intent_node

    state = _make_state(user_text=None, audio_bytes=None)
    result = await parse_intent_node(state)
    # Should not crash, return existing or defaults
    assert result["intent"] in (IntentEnum.PARTY, IntentEnum.BUDGET, None, IntentEnum.OFFICE, IntentEnum.GOURMET)
    assert isinstance(result["budget"], float)


@pytest.mark.asyncio
async def test_parse_intent_fallback_when_gemini_fails(monkeypatch) -> None:
    import app.services.gemini_service as svc

    monkeypatch.setattr(svc.settings, "GEMINI_MOCK_MODE", False)
    monkeypatch.setattr(svc.settings, "GEMINI_API_KEY", "fake-key")
    svc._client = None  # type: ignore[attr-defined]

    mock_parse = AsyncMock(side_effect=RuntimeError("gemini down"))
    with patch("app.services.gemini_service.parse_intent_multimodal", mock_parse):
        from app.nodes.parse_intent import parse_intent_node

        state = _make_state(user_text="Збери кошик для пікніка на 6 людей до 2500 грн, один вегетаріанець")
        result = await parse_intent_node(state)
        # Should fallback to regex, not crash, still parse party
        assert result["intent"] == IntentEnum.PARTY
        assert result["budget"] == 2500.0
