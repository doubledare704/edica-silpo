import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.config import Settings
from app.enums import IntentEnum
from google import genai


def test_get_genai_client_creates_client_without_module_cache(monkeypatch) -> None:
    import app.services.gemini_service as svc

    monkeypatch.setattr(svc.settings, "GEMINI_MOCK_MODE", False)
    monkeypatch.setattr(svc.settings, "GEMINI_API_KEY", "fake-key")
    clients = [MagicMock(spec=genai.Client), MagicMock(spec=genai.Client)]
    client_factory = MagicMock(side_effect=clients)
    monkeypatch.setattr(svc.genai, "Client", client_factory)

    first = svc.get_genai_client()
    second = svc.get_genai_client()

    assert first is clients[0]
    assert second is clients[1]
    assert first is not second
    assert client_factory.call_count == 2


def test_default_gemini_settings() -> None:
    config = Settings()
    assert config.GEMINI_API_KEY == ""
    assert config.GEMINI_MODEL == "gemini-3.5-flash-lite"
    assert config.GEMINI_TTS_MODEL == "gemini-3.1-flash-tts-preview"
    assert config.TTS_PROVIDER == "respeecher"
    assert config.GEMINI_MOCK_MODE is False


def test_gemini_settings_env_override(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    monkeypatch.setenv("GEMINI_MOCK_MODE", "true")
    monkeypatch.setenv("TTS_PROVIDER", "gemini")
    config = Settings()
    assert config.GEMINI_API_KEY == "test-key"
    assert config.GEMINI_MOCK_MODE is True
    assert config.TTS_PROVIDER == "gemini"


@pytest.mark.asyncio
async def test_transcribe_audio_mock_mode_returns_fallback(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_MOCK_MODE", "true")
    import app.services.gemini_service as svc

    monkeypatch.setattr(svc.settings, "GEMINI_MOCK_MODE", True)
    monkeypatch.setattr(svc.settings, "GEMINI_API_KEY", "")
    from app.services.gemini_service import transcribe_audio

    result = await transcribe_audio(b"fake_audio")
    assert isinstance(result, str)
    assert len(result) > 0
    # In mock mode should return Ukrainian fallback (hardcoded)
    assert "пікніка" in result or "Збери" in result


@pytest.mark.asyncio
async def test_transcribe_audio_with_mocked_client(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_MOCK_MODE", "false")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    import app.services.gemini_service as svc

    monkeypatch.setattr(svc.settings, "GEMINI_MOCK_MODE", False)
    monkeypatch.setattr(svc.settings, "GEMINI_API_KEY", "fake-key")

    mock_response = MagicMock()
    mock_response.text = "Збери кошик для офісу на 10 людей до 1500 грн"

    mock_client = MagicMock()
    mock_client.models.generate_content = MagicMock(return_value=mock_response)
    mock_client.aio = MagicMock()
    mock_client.aio.models = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    with patch("app.services.gemini_service.get_genai_client", return_value=mock_client):
        from app.services.gemini_service import transcribe_audio

        result = await transcribe_audio(b"fake_audio", mime="audio/webm")
        assert result == "Збери кошик для офісу на 10 людей до 1500 грн"
        # Async path is preferred
        assert mock_client.aio.models.generate_content.call_count == 1


@pytest.mark.asyncio
async def test_transcribe_audio_missing_key_raises(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_MOCK_MODE", "false")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    import app.services.gemini_service as svc

    monkeypatch.setattr(svc.settings, "GEMINI_MOCK_MODE", False)
    monkeypatch.setattr(svc.settings, "GEMINI_API_KEY", "")

    from app.services.gemini_service import get_genai_client

    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        get_genai_client()


@pytest.mark.asyncio
async def test_choose_picker_candidate_includes_original_query(monkeypatch) -> None:
    import app.services.gemini_service as svc

    monkeypatch.setattr(svc.settings, "GEMINI_MOCK_MODE", False)
    monkeypatch.setattr(svc.settings, "GEMINI_API_KEY", "fake-key")

    mock_response = MagicMock()
    mock_response.text = '{"index": 0}'

    mock_client = MagicMock()
    mock_client.aio = MagicMock()
    mock_client.aio.models = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    with patch("app.services.gemini_service.get_genai_client", return_value=mock_client):
        from app.services.gemini_service import choose_picker_candidate

        candidates = [{"title": "Куряче філе", "price": 180.0, "quantity": 1}]
        assert await choose_picker_candidate(candidates, 500.0, "grill goal", "Курка для гриля") == 0
        prompt = mock_client.aio.models.generate_content.call_args[1]["contents"][0]
        assert "Курка для гриля" in prompt


@pytest.mark.asyncio
async def test_choose_picker_candidate_reject_veto(monkeypatch) -> None:
    import app.services.gemini_service as svc

    monkeypatch.setattr(svc.settings, "GEMINI_MOCK_MODE", False)
    monkeypatch.setattr(svc.settings, "GEMINI_API_KEY", "fake-key")

    mock_response = MagicMock()
    mock_response.text = '{"reject": true}'

    mock_client = MagicMock()
    mock_client.aio = MagicMock()
    mock_client.aio.models = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    with patch("app.services.gemini_service.get_genai_client", return_value=mock_client):
        from app.services.gemini_service import ADVISOR_VETO, choose_picker_candidate

        candidates = [{"title": "Ошийник свинячий", "price": 240.0, "quantity": 1}]
        assert await choose_picker_candidate(candidates, 500.0, "chicken goal", "Курка для гриля") == ADVISOR_VETO


@pytest.mark.asyncio
async def test_choose_picker_candidate_prompt_ignores_price(monkeypatch) -> None:
    import app.services.gemini_service as svc

    monkeypatch.setattr(svc.settings, "GEMINI_MOCK_MODE", False)
    monkeypatch.setattr(svc.settings, "GEMINI_API_KEY", "fake-key")

    mock_response = MagicMock()
    mock_response.text = '{"index": 0}'

    mock_client = MagicMock()
    mock_client.aio = MagicMock()
    mock_client.aio.models = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    with patch("app.services.gemini_service.get_genai_client", return_value=mock_client):
        from app.services.gemini_service import choose_picker_candidate

        candidates = [{"title": "Вино Mirra Alentejo Tinto", "price": 668.0, "quantity": 1}]
        assert await choose_picker_candidate(candidates, 4000.0, "gourmet goal", "Вино вишукане") == 0
        prompt = mock_client.aio.models.generate_content.call_args[1]["contents"][0]
        assert "ціна" in prompt.lower()
        assert "не відхиляй" in prompt.lower()


@pytest.mark.asyncio
async def test_judge_prompt_ignores_price(monkeypatch) -> None:
    import app.services.gemini_service as svc

    monkeypatch.setattr(svc.settings, "GEMINI_MOCK_MODE", False)
    monkeypatch.setattr(svc.settings, "GEMINI_API_KEY", "fake-key")

    mock_response = MagicMock()
    mock_response.text = '{"verdict": "accept", "reason": "", "suggested_query": null}'

    mock_client = MagicMock()
    mock_client.aio = MagicMock()
    mock_client.aio.models = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    with patch("app.services.gemini_service.get_genai_client", return_value=mock_client):
        from app.services.gemini_service import judge_picker_candidate

        await judge_picker_candidate(
            "Вино вишукане",
            {"title": "Вино Mirra Alentejo Tinto", "price": 668.0, "quantity": 1},
            "gourmet goal",
        )
        prompt = mock_client.aio.models.generate_content.call_args[1]["contents"][0]
        assert "ціна" in prompt.lower()
        assert "не відхиляй" in prompt.lower()


def test_extract_json_list_handles_fences_and_prose() -> None:
    from app.services.gemini_service import _extract_json_list

    assert json.loads(_extract_json_list('[{"query": "Курка"}]')) == [{"query": "Курка"}]
    fenced = '```json\n[{"query": "Курка"}]\n```'
    assert json.loads(_extract_json_list(fenced)) == [{"query": "Курка"}]
    prose = 'Ось список покупок:\n[{"query": "Курка"}]\nСмачного!'
    assert json.loads(_extract_json_list(prose)) == [{"query": "Курка"}]


@pytest.mark.asyncio
async def test_research_menu_omits_json_mime_type_with_search_tool(monkeypatch) -> None:
    import app.services.gemini_service as svc

    monkeypatch.setattr(svc.settings, "GEMINI_MOCK_MODE", False)
    monkeypatch.setattr(svc.settings, "GEMINI_API_KEY", "fake-key")

    captured: dict[str, object] = {}

    async def _fake_agenerate(*args: object, **kwargs: object) -> object:
        captured.update(kwargs)
        response = MagicMock()
        response.text = (
            'Ось меню:\n[{"query": "Курка для гриля", "category": "meat", "quantity": 2, "dish": "Курка-гриль"}]'
        )
        return response

    monkeypatch.setattr(svc, "_agenerate", _fake_agenerate)
    from app.services.gemini_service import research_menu

    menu = await research_menu("grill goal")
    assert menu == [
        {
            "query": "Курка для гриля",
            "category": "meat",
            "quantity": 2,
            "prefer_private_label": False,
            "dish": "Курка-гриль",
        }
    ]
    config = captured["config"]
    assert getattr(config, "response_mime_type", None) in (None, "text/plain")
    assert getattr(config, "tools", None)


@pytest.mark.asyncio
async def test_formulate_picker_queries_parses_bare_list(monkeypatch) -> None:
    import app.services.gemini_service as svc

    monkeypatch.setattr(svc.settings, "GEMINI_MOCK_MODE", False)
    monkeypatch.setattr(svc.settings, "GEMINI_API_KEY", "fake-key")

    async def _fake_agenerate(*args: object, **kwargs: object) -> object:
        response = MagicMock()
        response.text = '[{"query": "Курка для гриля", "category": "meat", "quantity": 2}]'
        return response

    monkeypatch.setattr(svc, "_agenerate", _fake_agenerate)
    from app.services.gemini_service import formulate_picker_queries

    seed = await formulate_picker_queries("grill goal", [])
    assert seed == [{"query": "Курка для гриля", "category": "meat", "quantity": 2, "prefer_private_label": False}]


@pytest.mark.asyncio
async def test_parse_intent_multimodal_mock_mode_fallback(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_MOCK_MODE", "true")
    import app.services.gemini_service as svc

    monkeypatch.setattr(svc.settings, "GEMINI_MOCK_MODE", True)
    monkeypatch.setattr(svc.settings, "GEMINI_API_KEY", "")
    from app.services.gemini_service import parse_intent_multimodal

    result = await parse_intent_multimodal(
        user_text="Збери кошик для пікніка на 6 людей до 2500 грн, один вегетаріанець", audio_bytes=None
    )
    assert result.intent == IntentEnum.PARTY
    assert result.budget == 2500.0
    assert result.people_count == 6
    assert "vegetarian" in result.dietary_restrictions


@pytest.mark.asyncio
async def test_parse_intent_multimodal_with_mocked_client(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_MOCK_MODE", "false")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    import app.services.gemini_service as svc

    monkeypatch.setattr(svc.settings, "GEMINI_MOCK_MODE", False)
    monkeypatch.setattr(svc.settings, "GEMINI_API_KEY", "fake-key")

    mock_response = MagicMock()
    mock_response.text = '{"intent": "budget", "budget": 1000.0, "people_count": null, "dietary_restrictions": [], "raw_item_requests": ["молоко", "хліб", "яйця"]}'
    # also support .parsed attribute for context7 pattern
    mock_response.parsed = None

    mock_client = MagicMock()
    mock_client.models.generate_content = MagicMock(return_value=mock_response)
    mock_client.aio = MagicMock()
    mock_client.aio.models = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    with patch("app.services.gemini_service.get_genai_client", return_value=mock_client):
        from app.services.gemini_service import parse_intent_multimodal

        result = await parse_intent_multimodal(user_text="Економний кошик до 1000 грн", audio_bytes=None)
        assert result.intent == IntentEnum.BUDGET
        assert result.budget == 1000.0
        assert "молоко" in result.raw_item_requests


@pytest.mark.asyncio
async def test_parse_intent_multimodal_with_audio_bytes(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_MOCK_MODE", "false")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    import app.services.gemini_service as svc

    monkeypatch.setattr(svc.settings, "GEMINI_MOCK_MODE", False)
    monkeypatch.setattr(svc.settings, "GEMINI_API_KEY", "fake-key")

    mock_response = MagicMock()
    mock_response.text = '{"intent": "gourmet", "budget": 0.0, "people_count": 2, "dietary_restrictions": [], "raw_item_requests": ["сир", "вино"]}'

    mock_client = MagicMock()
    mock_client.models.generate_content = MagicMock(return_value=mock_response)
    mock_client.aio = MagicMock()
    mock_client.aio.models = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    with patch("app.services.gemini_service.get_genai_client", return_value=mock_client):
        from app.services.gemini_service import parse_intent_multimodal

        result = await parse_intent_multimodal(user_text=None, audio_bytes=b"fake_webm_bytes")
        assert result.intent == IntentEnum.GOURMET
        assert result.people_count == 2
        # Ensure generate_content called with audio part (via aio)
        call_kwargs = mock_client.aio.models.generate_content.call_args
        assert call_kwargs is not None


@pytest.mark.asyncio
async def test_plan_weekly_meals_mock_mode_returns_none(monkeypatch) -> None:
    import app.services.gemini_service as svc

    monkeypatch.setattr(svc.settings, "GEMINI_MOCK_MODE", True)
    monkeypatch.setattr(svc.settings, "GEMINI_API_KEY", "")
    from app.services.gemini_service import plan_weekly_meals

    assert await plan_weekly_meals("weekly goal") is None


@pytest.mark.asyncio
async def test_plan_weekly_meals_parses_list_and_keeps_dish(monkeypatch) -> None:
    import app.services.gemini_service as svc

    monkeypatch.setattr(svc.settings, "GEMINI_MOCK_MODE", False)
    monkeypatch.setattr(svc.settings, "GEMINI_API_KEY", "fake-key")

    async def _fake_agenerate(*args: object, **kwargs: object) -> object:
        response = MagicMock()
        response.text = (
            '[{"query": "Хек свіжоморожений", "category": "meat", "quantity": 2, "dish": "Хек з гречкою"}, '
            '{"query": "", "category": "general", "quantity": 1}]'
        )
        return response

    monkeypatch.setattr(svc, "_agenerate", _fake_agenerate)
    from app.services.gemini_service import plan_weekly_meals

    seed = await plan_weekly_meals("weekly goal")
    assert seed == [
        {
            "query": "Хек свіжоморожений",
            "category": "meat",
            "quantity": 2,
            "prefer_private_label": False,
            "dish": "Хек з гречкою",
        }
    ]


@pytest.mark.asyncio
async def test_plan_weekly_meals_normalizes_fish_category(monkeypatch) -> None:
    import app.services.gemini_service as svc

    monkeypatch.setattr(svc.settings, "GEMINI_MOCK_MODE", False)
    monkeypatch.setattr(svc.settings, "GEMINI_API_KEY", "fake-key")

    async def _fake_agenerate(*args: object, **kwargs: object) -> object:
        response = MagicMock()
        response.text = '[{"query": "Хек свіжоморожений", "category": "fish", "quantity": 2}]'
        return response

    monkeypatch.setattr(svc, "_agenerate", _fake_agenerate)
    from app.services.gemini_service import plan_weekly_meals

    seed = await plan_weekly_meals("weekly goal")
    assert seed is not None
    assert seed[0]["category"] == "meat"


@pytest.mark.asyncio
async def test_plan_weekly_meals_returns_none_on_failure(monkeypatch) -> None:
    import app.services.gemini_service as svc

    monkeypatch.setattr(svc.settings, "GEMINI_MOCK_MODE", False)
    monkeypatch.setattr(svc.settings, "GEMINI_API_KEY", "fake-key")

    async def _boom(*args: object, **kwargs: object) -> object:
        raise RuntimeError("API error")

    monkeypatch.setattr(svc, "_agenerate", _boom)
    from app.services.gemini_service import plan_weekly_meals

    assert await plan_weekly_meals("weekly goal") is None


@pytest.mark.asyncio
async def test_parse_intent_fallback_on_client_error(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_MOCK_MODE", "false")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    import app.services.gemini_service as svc

    monkeypatch.setattr(svc.settings, "GEMINI_MOCK_MODE", False)
    monkeypatch.setattr(svc.settings, "GEMINI_API_KEY", "fake-key")

    mock_client = MagicMock()
    mock_client.models.generate_content = MagicMock(side_effect=RuntimeError("API error"))
    mock_client.aio = MagicMock()
    mock_client.aio.models = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(side_effect=RuntimeError("API error"))

    with patch("app.services.gemini_service.get_genai_client", return_value=mock_client):
        from app.services.gemini_service import parse_intent_multimodal

        result = await parse_intent_multimodal(
            user_text="Збери кошик для пікніка на 6 людей до 2500 грн, один вегетаріанець", audio_bytes=None
        )
        # Should fallback to regex parsing, not crash
        assert result.intent == IntentEnum.PARTY
        assert result.budget == 2500.0
