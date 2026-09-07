import json
import logging
import re
from typing import Any

from google import genai
from google.genai import types

from ..common.prompts import (
    _GEMINI_INTENT_PROMPT,
    _GEMINI_TRANSCRIBE_PROMPT,
    _MOCK_TRANSCRIPTION,
)
from ..config import settings
from ..intent_schema import ParsedIntentSchema, extract_intent_fallback

logger = logging.getLogger(__name__)


def get_genai_client() -> genai.Client:
    """Create a Gemini client for the current operation."""
    if settings.GEMINI_MOCK_MODE:
        if not settings.GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is not set (mock mode needs no real calls, but client requested)")
    elif not settings.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set and GEMINI_MOCK_MODE is False")
    return genai.Client(api_key=settings.GEMINI_API_KEY)


async def _agenerate(
    *,
    model: str,
    contents: list[Any],
    config: types.GenerateContentConfig,
) -> types.GenerateContentResponse:
    """Pure-async Gemini call via client.aio. No sync fallback (decision #2)."""
    client = get_genai_client()
    return await client.aio.models.generate_content(
        model=model,
        contents=contents,
        config=config,
    )


def _extract_json_object(raw: str) -> str:
    """Extracts first {...} JSON object, tolerating markdown fences."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            return match.group(0)
    return cleaned


async def transcribe_audio(audio_bytes: bytes, mime: str = "audio/webm") -> str:
    """Transcribes audio_bytes via Gemini AsyncClient. Fallback to hardcoded mock on error or mock mode."""
    if not audio_bytes:
        return ""

    if settings.GEMINI_MOCK_MODE or not settings.GEMINI_API_KEY:
        logger.debug("Gemini transcribe mock mode, returning fallback")
        return _MOCK_TRANSCRIPTION

    try:
        contents: list[Any] = [
            types.Part.from_bytes(data=audio_bytes, mime_type=mime),
            _GEMINI_TRANSCRIBE_PROMPT,
        ]
        logger.info("Gemini transcribe start model=%s mime=%s bytes=%d", settings.GEMINI_MODEL, mime, len(audio_bytes))
        # Pure async via client.aio per https://googleapis.github.io/python-genai/
        response = await _agenerate(
            model=settings.GEMINI_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=0.0,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            ),
        )
        text = response.text
        if text and text.strip():
            logger.info("Gemini transcribe success chars=%d", len(text.strip()))
            return text.strip()
        logger.warning("Gemini transcribe returned empty text, using fallback")
        return _MOCK_TRANSCRIPTION
    except Exception as exc:  # noqa: BLE001 - broad for network/billing fallback
        logger.warning("Gemini transcribe failed: %s, using fallback", exc)
        return _MOCK_TRANSCRIPTION


async def choose_picker_candidate(
    candidates: list[dict[str, Any]],
    remaining: float,
    goal: str,
) -> int | None:
    """Asks Gemini to choose one candidate index, or None to fall back to greedy scoring."""
    if settings.GEMINI_MOCK_MODE or not settings.GEMINI_API_KEY or not candidates:
        return None
    try:
        lines = [
            f"{i}. {c.get('title', '?')} — {c.get('price', '?')} грн x{c.get('quantity', 1)}"
            for i, c in enumerate(candidates)
        ]
        prompt = (
            "Ти асистент Silpo Smart Shopper. Ціль: " + goal + ". "
            f"Залишок бюджету: {remaining:.2f} грн. Обери один індекс зі списку, "
            'який найкраще відповідає цілі. Відповідай JSON строго {"index": N}.\n' + "\n".join(lines)
        )
        response = await _agenerate(
            model=settings.GEMINI_MODEL,
            contents=[prompt],
            config=types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json",
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            ),
        )
        text = response.text
        if not text or not text.strip():
            return None
        index = int(json.loads(_extract_json_object(text)).get("index", -1))
        return index if 0 <= index < len(candidates) else None
    except Exception as exc:  # noqa: BLE001 - advisor failure must fall back to greedy
        logger.debug("Gemini picker advisor failed, using greedy fallback: %s", exc)
        return None


def _sanitize_seed(data: Any) -> list[dict[str, Any]] | None:
    """Validates an LLM-produced seed list; None means keep the planner fallback."""
    if not isinstance(data, list) or not data:
        return None
    seed: list[dict[str, Any]] = []
    for entry in data[:10]:
        if not isinstance(entry, dict):
            continue
        query = entry.get("query")
        if not isinstance(query, str) or not query.strip():
            continue
        try:
            quantity = int(entry.get("quantity", 1) or 1)
        except (TypeError, ValueError):
            quantity = 1
        category = entry.get("category")
        seed.append(
            {
                "query": query.strip(),
                "category": category if isinstance(category, str) and category else "general",
                "quantity": max(1, quantity),
                "prefer_private_label": bool(entry.get("prefer_private_label", False)),
            }
        )
    return seed or None


async def formulate_picker_queries(
    goal: str,
    fallback_seed: list[dict[str, Any]],
) -> list[dict[str, Any]] | None:
    """Asks Gemini to build goal-derived search queries; None means keep the planner fallback."""
    if settings.GEMINI_MOCK_MODE or not settings.GEMINI_API_KEY:
        return None
    try:
        prompt = (
            "Ти асистент Silpo Smart Shopper. Ціль: " + goal + ". "
            "Сформуй пошукові запити товарів українською (2-6 шт) для цієї цілі. "
            "Зберігай уточнення з цілі (свіжі, безалкогольне) у запитах. "
            'Відповідай JSON строго списком [{"query": "...", '
            '"category": "meat|vegetables|drinks|accessories|general", "quantity": N}]. '
            "Категорії: курка/м'ясо — meat, гриби — vegetables, овочі — vegetables, "
            'напої — drinks, вугілля — accessories. Приклад: "гриль з куркою, свіжими печерицями та безалкогольним пивом" -> '
            '[{"query": "Курка для гриля", "category": "meat", "quantity": 2}, '
            '{"query": "Печериці свіжі", "category": "vegetables", "quantity": 1}, '
            '{"query": "Овочі для гриля", "category": "vegetables", "quantity": 2}, '
            '{"query": "Пиво безалкогольне", "category": "drinks", "quantity": 2}].'
        )
        response = await _agenerate(
            model=settings.GEMINI_MODEL,
            contents=[prompt],
            config=types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json",
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            ),
        )
        text = response.text
        if not text or not text.strip():
            return None
        return _sanitize_seed(json.loads(_extract_json_object(text)))
    except Exception as exc:  # noqa: BLE001 - formulation failure must fall back to planner seed
        logger.debug("Gemini query formulation failed, using planner fallback: %s", exc)
        return None


async def judge_picker_candidate(
    query: str,
    candidate: dict[str, Any],
    goal: str,
) -> dict[str, Any]:
    """Asks Gemini whether a candidate matches the query and goal.

    Fail-open: any failure returns accept, so the deterministic gate and greedy
    scoring still decide exactly as without the judge.
    """
    accept = {"verdict": "accept", "reason": "", "suggested_query": None}
    if settings.GEMINI_MOCK_MODE or not settings.GEMINI_API_KEY:
        return accept
    try:
        request_line = (
            f'Запит: "{query}". '
            if query.strip()
            else "Запит відсутній (акційне доповнення до кошика) — оцінюй лише відповідність цілі. "
        )
        prompt = (
            "Ти асистент Silpo Smart Shopper. " + request_line + "Ціль: " + goal + ". "
            f'Кандидат: "{candidate.get("title", "?")}" — {candidate.get("price", "?")} грн '
            f"x{candidate.get('quantity', 1)}. Чи відповідає кандидат запиту та цілі? "
            "Відхиляй невідповідності: засіб гігієни замість вугілля, свинина замість курки, "
            "алкогольне замість безалкогольного, не ті овочі для гриля. "
            "Оцінюй відповідність саме цілі: відхиляй категорії, яких ціль не містить "
            "(риба та морепродукти, алкоголь при безалкогольній цілі, засоби гігієни "
            "для продуктового кошика), і порушення уточнень (мариновані замість свіжих, "
            "алкогольні замість безалкогольних). "
            'Відповідай JSON строго {"verdict": "accept"|"reject", "reason": "...", '
            '"suggested_query": "..."|null}.'
        )
        response = await _agenerate(
            model=settings.GEMINI_MODEL,
            contents=[prompt],
            config=types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json",
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            ),
        )
        text = response.text
        if not text or not text.strip():
            return accept
        data = json.loads(_extract_json_object(text))
        if not isinstance(data, dict) or data.get("verdict") not in ("accept", "reject"):
            return accept
        suggested = data.get("suggested_query")
        return {
            "verdict": data["verdict"],
            "reason": str(data.get("reason", "")),
            "suggested_query": suggested if isinstance(suggested, str) and suggested.strip() else None,
        }
    except Exception as exc:  # noqa: BLE001 - judge failure must fall back to greedy accept
        logger.debug("Gemini picker judge failed, accepting greedily: %s", exc)
        return accept


async def parse_intent_multimodal(
    user_text: str | None,
    audio_bytes: bytes | None,
) -> ParsedIntentSchema:
    """Multimodal intent parsing via Gemini structured output. Falls back to regex."""
    if settings.GEMINI_MOCK_MODE or not settings.GEMINI_API_KEY:
        text = user_text or ""
        if audio_bytes and not text.strip():
            text = _MOCK_TRANSCRIPTION
        if not text.strip():
            return ParsedIntentSchema()
        return extract_intent_fallback(text)

    try:
        contents: list[Any] = []

        if audio_bytes:
            mime = "audio/webm"
            contents.append(types.Part.from_bytes(data=audio_bytes, mime_type=mime))

        prompt_text = user_text or ""
        if not prompt_text.strip() and audio_bytes:
            prompt_text = "Transcribe and parse intent from audio."
        instruction = f"{_GEMINI_INTENT_PROMPT}\nUser input: {prompt_text}"
        contents.append(instruction)

        logger.info(
            "Gemini parse_intent start model=%s user_text_len=%d has_audio=%s",
            settings.GEMINI_MODEL,
            len(prompt_text),
            bool(audio_bytes),
        )
        response = await _agenerate(
            model=settings.GEMINI_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json",
                response_schema=ParsedIntentSchema,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            ),
        )
        parsed = response.parsed
        if parsed is not None and isinstance(parsed, ParsedIntentSchema):
            return parsed

        text = response.text
        if text and text.strip():
            cleaned = _extract_json_object(text)
            data = json.loads(cleaned)
            return ParsedIntentSchema.model_validate(data)

        logger.warning("Gemini parse_intent returned empty text, using fallback")
        return extract_intent_fallback(user_text or _MOCK_TRANSCRIPTION)

    except Exception as exc:  # noqa: BLE001
        logger.warning("Gemini parse_intent failed: %s, using fallback", exc)
        fallback_text = user_text or ""
        if not fallback_text.strip() and audio_bytes:
            fallback_text = _MOCK_TRANSCRIPTION
        if not fallback_text.strip():
            return ParsedIntentSchema()
        return extract_intent_fallback(fallback_text)
