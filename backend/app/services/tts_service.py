import logging
import uuid
from pathlib import Path

import httpx
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
        response = await client.aio.models.generate_content(
            model=settings.GEMINI_TTS_MODEL,
            contents=formatted,
            config=types.GenerateContentConfig(
                response_modalities=["audio"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="kore"))
                ),
            ),
        )
        audio_bytes = _extract_audio_bytes(response)
        if audio_bytes is None:
            logger.warning("Gemini TTS returned no audio data")
            return None
        return _save_audio_bytes(audio_bytes)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Gemini TTS failed: %s", exc)
        return None


def _extract_audio_bytes(response: types.GenerateContentResponse) -> bytes | None:
    for candidate in response.candidates or []:
        content = candidate.content
        for part in (content.parts or []) if content else []:
            inline = part.inline_data
            data = inline.data if inline else None
            if data:
                if isinstance(data, str):
                    import base64

                    return base64.b64decode(data)
                return bytes(data)
    return None


async def generate_audio_respeecher(text: str) -> str | None:
    """Generates audio via the Respeecher Bytes API.

    Posts the formatted transcript and returns a saved WAV file URL, or None
    when config is missing or the API returns a non-audio payload.
    """
    formatted = format_ukrainian_speech_text(text)
    if not formatted.strip() or not settings.RESPEECHER_API_KEY or not settings.RESPEECHER_VOICE_ID:
        return None

    endpoint = f"https://api.respeecher.com/v1/public/tts/{settings.RESPEECHER_MODEL}/tts/bytes"
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            endpoint,
            headers={"X-API-Key": settings.RESPEECHER_API_KEY, "Content-Type": "application/json"},
            json={
                "transcript": formatted,
                "voice": {"id": settings.RESPEECHER_VOICE_ID},
                "output_format": {"sample_rate": 22050},
            },
        )
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if "json" in content_type or content_type.startswith("text/"):
            logger.warning("Respeecher returned non-audio response (%s)", content_type)
            return None
        response_content = response.content
        if not response_content.startswith(b"RIFF"):
            logger.warning("Respeecher returned an invalid WAV payload")
            return None

    return _save_audio_bytes(response_content, suffix=".wav")


def _save_audio_bytes(audio_bytes: bytes, *, suffix: str = ".mp3") -> str | None:
    try:
        audio_dir = _get_audio_dir()
        audio_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{uuid.uuid4().hex[:8]}{suffix}"
        file_path = audio_dir / filename
        file_path.write_bytes(audio_bytes if isinstance(audio_bytes, bytes) else bytes(audio_bytes))
        return f"/static/audio/{filename}"
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to save TTS audio: %s", exc)
        return None
