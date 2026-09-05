from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from app.enums import IntentEnum
from app.nodes.tts import format_ukrainian_speech_text, tts_node
from app.services import tts_service
from app.state import SilpoAgentState


def test_format_ukrainian_speech_text() -> None:
    text = "Я зібрав кошик для пікніка на 6 осіб на суму 2450 гривень."
    formatted = format_ukrainian_speech_text(text)
    assert "6" not in formatted
    assert "2450" not in formatted
    assert "шість" in formatted
    assert "дві тисячі" in formatted


@pytest.mark.asyncio
async def test_tts_node_mock_mode(monkeypatch) -> None:
    monkeypatch.setattr("app.nodes.tts.settings.TTS_MOCK_MODE", True)
    state: SilpoAgentState = {
        "audio_bytes": None,
        "user_text": "Пікнік",
        "intent": IntentEnum.PARTY,
        "budget": 2500.0,
        "people_count": 6,
        "dietary_restrictions": [],
        "raw_item_requests": [],
        "calculated_items": [],
        "mcp_products": [],
        "total_price": 2450.0,
        "attempts": 1,
        "max_attempts": 3,
        "is_budget_exceeded": False,
        "cart_url": "https://silpo.ua/cart/share/mock_123",
        "summary_message": "Я зібрав кошик для пікніка на 6 осіб на суму 2450 гривень.",
        "audio_url": None,
        "messages": [],
    }
    result = await tts_node(state)
    assert result["audio_url"] == "/static/audio/mock_response.mp3"
    assert "2450" not in result["summary_message"]


@pytest.mark.asyncio
async def test_tts_node_disabled_no_mock(monkeypatch) -> None:
    monkeypatch.setattr("app.nodes.tts.settings.TTS_ENABLED", False)
    monkeypatch.setattr("app.nodes.tts.settings.TTS_MOCK_MODE", False)
    state: SilpoAgentState = {
        "audio_bytes": None,
        "user_text": "Пікнік",
        "intent": IntentEnum.PARTY,
        "budget": 2500.0,
        "people_count": 6,
        "dietary_restrictions": [],
        "raw_item_requests": [],
        "calculated_items": [],
        "mcp_products": [],
        "total_price": 2450.0,
        "attempts": 1,
        "max_attempts": 3,
        "is_budget_exceeded": False,
        "cart_url": "https://silpo.ua/cart/share/mock_123",
        "summary_message": "Я зібрав кошик для пікніка на 6 осіб на суму 2450 гривень.",
        "audio_url": None,
        "messages": [],
    }
    result = await tts_node(state)
    assert result["audio_url"] is None
    assert len(result["summary_message"]) > 0


@pytest.mark.asyncio
async def test_tts_node_routes_to_gemini_provider(monkeypatch) -> None:
    monkeypatch.setattr("app.nodes.tts.settings.TTS_ENABLED", True)
    monkeypatch.setattr("app.nodes.tts.settings.TTS_MOCK_MODE", False)
    monkeypatch.setattr("app.nodes.tts.settings.TTS_PROVIDER", "gemini")
    generate_audio = AsyncMock(return_value="/static/audio/gemini-result.mp3")
    monkeypatch.setattr(tts_service, "generate_audio_gemini", generate_audio)

    result = await tts_node({"summary_message": "Кошик на 2 особи"})

    assert result["audio_url"] == "/static/audio/gemini-result.mp3"
    assert "2" not in result["summary_message"]
    generate_audio.assert_awaited_once()


@pytest.mark.asyncio
async def test_tts_node_keeps_summary_when_provider_fails(monkeypatch) -> None:
    monkeypatch.setattr("app.nodes.tts.settings.TTS_ENABLED", True)
    monkeypatch.setattr("app.nodes.tts.settings.TTS_MOCK_MODE", False)
    monkeypatch.setattr("app.nodes.tts.settings.TTS_PROVIDER", "gemini")
    monkeypatch.setattr(tts_service, "generate_audio_gemini", AsyncMock(side_effect=RuntimeError("provider down")))

    result = await tts_node({"summary_message": "Кошик на 2 особи"})

    assert result["audio_url"] is None
    assert result["summary_message"]


@pytest.mark.asyncio
async def test_generate_audio_gemini_saves_output_audio(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(tts_service.settings, "GEMINI_MOCK_MODE", False)
    monkeypatch.setattr(tts_service.settings, "GEMINI_API_KEY", "fake-key")
    monkeypatch.setattr(tts_service, "_get_audio_dir", lambda: tmp_path)
    response = SimpleNamespace(output_audio=SimpleNamespace(data=b"audio-bytes"))
    client = SimpleNamespace(
        aio=SimpleNamespace(models=SimpleNamespace(generate_content=AsyncMock(return_value=response)))
    )
    monkeypatch.setattr(tts_service, "get_genai_client", lambda: client)

    audio_url = await tts_service.generate_audio_gemini("Кошик на 2 особи")

    assert audio_url is not None
    assert audio_url.startswith("/static/audio/")
    assert next(iter(tmp_path.iterdir())).read_bytes() == b"audio-bytes"


@pytest.mark.asyncio
async def test_generate_audio_respeecher_posts_formatted_text(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(tts_service.settings, "RESPEECHER_API_KEY", "fake-key")
    monkeypatch.setattr(tts_service.settings, "RESPEECHER_VOICE_ID", "voice-1")
    monkeypatch.setattr(tts_service.settings, "RESPEECHER_API_URL", "https://example.test/tts")
    monkeypatch.setattr(tts_service, "_get_audio_dir", lambda: tmp_path)

    class FakeResponse:
        def __init__(self) -> None:
            self.headers = {"content-type": "audio/mpeg"}
            self.content = b"respeecher-audio"

        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def __init__(self, **kwargs) -> None:
            self.request: dict[str, object] = {}

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> None:
            return None

        async def post(self, url: str, **kwargs):
            self.request = {"url": url, **kwargs}
            return FakeResponse()

    client = FakeClient()
    monkeypatch.setattr(tts_service.httpx, "AsyncClient", lambda **kwargs: client)

    audio_url = await tts_service.generate_audio_respeecher("Кошик на 2 особи")

    assert audio_url is not None
    assert client.request["url"] == "https://example.test/tts"
    assert client.request["json"] == {"text": "Кошик на два особи", "voice_id": "voice-1"}
