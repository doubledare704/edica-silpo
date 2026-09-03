"""Phase H3: agent tools as pure-async @tool with Command state updates."""

from typing import Any

import pytest
from langchain.tools import ToolRuntime
from langchain_core.tools import BaseTool


def _call(tool_name: str, args: dict[str, Any], state: dict[str, Any] | None = None) -> dict[str, Any]:
    """Plain-args invocation with a real ToolRuntime, mirroring ToolNode injection."""
    return {
        **args,
        "runtime": ToolRuntime(
            state=state or {},
            context=None,
            config={},
            stream_writer=lambda *a, **k: None,
            tool_call_id="test-call-1",
            store=None,
        ),
    }


def test_agent_tools_importable() -> None:
    from app import agent_tools

    for name in ["plan_items", "fetch_products", "check_budget", "create_cart"]:
        assert hasattr(agent_tools, name), f"missing tool {name}"
        tool = getattr(agent_tools, name)
        assert isinstance(tool, BaseTool), f"{name} must be a LangChain tool"


@pytest.mark.asyncio
async def test_plan_items_party_returns_command() -> None:
    from app.agent_tools import plan_items
    from langgraph.types import Command

    result = await plan_items.ainvoke(
        _call(
            "plan_items",
            {
                "intent": "party",
                "budget": 2500.0,
                "people_count": 6,
                "dietary_restrictions": ["vegetarian"],
            },
        )
    )
    assert isinstance(result, Command)
    update = result.update
    assert "calculated_items" in update
    assert len(update["calculated_items"]) > 0
    assert update["intent"] == "party"
    assert "messages" in update


@pytest.mark.asyncio
async def test_fetch_products_returns_command() -> None:
    from app.agent_tools import fetch_products
    from langgraph.types import Command

    result = await fetch_products.ainvoke(
        _call(
            "fetch_products",
            {
                "calculated_items": [
                    {"query": "Молоко Премія 2.5%", "quantity": 1},
                    {"query": "Хліб український нарізний", "quantity": 1},
                ]
            },
        )
    )
    assert isinstance(result, Command)
    assert "mcp_products" in result.update
    assert len(result.update["mcp_products"]) == 2
    assert result.update["mcp_products"][0]["price"] > 0


@pytest.mark.asyncio
async def test_check_budget_exceeded_path() -> None:
    from app.agent_tools import check_budget
    from langgraph.types import Command

    result = await check_budget.ainvoke(
        _call(
            "check_budget",
            {
                "mcp_products": [{"price": 2000.0, "quantity": 2}],
                "budget": 2500.0,
                "attempts": 0,
            },
        )
    )
    assert isinstance(result, Command)
    assert result.update["total_price"] == 4000.0
    assert result.update["is_budget_exceeded"] is True
    assert result.update["attempts"] == 1


@pytest.mark.asyncio
async def test_check_budget_ok_path() -> None:
    from app.agent_tools import check_budget

    result = await check_budget.ainvoke(
        _call(
            "check_budget",
            {
                "mcp_products": [{"price": 100.0, "quantity": 2}],
                "budget": 2500.0,
                "attempts": 0,
            },
        )
    )
    assert result.update["is_budget_exceeded"] is False
    assert result.update["total_price"] == 200.0


@pytest.mark.asyncio
async def test_create_cart_returns_url_and_summary() -> None:
    from app.agent_tools import create_cart
    from langgraph.types import Command

    result = await create_cart.ainvoke(
        _call(
            "create_cart",
            {
                "intent": "party",
                "total_price": 1500.0,
                "people_count": 6,
                "mcp_products": [{"id": "sku-1", "title": "Ошийник", "price": 240.0, "quantity": 2}],
            },
        )
    )
    assert isinstance(result, Command)
    assert result.update["cart_url"].startswith("https://silpo.ua/cart")
    assert len(result.update["summary_message"]) > 0


def test_tools_are_async() -> None:
    import inspect

    from app import agent_tools

    for name in ["plan_items", "fetch_products", "check_budget", "create_cart"]:
        tool = getattr(agent_tools, name)
        assert tool.coroutine is not None, f"{name} must be async (coroutine)"
        assert inspect.iscoroutinefunction(tool.coroutine)


def test_runtime_excluded_from_model_facing_schema() -> None:
    """Regression: runtime must be injected, never model-visible.

    A leaked runtime field makes Gemini schema conversion fail with
    PydanticInvalidForJsonSchema (CallableSchema) at bind_tools time.
    """
    from app import agent_tools

    for name in ["plan_items", "fetch_products", "check_budget", "create_cart"]:
        tool = getattr(agent_tools, name)
        assert "runtime" not in tool.tool_call_schema.model_fields, f"{name} leaks runtime to the model"
