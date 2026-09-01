from app.nodes.stt import stt_node
from app.state import AgentState


def test_stt_node_preserves_existing_user_text() -> None:
    initial_state: AgentState = {
        "audio_bytes": None,
        "user_text": "Збери кошик для вечірки",
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
    result = stt_node(initial_state)
    assert result["user_text"] == "Збери кошик для вечірки"


def test_stt_node_transcribes_audio_bytes_mock() -> None:
    initial_state: AgentState = {
        "audio_bytes": b"fake_audio_content",
        "user_text": None,
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
    result = stt_node(initial_state)
    assert result["user_text"] is not None
    assert len(result["user_text"]) > 0


def test_stt_node_handles_empty_input() -> None:
    initial_state: AgentState = {
        "audio_bytes": None,
        "user_text": None,
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
    result = stt_node(initial_state)
    assert result.get("user_text") in (None, "")
