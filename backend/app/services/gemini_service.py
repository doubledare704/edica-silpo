import json
import logging
import re
from typing import Any

from google import genai
from google.genai import types

from ..common.prompts import (
    _GEMINI_INTENT_PROMPT,
    _GEMINI_TRANSCRIBE_PROMPT,
    _GEMINI_WEEKLY_MEAL_PROMPT,
    _MOCK_TRANSCRIPTION,
)
from ..config import settings
from ..intent_schema import ParsedIntentSchema, extract_intent_fallback

logger = logging.getLogger(__name__)

#: Sentinel returned by choose_picker_candidate when the advisor vetoes every candidate.
ADVISOR_VETO = -1

#: Substrings marking a Gemini failure as worth failing over to the next model.
#: 429 = per-minute/daily quota spent, 503/504 = transient overload. Anything
#: else (400/401/403, bad payload or key) fails fast without touching fallbacks.
_RETRYABLE_MARKERS = (
    "429",
    "resource_exhausted",
    "rate_limit",
    "quota",
    "too_many_requests",
    "503",
    "unavailable",
    "service_unavailable",
    "504",
    "deadline_exceeded",
)


def parse_model_list(raw: str) -> list[str]:
    """Splits a comma-separated model list, trimming and deduping in order."""
    seen: set[str] = set()
    models: list[str] = []
    for part in raw.split(","):
        name = part.strip()
        if name and name not in seen:
            seen.add(name)
            models.append(name)
    return models


def _dedup_models(models: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for name in models:
        cleaned = name.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            unique.append(cleaned)
    return unique


def get_flash_models() -> list[str]:
    """Primary plus Flash-Lite fallbacks for audio/structured/grounded calls."""
    return _dedup_models([settings.GEMINI_MODEL, *parse_model_list(settings.GEMINI_MODEL_FALLBACKS)])


def get_plain_models() -> list[str]:
    """Flash chain plus plain-text fallbacks (e.g. Gemma) for bare-JSON calls."""
    return _dedup_models([*get_flash_models(), *parse_model_list(settings.GEMINI_MODEL_FALLBACKS_PLAIN)])


def _is_retryable_error(exc: Exception) -> bool:
    """True when the next model in the chain deserves a try (quota/overload).

    A dead model code (`model_not_found`) also fails over: per the API docs
    the client should fall back to a different model in that case.
    """
    haystack = f"{type(exc).__name__} {exc}".lower()
    return "model_not_found" in haystack or any(marker in haystack for marker in _RETRYABLE_MARKERS)


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
    models: list[str] | None = None,
) -> types.GenerateContentResponse:
    """Pure-async Gemini call via client.aio. No sync fallback (decision #2).

    Ordered failover: tries `models` in order (default `[model]`), moving to
    the next model only on retryable quota/overload errors. Non-retryable
    errors raise immediately; exhausted chains raise the last error so
    callers keep their deterministic fallbacks.
    """
    chain = _dedup_models(models) if models else [model]
    if not chain:
        chain = [model]
    client = get_genai_client()
    last_exc: Exception | None = None
    for attempt, candidate in enumerate(chain):
        try:
            return await client.aio.models.generate_content(
                model=candidate,
                contents=contents,
                config=config,
            )
        except Exception as exc:
            last_exc = exc
            if _is_retryable_error(exc) and attempt < len(chain) - 1:
                logger.warning(
                    "Gemini model %s exhausted (%s), failing over to %s",
                    candidate,
                    exc,
                    chain[attempt + 1],
                )
                continue
            raise
    raise last_exc if last_exc is not None else RuntimeError("Gemini model chain is empty")


