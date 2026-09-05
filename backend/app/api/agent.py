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
        "cart_url": accumulated_state.get("cart_url"),
        "summary": accumulated_state.get("summary_message"),
        "audio_url": accumulated_state.get("audio_url"),
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
