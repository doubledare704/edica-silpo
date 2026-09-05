import logging
from typing import Any

from ..enums import IntentEnum
from ..intent_schema import extract_intent_fallback
from ..services import gemini_service
from ..state import SilpoAgentState

logger = logging.getLogger(__name__)


async def parse_intent_node(state: SilpoAgentState) -> dict[str, Any]:
    """Extracts structured intent via Gemini multimodal, fallback to regex."""
    user_text = state.get("user_text") or ""
    audio_bytes = state.get("audio_bytes")

    if not user_text.strip() and not audio_bytes:
        result = {
            "intent": state.get("intent") or IntentEnum.PARTY,
            "budget": state.get("budget", 0.0),
            "people_count": state.get("people_count"),
            "dietary_restrictions": state.get("dietary_restrictions", []),
            "raw_item_requests": state.get("raw_item_requests", []),
        }
        logger.info("parse_intent done source=defaults intent=%s budget=%s", result["intent"], result["budget"])
        return result

    try:
        parsed = await gemini_service.parse_intent_multimodal(
            user_text=user_text if user_text.strip() else None,
            audio_bytes=audio_bytes,
        )
    except Exception:
        logger.exception("Gemini parse_intent failed, falling back to regex")
        parsed = extract_intent_fallback(user_text or "")

    result = {
        "intent": parsed.intent,
        "budget": parsed.budget,
        "people_count": parsed.people_count,
        "dietary_restrictions": parsed.dietary_restrictions,
        "raw_item_requests": parsed.raw_item_requests,
    }
    logger.info(
        "parse_intent done intent=%s budget=%s people=%s items=%d",
        parsed.intent,
        parsed.budget,
        parsed.people_count,
        len(parsed.raw_item_requests),
    )
    return result
