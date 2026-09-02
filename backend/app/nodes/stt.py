from typing import Any

from ..services import gemini_service
from ..state import AgentState


def _detect_mime(audio_bytes: bytes) -> str:
    """Detects mime from header bytes. WebM (EBML) vs WAV (RIFF). Defaults to audio/webm."""
    if audio_bytes.startswith(b"\x1a\x45\xdf\xa3"):
        return "audio/webm"
    if audio_bytes.startswith(b"RIFF"):
        return "audio/wav"
    # Frontend records audio/webm, so default to that
    return "audio/webm"


async def stt_node(state: AgentState) -> dict[str, Any]:
    """Transcribes input audio bytes via Gemini, or preserves existing user text.

    Priority: user_text (user correction) -> Gemini transcribe -> None.
    Keeps WebM, detects mime from header bytes.
    """
    user_text = state.get("user_text")
    if user_text and user_text.strip():
        return {"user_text": user_text}

    audio_bytes = state.get("audio_bytes")
    if audio_bytes:
        mime = _detect_mime(audio_bytes)
        transcribed = await gemini_service.transcribe_audio(audio_bytes, mime=mime)
        # transcribe_audio already falls back to hardcoded mock on error/mock mode
        if transcribed and transcribed.strip():
            return {"user_text": transcribed}
        # Fallback if transcribe returns empty
        return {"user_text": "Збери кошик для пікніка на 6 людей до 2500 грн, один вегетаріанець"}

    return {"user_text": user_text}
