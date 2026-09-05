from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.config import Settings
from app.enums import IntentEnum


def test_default_gemini_settings() -> None:
    config = Settings()
    assert config.GEMINI_API_KEY == ""
    assert config.GEMINI_MODEL == "gemini-3.5-flash-lite"
    assert config.GEMINI_TTS_MODEL == "gemini-3.1-flash-tts-preview"
    assert config.TTS_PROVIDER == "respeecher"
    assert config.GEMINI_MOCK_MODE is False


def test_gemini_settings_env_override(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    monkeypatch.setenv("GEMINI_MOCK_MODE", "true")
    monkeypatch.setenv("TTS_PROVIDER", "gemini")
    config = Settings()
    assert config.GEMINI_API_KEY == "test-key"
    assert config.GEMINI_MOCK_MODE is True
    assert config.TTS_PROVIDER == "gemini"


@pytest.mark.asyncio
async def test_transcribe_audio_mock_mode_returns_fallback(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_MOCK_MODE", "true")
    import app.services.gemini_service as svc

    monkeypatch.setattr(svc.settings, "GEMINI_MOCK_MODE", True)
    monkeypatch.setattr(svc.settings, "GEMINI_API_KEY", "")
    svc._client = None  # type: ignore[attr-defined]
    from app.services.gemini_service import transcribe_audio

    result = await transcribe_audio(b"fake_audio")
    assert isinstance(result, str)
    assert len(result) > 0
    # In mock mode should return Ukrainian fallback (hardcoded)
    assert "пікніка" in result or "Збери" in result


@pytest.mark.asyncio
async def test_transcribe_audio_with_mocked_client(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_MOCK_MODE", "false")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    import app.services.gemini_service as svc

    monkeypatch.setattr(svc.settings, "GEMINI_MOCK_MODE", False)
    monkeypatch.setattr(svc.settings, "GEMINI_API_KEY", "fake-key")
    svc._client = None  # type: ignore[attr-defined]

    mock_response = MagicMock()
    mock_response.text = "Збери кошик для офісу на 10 людей до 1500 грн"

    mock_client = MagicMock()
    mock_client.models.generate_content = MagicMock(return_value=mock_response)
    mock_client.aio = MagicMock()
    mock_client.aio.models = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    with patch("app.services.gemini_service.get_genai_client", return_value=mock_client):
        from app.services.gemini_service import transcribe_audio

        result = await transcribe_audio(b"fake_audio", mime="audio/webm")
        assert result == "Збери кошик для офісу на 10 людей до 1500 грн"
        # Async path is preferred
        assert mock_client.aio.models.generate_content.call_count == 1


@pytest.mark.asyncio
async def test_transcribe_audio_missing_key_raises(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_MOCK_MODE", "false")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    import app.services.gemini_service as svc

    monkeypatch.setattr(svc.settings, "GEMINI_MOCK_MODE", False)
    monkeypatch.setattr(svc.settings, "GEMINI_API_KEY", "")
    svc._client = None  # type: ignore[attr-defined]

    from app.services.gemini_service import get_genai_client

    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        get_genai_client()


@pytest.mark.asyncio
async def test_parse_intent_multimodal_mock_mode_fallback(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_MOCK_MODE", "true")
    import app.services.gemini_service as svc

    monkeypatch.setattr(svc.settings, "GEMINI_MOCK_MODE", True)
    monkeypatch.setattr(svc.settings, "GEMINI_API_KEY", "")
    svc._client = None  # type: ignore[attr-defined]
    from app.services.gemini_service import parse_intent_multimodal

    result = await parse_intent_multimodal(
        user_text="Збери кошик для пікніка на 6 людей до 2500 грн, один вегетаріанець", audio_bytes=None
    )
    assert result.intent == IntentEnum.PARTY
    assert result.budget == 2500.0
    assert result.people_count == 6
    assert "vegetarian" in result.dietary_restrictions


@pytest.mark.asyncio
async def test_parse_intent_multimodal_with_mocked_client(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_MOCK_MODE", "false")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    import app.services.gemini_service as svc

    monkeypatch.setattr(svc.settings, "GEMINI_MOCK_MODE", False)
    monkeypatch.setattr(svc.settings, "GEMINI_API_KEY", "fake-key")
    svc._client = None  # type: ignore[attr-defined]

    mock_response = MagicMock()
    mock_response.text = '{"intent": "budget", "budget": 1000.0, "people_count": null, "dietary_restrictions": [], "raw_item_requests": ["молоко", "хліб", "яйця"]}'
    # also support .parsed attribute for context7 pattern
    mock_response.parsed = None

    mock_client = MagicMock()
    mock_client.models.generate_content = MagicMock(return_value=mock_response)
    mock_client.aio = MagicMock()
    mock_client.aio.models = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    with patch("app.services.gemini_service.get_genai_client", return_value=mock_client):
        from app.services.gemini_service import parse_intent_multimodal

        result = await parse_intent_multimodal(user_text="Економний кошик до 1000 грн", audio_bytes=None)
        assert result.intent == IntentEnum.BUDGET
        assert result.budget == 1000.0
        assert "молоко" in result.raw_item_requests


@pytest.mark.asyncio
async def test_parse_intent_multimodal_with_audio_bytes(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_MOCK_MODE", "false")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    import app.services.gemini_service as svc

    monkeypatch.setattr(svc.settings, "GEMINI_MOCK_MODE", False)
    monkeypatch.setattr(svc.settings, "GEMINI_API_KEY", "fake-key")
    svc._client = None  # type: ignore[attr-defined]

    mock_response = MagicMock()
    mock_response.text = '{"intent": "gourmet", "budget": 0.0, "people_count": 2, "dietary_restrictions": [], "raw_item_requests": ["сир", "вино"]}'

    mock_client = MagicMock()
    mock_client.models.generate_content = MagicMock(return_value=mock_response)
    mock_client.aio = MagicMock()
    mock_client.aio.models = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    with patch("app.services.gemini_service.get_genai_client", return_value=mock_client):
        from app.services.gemini_service import parse_intent_multimodal

        result = await parse_intent_multimodal(user_text=None, audio_bytes=b"fake_webm_bytes")
        assert result.intent == IntentEnum.GOURMET
        assert result.people_count == 2
        # Ensure generate_content called with audio part (via aio)
        call_kwargs = mock_client.aio.models.generate_content.call_args
        assert call_kwargs is not None


@pytest.mark.asyncio
async def test_parse_intent_fallback_on_client_error(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_MOCK_MODE", "false")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    import app.services.gemini_service as svc

    monkeypatch.setattr(svc.settings, "GEMINI_MOCK_MODE", False)
    monkeypatch.setattr(svc.settings, "GEMINI_API_KEY", "fake-key")
    svc._client = None  # type: ignore[attr-defined]

    mock_client = MagicMock()
    mock_client.models.generate_content = MagicMock(side_effect=RuntimeError("API error"))
    mock_client.aio = MagicMock()
    mock_client.aio.models = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(side_effect=RuntimeError("API error"))

    with patch("app.services.gemini_service.get_genai_client", return_value=mock_client):
        from app.services.gemini_service import parse_intent_multimodal

        result = await parse_intent_multimodal(
            user_text="Збери кошик для пікніка на 6 людей до 2500 грн, один вегетаріанець", audio_bytes=None
        )
        # Should fallback to regex parsing, not crash
        assert result.intent == IntentEnum.PARTY
        assert result.budget == 2500.0
