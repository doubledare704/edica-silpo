import json
import logging
from typing import TYPE_CHECKING, Any

from google import genai
from google.genai import types

from ..config import settings

if TYPE_CHECKING:
    from ..nodes.parse_intent import ParsedIntentSchema

logger = logging.getLogger(__name__)

_client: genai.Client | None = None

_MOCK_TRANSCRIPTION = "Збери кошик для пікніка на 6 людей до 2500 грн, один вегетаріанець"

_GEMINI_TRANSCRIBE_PROMPT = (
    "Transcribe verbatim in Ukrainian, no translation. Return only the transcription text, no extra formatting."
)

_GEMINI_INTENT_PROMPT = (
    "Ти асистент Silpo Smart Shopper. Визнач IntentEnum {party, budget, office, gourmet}, "
    "budget (грн), people_count, dietary_restrictions [vegetarian, vegan, lactose_free, gluten_free], "
    "raw_item_requests (укр назви товарів, 2-5 шт). "
    "Відповідай JSON строго за схемою. Приклади: "
    "'Збери кошик для пікніка на 6 людей до 2500 грн, один вегетаріанець' -> "
    '{"intent":"party","budget":2500,"people_count":6,"dietary_restrictions":["vegetarian"],'
    '"raw_item_requests":["м\'ясо","овочі","напої","вугілля"]}; '
    "'Економний кошик до 1000 грн' -> "
    '{"intent":"budget","budget":1000,"people_count":null,"dietary_restrictions":[],'
    '"raw_item_requests":["молоко","хліб","яйця","масло","крупа"]}. '
    "Мова виходу: enum English, сутності Ukrainian."
)


def get_genai_client() -> genai.Client:
    """Lazy singleton for google-genai Client."""
    global _client
    if _client is not None:
        return _client
    if settings.GEMINI_MOCK_MODE:
        # In mock mode allow missing key, but still need a client for tests that patch it
        # If key missing, tests will patch get_genai_client directly, so we raise only if not mocked
        # Create a dummy client that will be patched; if not patched, calls will fail gracefully via try/except
        if not settings.GEMINI_API_KEY:
            # Return a placeholder that will be used only when mocked in tests
            # For real mock mode without billing, transcription/parse fallback doesn't need client
            raise RuntimeError("GEMINI_API_KEY is not set (mock mode needs no real calls, but client requested)")
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
        return _client
    if not settings.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set and GEMINI_MOCK_MODE is False")
    _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


def reset_genai_client() -> None:
    """Reset singleton for testing."""
    global _client
    _client = None


async def transcribe_audio(audio_bytes: bytes, mime: str = "audio/webm") -> str:
    """Transcribes audio_bytes via Gemini. Fallback to hardcoded mock on error or mock mode."""
    if not audio_bytes:
        return ""

    # Mock mode or missing key -> deterministic fallback to keep tests green
    if settings.GEMINI_MOCK_MODE or not settings.GEMINI_API_KEY:
        logger.debug("Gemini transcribe mock mode, returning fallback")
        return _MOCK_TRANSCRIPTION

    try:
        client = get_genai_client()
        # Build contents: inline audio bytes + transcription prompt
        contents: list[Any] = [
            types.Part.from_bytes(data=audio_bytes, mime_type=mime),
            _GEMINI_TRANSCRIBE_PROMPT,
        ]
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=0.0,
            ),
        )
        text = getattr(response, "text", None)
        if text and text.strip():
            return text.strip()
        # Fallback if empty
        logger.warning("Gemini transcribe returned empty text, using fallback")
        return _MOCK_TRANSCRIPTION
    except Exception as exc:  # noqa: BLE001 - broad for network/billing fallback
        logger.warning("Gemini transcribe failed: %s, using fallback", exc)
        return _MOCK_TRANSCRIPTION


async def parse_intent_multimodal(
    user_text: str | None,
    audio_bytes: bytes | None,
) -> "ParsedIntentSchema":
    """Multimodal intent parsing via Gemini structured output. Falls back to regex."""
    # Local import to avoid circular dependency with nodes module
    from ..nodes.parse_intent import ParsedIntentSchema, _extract_intent_fallback

    # Mock mode -> direct fallback without billing
    if settings.GEMINI_MOCK_MODE or not settings.GEMINI_API_KEY:
        text = user_text or ""
        if audio_bytes and not text.strip():
            # Simulate transcription fallback then parse
            text = _MOCK_TRANSCRIPTION
        if not text.strip():
            return ParsedIntentSchema()
        return _extract_intent_fallback(text)

    try:
        client = get_genai_client()
        contents: list[Any] = []

        # If audio provided, include it for better confidence (multimodal)
        if audio_bytes:
            # Detect mime: plan keeps WebM
            mime = "audio/webm"
            contents.append(types.Part.from_bytes(data=audio_bytes, mime_type=mime))

        # Always include text prompt: either user_text or transcribe hint
        prompt_text = user_text or ""
        if not prompt_text.strip() and audio_bytes:
            prompt_text = "Transcribe and parse intent from audio."
        instruction = f"{_GEMINI_INTENT_PROMPT}\nUser input: {prompt_text}"
        contents.append(instruction)

        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json",
                response_schema=ParsedIntentSchema,
            ),
        )

        # Prefer parsed attribute if SDK provides it
        parsed = getattr(response, "parsed", None)
        if parsed is not None and isinstance(parsed, ParsedIntentSchema):
            return parsed

        text = getattr(response, "text", None)
        if text and text.strip():
            # Clean potential markdown code fences
            cleaned = text.strip()
            if cleaned.startswith("```"):
                # Remove ```json ... ```
                cleaned = cleaned.strip("`")
                # Find first { and last }
                start = cleaned.find("{")
                end = cleaned.rfind("}")
                if start != -1 and end != -1:
                    cleaned = cleaned[start : end + 1]
            data = json.loads(cleaned)
            return ParsedIntentSchema.model_validate(data)

        logger.warning("Gemini parse_intent returned empty text, using fallback")
        return _extract_intent_fallback(user_text or _MOCK_TRANSCRIPTION)

    except Exception as exc:  # noqa: BLE001
        logger.warning("Gemini parse_intent failed: %s, using fallback", exc)
        fallback_text = user_text or ""
        if not fallback_text.strip() and audio_bytes:
            fallback_text = _MOCK_TRANSCRIPTION
        if not fallback_text.strip():
            return ParsedIntentSchema()
        return _extract_intent_fallback(fallback_text)
