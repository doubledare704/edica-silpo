import logging
import uuid
from pathlib import Path

from google.genai import types

from ..config import settings
from ..utils.speech import format_ukrainian_speech_text
from .gemini_service import get_genai_client

logger = logging.getLogger(__name__)


def _get_audio_dir() -> Path:
    # backend/app/services -> backend/static/audio
    return Path(__file__).resolve().parent.parent.parent / "static" / "audio"


async def generate_audio_gemini(text: str) -> str | None:
    """Generates audio via Gemini TTS preview. Returns /static/audio/... URL or None on failure."""
    formatted = format_ukrainian_speech_text(text)
    if not formatted.strip():
        return None

    if settings.GEMINI_MOCK_MODE or not settings.GEMINI_API_KEY:
        logger.debug("Gemini TTS mock mode or missing key, returning None")
        return None

    try:
        client = get_genai_client()
        response = client.models.generate_content(
            model=settings.GEMINI_TTS_MODEL,
            contents=formatted,
            config=types.GenerateContentConfig(
                response_modalities=["audio"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="kore"))
                ),
            ),
        )
        # Response may contain inline_data or audio bytes
        # Try common locations
        candidates = getattr(response, "candidates", None)
        if candidates:
            # Look for inline data
            for cand in candidates:
                content = getattr(cand, "content", None)
                parts = getattr(content, "parts", None) if content else None
                if parts:
                    for part in parts:
                        inline = getattr(part, "inline_data", None)
                        if inline and getattr(inline, "data", None):
                            audio_bytes = inline.data  # type: ignore[attr-defined]
                            # inline.data may be base64 string or bytes
                            if isinstance(audio_bytes, str):
                                import base64

                                audio_bytes = base64.b64decode(audio_bytes)
                            return _save_audio_bytes(audio_bytes)

        # Fallback: try response.candidates[0].content.parts[0].inline_data
        # Alternative shape via SDK tests
        logger.warning("Gemini TTS returned no inline_data, checking alternative")
        # Some SDK versions return bytes directly via response
        # If nothing found, return None
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("Gemini TTS failed: %s", exc)
        return None


def _save_audio_bytes(audio_bytes: bytes) -> str | None:
    try:
        audio_dir = _get_audio_dir()
        audio_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{uuid.uuid4().hex[:8]}.mp3"
        file_path = audio_dir / filename
        file_path.write_bytes(audio_bytes if isinstance(audio_bytes, bytes) else bytes(audio_bytes))
        return f"/static/audio/{filename}"
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to save TTS audio: %s", exc)
        return None
