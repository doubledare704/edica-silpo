import logging
from unittest.mock import AsyncMock

import pytest


def _info_records(caplog, logger_name: str) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.name == logger_name and r.levelno == logging.INFO]


async def test_stt_node_logs_info_before_return(caplog) -> None:
    from app.nodes.stt import stt_node

    with caplog.at_level(logging.INFO, logger="app.nodes.stt"):
        result = await stt_node({"user_text": "hello", "audio_bytes": None})  # type: ignore[typeddict-item]

    assert result["user_text"] == "hello"
    assert _info_records(caplog, "app.nodes.stt"), "stt_node must log at INFO before returning"


async def test_parse_intent_node_logs_info_before_return(caplog) -> None:
    from app.nodes.parse_intent import parse_intent_node

    with caplog.at_level(logging.INFO, logger="app.nodes.parse_intent"):
        result = await parse_intent_node({"user_text": "", "audio_bytes": None})  # type: ignore[typeddict-item]

    assert "intent" in result
    assert _info_records(caplog, "app.nodes.parse_intent"), "parse_intent_node must log at INFO before returning"


@pytest.mark.asyncio
async def test_plan_domain_logic_node_logs_info_before_return(caplog) -> None:
    from app.nodes.plan_domain_logic import plan_domain_logic_node

    with caplog.at_level(logging.INFO, logger="app.nodes.plan_domain_logic"):
        result = await plan_domain_logic_node({"intent": None})  # type: ignore[typeddict-item]

    assert "calculated_items" in result
    assert _info_records(caplog, "app.nodes.plan_domain_logic")


async def test_mcp_fetch_node_logs_info_before_return(caplog, monkeypatch) -> None:
    from app.nodes import mcp_fetch
    from app.services import mcp_service

    monkeypatch.setattr(mcp_service.mcp_product_service, "fetch_products", AsyncMock(return_value=[]))
    with caplog.at_level(logging.INFO, logger="app.nodes.mcp_fetch"):
        result = await mcp_fetch.mcp_fetch_node({"calculated_items": []})  # type: ignore[typeddict-item]

    assert result == {"mcp_products": []}
    assert _info_records(caplog, "app.nodes.mcp_fetch"), "mcp_fetch_node must log at INFO before returning"


@pytest.mark.asyncio
async def test_check_constraints_node_logs_info_before_return(caplog) -> None:
    from app.nodes.check_constraints import check_constraints_node

    with caplog.at_level(logging.INFO, logger="app.nodes.check_constraints"):
        result = await check_constraints_node(  # type: ignore[typeddict-item]
            {"mcp_products": [], "budget": 0.0, "attempts": 0}
        )

    assert result["total_price"] == 0.0
    assert _info_records(caplog, "app.nodes.check_constraints")


@pytest.mark.asyncio
async def test_create_cart_node_logs_info_before_return(caplog) -> None:
    from app.nodes.create_cart import create_cart_node

    state = {"total_price": 100.0, "intent": None}  # type: ignore[typeddict-item]
    with caplog.at_level(logging.INFO, logger="app.nodes.create_cart"):
        result = await create_cart_node(state)

    assert "cart_url" in result
    assert _info_records(caplog, "app.nodes.create_cart")


@pytest.mark.asyncio
async def test_tts_node_logs_info_before_return(caplog) -> None:
    from app.nodes.tts import tts_node

    with caplog.at_level(logging.INFO, logger="app.nodes.tts"):
        result = await tts_node({"summary_message": "Кошик готовий"})  # type: ignore[typeddict-item]

    assert "audio_url" in result
    assert _info_records(caplog, "app.nodes.tts"), "tts_node must log at INFO before returning"
