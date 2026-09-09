"""TDD for Gemini model failover chain (long-tail dialogue quota survival).

Ordered failover: primary first, next model only on retryable errors
(429/503/504). No shared counters. Gemma/plain models only for
plain-text JSON calls; audio, structured schema, and search grounding
stay on Flash-Lite.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from app.config import Settings, settings
from google.genai import types


def _quota_error() -> RuntimeError:
    return RuntimeError("429 RESOURCE_EXHAUSTED: quota_exceeded, retry later")


def _unavailable_error() -> RuntimeError:
    return RuntimeError("503 service_unavailable: overloaded, retry later")


def _bad_request_error() -> RuntimeError:
    return RuntimeError("400 invalid_request: malformed payload")


def test_parse_model_list_splits_and_dedupes() -> None:
    from app.services.gemini_service import parse_model_list

    assert parse_model_list("") == []
    assert parse_model_list("  , ,") == []
    assert parse_model_list("a,b, a ,,c") == ["a", "b", "c"]


def test_flash_models_start_with_primary() -> None:
    import app.services.gemini_service as svc

    models = svc.get_flash_models()
    assert models[0] == settings.GEMINI_MODEL
    assert len(models) == len(set(models))
    assert len(models) >= 2


def test_plain_models_include_flash_chain() -> None:
    import app.services.gemini_service as svc

    flash = svc.get_flash_models()
    plain = svc.get_plain_models()
    assert plain[: len(flash)] == flash


def test_is_retryable_error_classification() -> None:
    from app.services.gemini_service import _is_retryable_error

    assert _is_retryable_error(_quota_error()) is True
    assert _is_retryable_error(_unavailable_error()) is True
    assert _is_retryable_error(_bad_request_error()) is False
    assert _is_retryable_error(RuntimeError("401 authentication: bad key")) is False
    assert _is_retryable_error(RuntimeError("403 permission_denied")) is False
    assert _is_retryable_error(RuntimeError("404 model_not_found: unknown model")) is True


def test_settings_has_fallback_fields() -> None:
    config = Settings()
    assert isinstance(config.GEMINI_MODEL_FALLBACKS, str)
    assert isinstance(config.GEMINI_MODEL_FALLBACKS_PLAIN, str)
    assert "gemini-3.1-flash-lite" in config.GEMINI_MODEL_FALLBACKS
    assert "gemma-4-26b-a4b-it" in config.GEMINI_MODEL_FALLBACKS_PLAIN
    assert "gemma-4-31b-it" in config.GEMINI_MODEL_FALLBACKS_PLAIN


@pytest.mark.asyncio
async def test_agenerate_fails_over_on_429(monkeypatch) -> None:
    import app.services.gemini_service as svc

    monkeypatch.setattr(svc.settings, "GEMINI_API_KEY", "fake-key")
    monkeypatch.setattr(svc.settings, "GEMINI_MOCK_MODE", False)

    ok_response = MagicMock()
    ok_response.text = "ok"

    mock_client = MagicMock()
    mock_client.aio = MagicMock()
    mock_client.aio.models = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(side_effect=[_quota_error(), ok_response])
    monkeypatch.setattr(svc, "get_genai_client", lambda: mock_client)

    config = types.GenerateContentConfig(temperature=0.0)
    response = await svc._agenerate(
        model="gemini-3.5-flash-lite",
        models=["gemini-3.5-flash-lite", "gemini-3.1-flash-lite"],
        contents=["ping"],
        config=config,
    )
    assert response is ok_response
    calls = mock_client.aio.models.generate_content.call_args_list
    assert [c[1]["model"] for c in calls] == [
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
    ]


@pytest.mark.asyncio
async def test_agenerate_skips_dead_model_code(monkeypatch) -> None:
    import app.services.gemini_service as svc

    monkeypatch.setattr(svc.settings, "GEMINI_API_KEY", "fake-key")
    monkeypatch.setattr(svc.settings, "GEMINI_MOCK_MODE", False)

    ok_response = MagicMock()
    ok_response.text = "ok"

    mock_client = MagicMock()
    mock_client.aio = MagicMock()
    mock_client.aio.models = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(
        side_effect=[
            RuntimeError("404 model_not_found: unknown model"),
            ok_response,
        ]
    )
    monkeypatch.setattr(svc, "get_genai_client", lambda: mock_client)

    config = types.GenerateContentConfig(temperature=0.0)
    response = await svc._agenerate(
        model="dead-model",
        models=["dead-model", "gemini-3.1-flash-lite"],
        contents=["ping"],
        config=config,
    )
    assert response is ok_response
    assert mock_client.aio.models.generate_content.call_count == 2


@pytest.mark.asyncio
async def test_agenerate_does_not_fail_over_on_400(monkeypatch) -> None:
    import app.services.gemini_service as svc

    monkeypatch.setattr(svc.settings, "GEMINI_API_KEY", "fake-key")
    monkeypatch.setattr(svc.settings, "GEMINI_MOCK_MODE", False)

    mock_client = MagicMock()
    mock_client.aio = MagicMock()
    mock_client.aio.models = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(side_effect=_bad_request_error())
    monkeypatch.setattr(svc, "get_genai_client", lambda: mock_client)

    config = types.GenerateContentConfig(temperature=0.0)
    with pytest.raises(RuntimeError, match="400"):
        await svc._agenerate(
            model="gemini-3.5-flash-lite",
            models=["gemini-3.5-flash-lite", "gemini-3.1-flash-lite"],
            contents=["ping"],
            config=config,
        )
    assert mock_client.aio.models.generate_content.call_count == 1


@pytest.mark.asyncio
async def test_agenerate_raises_after_chain_exhausted(monkeypatch) -> None:
    import app.services.gemini_service as svc

    monkeypatch.setattr(svc.settings, "GEMINI_API_KEY", "fake-key")
    monkeypatch.setattr(svc.settings, "GEMINI_MOCK_MODE", False)

    mock_client = MagicMock()
    mock_client.aio = MagicMock()
    mock_client.aio.models = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(side_effect=_quota_error())
    monkeypatch.setattr(svc, "get_genai_client", lambda: mock_client)

    config = types.GenerateContentConfig(temperature=0.0)
    with pytest.raises(RuntimeError, match="429"):
        await svc._agenerate(
            model="m1",
            models=["m1", "m2"],
            contents=["ping"],
            config=config,
        )
    assert mock_client.aio.models.generate_content.call_count == 2


@pytest.mark.asyncio
async def test_flash_only_calls_never_use_plain_models(monkeypatch) -> None:
    import app.services.gemini_service as svc

    monkeypatch.setattr(svc.settings, "GEMINI_MOCK_MODE", False)
    monkeypatch.setattr(svc.settings, "GEMINI_API_KEY", "fake-key")
    monkeypatch.setattr(svc.settings, "GEMINI_MODEL_FALLBACKS_PLAIN", "gemma-test-31b")

    captured: dict[str, object] = {}

    async def _fake_agenerate(*args: object, **kwargs: object) -> object:
        captured.update(kwargs)
        response = MagicMock()
        response.text = '[{"query": "Курка для гриля", "category": "meat", "quantity": 2, "dish": "Курка-гриль"}]'
        return response

    monkeypatch.setattr(svc, "_agenerate", _fake_agenerate)
    await svc.research_menu("grill goal")
    chain = captured.get("models")
    assert isinstance(chain, list)
    assert "gemma-test-31b" not in chain


@pytest.mark.asyncio
async def test_plain_calls_use_extended_chain(monkeypatch) -> None:
    import app.services.gemini_service as svc

    monkeypatch.setattr(svc.settings, "GEMINI_MOCK_MODE", False)
    monkeypatch.setattr(svc.settings, "GEMINI_API_KEY", "fake-key")
    monkeypatch.setattr(svc.settings, "GEMINI_MODEL_FALLBACKS_PLAIN", "gemma-test-31b")

    captured: dict[str, object] = {}

    async def _fake_agenerate(*args: object, **kwargs: object) -> object:
        captured.update(kwargs)
        response = MagicMock()
        response.text = '{"verdict": "accept", "reason": "", "suggested_query": null}'
        return response

    monkeypatch.setattr(svc, "_agenerate", _fake_agenerate)
    await svc.judge_picker_candidate(
        "Курка для гриля",
        {"title": "Куряче філе", "price": 180.0, "quantity": 1},
        "grill goal",
    )
    chain = captured.get("models")
    assert isinstance(chain, list)
    assert "gemma-test-31b" in chain
