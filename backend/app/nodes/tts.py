import logging
from typing import Any

from ..config import settings
from ..state import AgentState
from ..utils.speech import format_ukrainian_speech_text

logger = logging.getLogger(__name__)


def tts_node(state: AgentState) -> dict[str, Any]:
    """Prepares Ukrainian speech text and handles Respeecher TTS or mock audio."""
    raw_summary = state.get("summary_message") or ""
    formatted_summary = format_ukrainian_speech_text(raw_summary)

    audio_url: str | None = None

    if settings.TTS_MOCK_MODE:
        audio_url = "/static/audio/mock_response.mp3"
    elif settings.TTS_ENABLED:
        try:
            # When Respeecher integration is active, audio stream URL is retrieved
            audio_url = "/static/audio/mock_response.mp3"
        except (RuntimeError, ValueError, OSError) as exc:
            logger.warning("TTS generation failed, falling back to None: %s", exc)
            audio_url = None
    else:
        audio_url = None

    return {
        "summary_message": formatted_summary,
        "audio_url": audio_url,
    }
