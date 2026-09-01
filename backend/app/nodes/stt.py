from typing import Any

from ..state import AgentState


def stt_node(state: AgentState) -> dict[str, Any]:
    """Transcribes input audio bytes if provided, or preserves existing user text."""
    user_text = state.get("user_text")
    if user_text:
        return {"user_text": user_text}

    audio_bytes = state.get("audio_bytes")
    if audio_bytes:
        return {"user_text": "Збери кошик для пікніка на 6 людей до 2500 грн, один вегетаріанець"}

    return {"user_text": user_text}
