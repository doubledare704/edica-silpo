from app.enums import IntentEnum
from app.nodes.tts import format_ukrainian_speech_text, tts_node
from app.state import AgentState


def test_format_ukrainian_speech_text() -> None:
    text = "Я зібрав кошик для пікніка на 6 осіб на суму 2450 гривень."
    formatted = format_ukrainian_speech_text(text)
    assert "6" not in formatted
    assert "2450" not in formatted
    assert "шість" in formatted
    assert "дві тисячі" in formatted


def test_tts_node_mock_mode(monkeypatch) -> None:
    monkeypatch.setattr("app.nodes.tts.settings.TTS_MOCK_MODE", True)
    state: AgentState = {
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
    result = tts_node(state)
    assert result["audio_url"] == "/static/audio/mock_response.mp3"
    assert "2450" not in result["summary_message"]


def test_tts_node_disabled_no_mock(monkeypatch) -> None:
    monkeypatch.setattr("app.nodes.tts.settings.TTS_ENABLED", False)
    monkeypatch.setattr("app.nodes.tts.settings.TTS_MOCK_MODE", False)
    state: AgentState = {
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
    result = tts_node(state)
    assert result["audio_url"] is None
    assert len(result["summary_message"]) > 0
