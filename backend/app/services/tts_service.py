import logging
import uuid
from pathlib import Path
from typing import Any

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


def _extract_audio_bytes(response: Any) -> bytes | None:
    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", None) or []:
            inline = getattr(part, "inline_data", None)
            data = getattr(inline, "data", None) if inline else None
            if data:
                if isinstance(data, str):
                    import base64

                    return base64.b64decode(data)
                return bytes(data)

    output_audio = getattr(response, "output_audio", None)
    data = getattr(output_audio, "data", None) if output_audio else None
    if isinstance(data, str):
        import base64

        return base64.b64decode(data)
    if data:
        return bytes(data)
    return None


async def generate_audio_respeecher(text: str) -> str | None:
    """Generates audio through a configured Respeecher HTTP endpoint."""
    formatted = format_ukrainian_speech_text(text)
    if not formatted.strip() or not settings.RESPEECHER_API_KEY or not settings.RESPEECHER_VOICE_ID:
        return None

    endpoint = getattr(settings, "RESPEECHER_API_URL", "")
    if not endpoint:
        logger.warning("Respeecher TTS endpoint is not configured")
        return None

    response_content: bytes
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            endpoint,
            headers={"Authorization": f"Bearer {settings.RESPEECHER_API_KEY}"},
            json={"text": formatted, "voice_id": settings.RESPEECHER_VOICE_ID},
        )
        response.raise_for_status()
        if "application/json" in response.headers.get("content-type", ""):
            payload = response.json()
            audio_url = payload.get("audio_url")
            if audio_url:
                return str(audio_url)
            encoded_audio = payload.get("audio_base64")
            if not encoded_audio:
                raise ValueError("Respeecher response contains no audio")
            import base64

            response_content = base64.b64decode(encoded_audio)
        else:
            response_content = response.content

    return _save_audio_bytes(response_content)


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
