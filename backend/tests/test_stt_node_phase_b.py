from unittest.mock import AsyncMock, patch

import pytest
from app.state import SilpoAgentState


def _make_state(
    *,
    user_text: str | None = None,
    audio_bytes: bytes | None = None,
) -> SilpoAgentState:
    return {
        "audio_bytes": audio_bytes,
        "user_text": user_text,
        "intent": None,
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
async def test_stt_node_prefers_user_text_over_audio(monkeypatch) -> None:
    """User corrected text wins, gemini not called."""
    import app.services.gemini_service as svc

    monkeypatch.setattr(svc.settings, "GEMINI_MOCK_MODE", False)
    monkeypatch.setattr(svc.settings, "GEMINI_API_KEY", "fake-key")

    mock_transcribe = AsyncMock(return_value="transcribed via gemini")
    with patch("app.services.gemini_service.transcribe_audio", mock_transcribe):
        from app.nodes.stt import stt_node

        state = _make_state(user_text="Збери кошик для офісу", audio_bytes=b"webm_bytes")
        result = await stt_node(state)
        assert result["user_text"] == "Збери кошик для офісу"
        mock_transcribe.assert_not_called()


@pytest.mark.asyncio
async def test_stt_node_transcribes_via_gemini(monkeypatch) -> None:
    import app.services.gemini_service as svc

    monkeypatch.setattr(svc.settings, "GEMINI_MOCK_MODE", False)
    monkeypatch.setattr(svc.settings, "GEMINI_API_KEY", "fake-key")

    mock_transcribe = AsyncMock(return_value="Збери кошик для офісу на 10 людей до 1500 грн")
    with patch("app.services.gemini_service.transcribe_audio", mock_transcribe):
        from app.nodes.stt import stt_node

        state = _make_state(user_text=None, audio_bytes=b"\x1a\x45\xdf\xa3 fake webm")
        result = await stt_node(state)
        assert result["user_text"] == "Збери кошик для офісу на 10 людей до 1500 грн"
        mock_transcribe.assert_called_once()
        # Should detect webm mime
        call_kwargs = mock_transcribe.call_args
        assert call_kwargs is not None
        args, kwargs = call_kwargs
        # transcribe_audio(audio_bytes, mime="audio/webm")
        mime_arg = kwargs.get("mime") or (args[1] if len(args) > 1 else None)
        assert mime_arg == "audio/webm"


@pytest.mark.asyncio
async def test_stt_node_detects_wav_mime(monkeypatch) -> None:
    import app.services.gemini_service as svc

    monkeypatch.setattr(svc.settings, "GEMINI_MOCK_MODE", False)
    monkeypatch.setattr(svc.settings, "GEMINI_API_KEY", "fake-key")

    mock_transcribe = AsyncMock(return_value="transcribed wav")
    with patch("app.services.gemini_service.transcribe_audio", mock_transcribe):
        from app.nodes.stt import stt_node

        # RIFF header for wav
        state = _make_state(user_text=None, audio_bytes=b"RIFF\xff\xffWAVE")
        result = await stt_node(state)
        assert result["user_text"] == "transcribed wav"
        mime_arg = (
            mock_transcribe.call_args[0][1]
            if len(mock_transcribe.call_args[0]) > 1
            else mock_transcribe.call_args[1].get("mime")
        )
        assert mime_arg == "audio/wav"


@pytest.mark.asyncio
async def test_stt_node_mock_mode_returns_fallback(monkeypatch) -> None:
    import app.services.gemini_service as svc

    monkeypatch.setattr(svc.settings, "GEMINI_MOCK_MODE", True)
    monkeypatch.setattr(svc.settings, "GEMINI_API_KEY", "")

    from app.nodes.stt import stt_node

    state = _make_state(user_text=None, audio_bytes=b"fake")
    result = await stt_node(state)
    assert result["user_text"] is not None
    assert "пікніка" in result["user_text"] or "Збери" in result["user_text"]


@pytest.mark.asyncio
async def test_stt_node_handles_empty_input() -> None:
    from app.nodes.stt import stt_node

    state = _make_state(user_text=None, audio_bytes=None)
    result = await stt_node(state)
    assert result.get("user_text") in (None, "")