def _extract_json_object(raw: str) -> str:
    """Extracts first {...} JSON object, tolerating markdown fences."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            return match.group(0)
    return cleaned


def _extract_json_list(raw: str) -> str:
    """Extracts the first [...] JSON list, tolerating fences and surrounding prose."""
    cleaned = raw.strip()
    if cleaned.startswith("["):
        return cleaned
    match = re.search(r"\[.*\]", cleaned, re.DOTALL)
    return match.group(0) if match else cleaned


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
            models=get_flash_models(),
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
    query: str = "",
) -> int | None:
    """Asks Gemini to choose one candidate index, or None to fall back to greedy scoring.

    The original search query is passed so the advisor judges fit against what was
    asked, not just the goal. Returns ADVISOR_VETO when no candidate fits.
    """
    if settings.GEMINI_MOCK_MODE or not settings.GEMINI_API_KEY or not candidates:
        return None
    try:
        lines = [
            f"{i}. {c.get('title', '?')} — {c.get('price', '?')} грн x{c.get('quantity', 1)}"
            for i, c in enumerate(candidates)
        ]
        request_line = f'Початковий запит: "{query}". ' if query.strip() else ""
        prompt = (
            "Ти асистент Silpo Smart Shopper. " + request_line + "Ціль: " + goal + ". "
            f"Залишок бюджету: {remaining:.2f} грн. Обери один індекс зі списку, "
            "який найкраще відповідає запиту та цілі. "
            "Ціна НЕ є критерієм вибору: не відхиляй кандидатів через низьку ціну, бюджет контролюється окремо. "
            'Відповідай JSON строго {"index": N} або {"reject": true}, якщо жоден кандидат не підходить.\n'
            + "\n".join(lines)
        )
        response = await _agenerate(
            model=settings.GEMINI_MODEL,
            models=get_plain_models(),
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
        data = json.loads(_extract_json_object(text))
        if isinstance(data, dict) and data.get("reject") is True:
            return ADVISOR_VETO
        index = int(data.get("index", -1)) if isinstance(data, dict) else -1
        return index if 0 <= index < len(candidates) else None
    except Exception as exc:  # noqa: BLE001 - advisor failure must fall back to greedy
        logger.debug("Gemini picker advisor failed, using greedy fallback: %s", exc)
        return None


def _sanitize_seed(data: Any, note_keys: tuple[str, ...] = ()) -> list[dict[str, Any]] | None:
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
        item = {
            "query": query.strip(),
            "category": category if isinstance(category, str) and category else "general",
            "quantity": max(1, quantity),
            "prefer_private_label": bool(entry.get("prefer_private_label", False)),
        }
        for key in note_keys:
            note = entry.get(key)
            if isinstance(note, str) and note.strip():
                item[key] = note.strip()
        seed.append(item)
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
            'напої — drinks, вугілля та одноразовий посуд — accessories. Приклад: "гриль з куркою, свіжими печерицями та безалкогольним пивом" -> '
            '[{"query": "Курка для гриля", "category": "meat", "quantity": 2}, '
            '{"query": "Печериці свіжі", "category": "vegetables", "quantity": 1}, '
            '{"query": "Овочі для гриля", "category": "vegetables", "quantity": 2}, '
            '{"query": "Пиво безалкогольне", "category": "drinks", "quantity": 2}, '
            '{"query": "Стаканчики одноразові", "category": "accessories", "quantity": 1}].'
        )
        response = await _agenerate(
            model=settings.GEMINI_MODEL,
            models=get_plain_models(),
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
        return _sanitize_seed(json.loads(_extract_json_list(text)))
    except Exception as exc:  # noqa: BLE001 - formulation failure must fall back to planner seed
        logger.debug("Gemini query formulation failed, using planner fallback: %s", exc)
        return None


async def research_menu(goal: str) -> list[dict[str, Any]] | None:
    """Grounded menu research: dishes plus a shopping list for the goal.

    Uses Google Search grounding so dish and qualifier choices reflect real
    recipes. Structured output is intentionally NOT requested: the API rejects
    response_mime_type together with the google_search tool, so the prompt
    demands bare JSON and _extract_json_list recovers the list from prose.
    None means keep the deterministic planner fallback.
    """
    if settings.GEMINI_MOCK_MODE or not settings.GEMINI_API_KEY:
        return None
    try:
        prompt = (
            "Ти асистент Silpo Smart Shopper. Ціль: " + goal + ". "
            "Досліди в інтернеті 2-3 прості рецепти страв для цієї події "
            "(наприклад курка-гриль та овочі-гриль для пікніка) і склади список покупок "
            "українською (3-7 позицій) з кількістю на вказану кількість людей. "
            "Зберігай уточнення з цілі (свіжі, безалкогольне, одноразовий посуд). "
            "Відповідай ТІЛЬКИ JSON-списком без пояснень: "
            '[{"query": "...", "category": "meat|vegetables|drinks|accessories|general", '
            '"quantity": N, "dish": "страва"}].'
        )
        response = await _agenerate(
            model=settings.GEMINI_MODEL,
            models=get_flash_models(),
            contents=[prompt],
            config=types.GenerateContentConfig(
                temperature=0.2,
                tools=[types.Tool(google_search=types.GoogleSearch())],
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            ),
        )
        text = response.text
        if not text or not text.strip():
            return None
        return _sanitize_seed(json.loads(_extract_json_list(text)), ("dish", "note"))
    except Exception as exc:  # noqa: BLE001 - research failure must fall back to planner seed
        logger.debug("Gemini menu research failed, using planner fallback: %s", exc)
        return None


_WEEKLY_MEAL_KNOWN_CATEGORIES = frozenset({"meat", "vegetables", "grocery", "dairy", "bakery", "general"})

# The prompt asks for fish twice a week but offers no fish category, so remap
# strays to picker-compatible values (fish counts as meat protein, as in planners).
_WEEKLY_MEAL_CATEGORY_ALIASES = {"fish": "meat", "seafood": "meat"}


def _normalize_weekly_category(category: object) -> str:
    normalized = str(category or "").strip().lower()
    if normalized in _WEEKLY_MEAL_KNOWN_CATEGORIES:
        return normalized
    return _WEEKLY_MEAL_CATEGORY_ALIASES.get(normalized, "general")


async def plan_weekly_meals(goal: str) -> list[dict[str, Any]] | None:
    """Builds a budget-aware 7-day shopping seed; None means use deterministic fallback."""
    if settings.GEMINI_MOCK_MODE or not settings.GEMINI_API_KEY:
        return None
    try:
        response = await _agenerate(
            model=settings.GEMINI_MODEL,
            models=get_plain_models(),
            contents=[_GEMINI_WEEKLY_MEAL_PROMPT + " Ціль: " + goal],
            config=types.GenerateContentConfig(
                temperature=0.2,
                response_mime_type="application/json",
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            ),
        )
        text = response.text
        if not text or not text.strip():
            return None
        seed = _sanitize_seed(json.loads(_extract_json_list(text)), ("dish",))
        if seed is None:
            return None
        for item in seed:
            item["category"] = _normalize_weekly_category(item.get("category"))
        return seed
    except Exception as exc:  # noqa: BLE001 - failure keeps deterministic fallback
        logger.debug("Gemini weekly meal plan failed, using fallback: %s", exc)
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
            "алкогольні замість безалкогольних, багаторазові термочашки замість одноразових). "
            "Ціна кандидата НЕ є критерієм відповідності: не відхиляй дешевший товар — бюджет контролюється окремо. "
            'Відповідай JSON строго {"verdict": "accept"|"reject", "reason": "...", '
            '"suggested_query": "..."|null}.'
        )
        response = await _agenerate(
            model=settings.GEMINI_MODEL,
            models=get_plain_models(),
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
            models=get_flash_models(),
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
