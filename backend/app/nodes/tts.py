import logging
from typing import Any

from ..config import settings
from ..services import tts_service
from ..state import SilpoAgentState
from ..utils.speech import format_ukrainian_speech_text

logger = logging.getLogger(__name__)


async def tts_node(state: SilpoAgentState) -> dict[str, Any]:
    """Formats the summary and optionally generates provider-backed speech.

    Voice in, voice out: audio is generated only when the request carried
    voice input. Text requests get the text summary without an audio reply.
    """
    raw_summary = state.get("summary_message") or ""
    formatted_summary = format_ukrainian_speech_text(raw_summary)

    audio_url: str | None = None

    if state.get("audio_bytes"):
        if settings.TTS_MOCK_MODE:
            audio_url = "/static/audio/mock_response.wav"
        elif settings.TTS_ENABLED:
            try:
                if settings.TTS_PROVIDER == "gemini":
                    audio_url = await tts_service.generate_audio_gemini(formatted_summary)
                elif settings.TTS_PROVIDER == "respeecher":
                    audio_url = await tts_service.generate_audio_respeecher(formatted_summary)
                else:
                    logger.warning("Unsupported TTS provider: %s", settings.TTS_PROVIDER)
            except Exception as exc:  # noqa: BLE001 - speech must not block shopping
                logger.warning("TTS generation failed, falling back to None: %s", exc)

    logger.info("tts done audio_url=%s summary_chars=%d", audio_url, len(formatted_summary))
    return {
        "summary_message": formatted_summary,
        "audio_url": audio_url,
    }
