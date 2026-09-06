import base64
import binascii
import logging
from collections.abc import AsyncGenerator, AsyncIterable

from fastapi import APIRouter
from fastapi.sse import EventSourceResponse, ServerSentEvent

from ..enums import IntentEnum, NodeName, SSEEvent
from ..graph import create_silpo_agent_graph
from ..schemas import AgentStreamRequest
from ..state import SilpoAgentState

logger = logging.getLogger(__name__)

router = APIRouter(tags=["agent"])

# Shared agent graph with MemorySaver checkpointer
agent_graph = create_silpo_agent_graph()


def _serialize_cart_items(products: object) -> list[dict[str, object]]:
    if not isinstance(products, list):
        return []
    items: list[dict[str, object]] = []
    for entry in products:
        if not isinstance(entry, dict):
            continue
        try:
            price = float(entry.get("price", 0.0) or 0.0)
        except (TypeError, ValueError):
            price = 0.0
        try:
            quantity = int(entry.get("quantity", 1) or 1)
        except (TypeError, ValueError):
            quantity = 1
        product_id = entry.get("productId") or entry.get("id")
        items.append(
            {
                "id": str(product_id) if product_id is not None else None,
                "title": str(entry.get("title", "")),
                "price": round(price, 2),
                "quantity": quantity,
                "is_private_label": bool(entry.get("is_private_label", False)),
                "line_total": round(price * quantity, 2),
            }
        )
    return items


async def _sse_generator(
    user_text: str | None,
    thread_id: str,
    audio_bytes: bytes | None = None,
) -> AsyncGenerator[ServerSentEvent, None]:
    # 1. Emit session_info event
    yield ServerSentEvent(event=SSEEvent.SESSION_INFO, data={"thread_id": thread_id})

    initial_state: SilpoAgentState = {
        "audio_bytes": audio_bytes,
        "user_text": user_text,
        "intent": None,
        "budget": 0.0,
        "people_count": None,
        "dietary_restrictions": [],
        "raw_item_requests": [],
        "calculated_items": [],
        "mcp_products": [],
        "total_price": 0.0,
        "attempts": 0,
        "max_attempts": 3,
        "is_budget_exceeded": False,
        "remaining_budget": 0.0,
        "unfulfilled_requests": [],
        "is_requirements_met": False,
        "picker_trace": [],
        "picker_accepted": 0,
        "shopping_context": None,
        "cart_url": None,
        "summary_message": "",
        "audio_url": None,
        "delivery_address": None,
        "fulfillment": None,
        "messages": [],
    }

    config = {"configurable": {"thread_id": thread_id}}
    accumulated_state: dict[str, object] = dict(initial_state)

    async for chunk in agent_graph.astream(initial_state, config=config, stream_mode="updates"):
        for node_name, node_output in chunk.items():
            accumulated_state.update(node_output)

            # Emit thinking_step event
            yield ServerSentEvent(event=SSEEvent.THINKING_STEP, data={"node": node_name, "status": "completed"})

            # Emit tool events for MCP node
            if node_name == NodeName.MCP_FETCH:
                yield ServerSentEvent(
                    event=SSEEvent.TOOL_START,
                    data={"tool": "silpo-py-mcp", "details": {"items": accumulated_state.get("calculated_items")}},
                )
                yield ServerSentEvent(event=SSEEvent.TOOL_END, data={"tool": "silpo-py-mcp", "status": "completed"})

            # Emit tool events for each picker tool call
            if node_name == NodeName.PICKER:
                trace = accumulated_state.get("picker_trace", [])
                if isinstance(trace, list):
                    for entry in trace:
                        if not isinstance(entry, dict):
                            continue
                        yield ServerSentEvent(
                            event=SSEEvent.TOOL_START,
                            data={"tool": entry.get("tool", "silpo-py-mcp"), "details": {"query": entry.get("query")}},
                        )
                        yield ServerSentEvent(
                            event=SSEEvent.TOOL_END,
                            data={
                                "tool": entry.get("tool", "silpo-py-mcp"),
                                "status": entry.get("status", "completed"),
                            },
                        )

    # Emit final node_complete event
    final_payload = {
        "node": (
            NodeName.UNSUPPORTED.value
            if accumulated_state.get("intent") == IntentEnum.UNSUPPORTED
            else NodeName.TTS.value
        ),
        "intent": accumulated_state.get("intent"),
        "total_price": accumulated_state.get("total_price", 0.0),
        "is_budget_exceeded": accumulated_state.get("is_budget_exceeded", False),
        "remaining_budget": accumulated_state.get("remaining_budget", 0.0),
        "is_requirements_met": accumulated_state.get("is_requirements_met", False),
        "cart_url": accumulated_state.get("cart_url"),
        "summary": accumulated_state.get("summary_message"),
        "audio_url": accumulated_state.get("audio_url"),
        "items": _serialize_cart_items(accumulated_state.get("mcp_products", [])),
    }
    yield ServerSentEvent(event=SSEEvent.NODE_COMPLETE, data=final_payload)


@router.post("/api/agent/stream", response_class=EventSourceResponse)
async def stream_agent_endpoint(request: AgentStreamRequest) -> AsyncIterable[ServerSentEvent]:
    """Streams LangGraph agent progress and final shopping cart via Server-Sent Events (SSE)."""
    audio_bytes = None
    if request.audio_base64:
        try:
            audio_bytes = base64.b64decode(request.audio_base64)
        except (binascii.Error, ValueError) as exc:
            logger.debug("Failed to decode base64 audio: %s", exc)

    async for event in _sse_generator(request.user_text, request.thread_id, audio_bytes):
        yield event
