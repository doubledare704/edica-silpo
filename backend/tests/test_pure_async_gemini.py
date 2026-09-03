"""Phase H6: pure-async Gemini — no to_thread sync fallback."""

import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def test_gemini_service_has_no_sync_fallback() -> None:
    import app.services.gemini_service as svc

    src = inspect.getsource(svc)
    assert "to_thread" not in src, "sync fallback must be removed (decision #2)"
    assert "client.aio.models.generate_content" in src


def test_tts_service_uses_pure_async() -> None:
    import app.services.tts_service as tts

    src = inspect.getsource(tts)
    assert "await client.aio.models.generate_content" in src
    assert "to_thread" not in src


@pytest.mark.asyncio
async def test_transcribe_never_calls_sync_on_aio_attribute_error(monkeypatch) -> None:
    import app.services.gemini_service as svc

    monkeypatch.setattr(svc.settings, "GEMINI_MOCK_MODE", False)
    monkeypatch.setattr(svc.settings, "GEMINI_API_KEY", "fake-key")

    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(side_effect=AttributeError("no aio"))
    mock_client.models.generate_content = MagicMock(return_value=MagicMock(text="SHOULD NOT BE USED"))

    with patch("app.services.gemini_service.get_genai_client", return_value=mock_client):
        from app.services.gemini_service import _MOCK_TRANSCRIPTION, transcribe_audio

        result = await transcribe_audio(b"fake_audio", mime="audio/webm")
        # Pure-async: sync fallback must NOT be used; graceful mock fallback instead
        assert mock_client.models.generate_content.call_count == 0
        assert result == _MOCK_TRANSCRIPTION


@pytest.mark.asyncio
async def test_parse_intent_never_calls_sync_on_aio_attribute_error(monkeypatch) -> None:
    import app.services.gemini_service as svc

    monkeypatch.setattr(svc.settings, "GEMINI_MOCK_MODE", False)
    monkeypatch.setattr(svc.settings, "GEMINI_API_KEY", "fake-key")

    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(side_effect=AttributeError("no aio"))
    mock_client.models.generate_content = MagicMock(
        return_value=MagicMock(
            text='{"intent":"gourmet","budget":0,"people_count":2,'
            '"dietary_restrictions":[],"raw_item_requests":["сир"]}'
        )
    )

    with patch("app.services.gemini_service.get_genai_client", return_value=mock_client):
        from app.enums import IntentEnum
        from app.services.gemini_service import parse_intent_multimodal

        result = await parse_intent_multimodal(
            user_text="Збери кошик для пікніка на 6 людей до 2500 грн, один вегетаріанець",
            audio_bytes=None,
        )
        assert mock_client.models.generate_content.call_count == 0
        # Falls back to regex, not sync path
        assert result.intent == IntentEnum.PARTY
        assert result.budget == 2500.0
