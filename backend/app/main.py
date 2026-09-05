import base64
import binascii
import logging
import uuid
from collections.abc import AsyncGenerator, AsyncIterable
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.sse import EventSourceResponse, ServerSentEvent
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import settings
from .enums import NodeName, SSEEvent
from .graph import create_silpo_agent_graph
from .logging_config import configure_logging
from .state import SilpoAgentState

configure_logging(settings.LOG_LEVEL)

logger = logging.getLogger(__name__)

app = FastAPI(title="Silpo Smart Shopper Agent")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static directory for mock audio files if present
static_dir = Path(__file__).resolve().parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Shared agent graph with MemorySaver checkpointer
agent_graph = create_silpo_agent_graph()


class AgentStreamRequest(BaseModel):
    user_text: str | None = None
    thread_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    audio_base64: str | None = None


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
        "node": NodeName.TTS.value,
        "intent": accumulated_state.get("intent"),
        "total_price": accumulated_state.get("total_price", 0.0),
        "is_budget_exceeded": accumulated_state.get("is_budget_exceeded", False),
        "cart_url": accumulated_state.get("cart_url"),
        "summary": accumulated_state.get("summary_message"),
        "audio_url": accumulated_state.get("audio_url"),
    }
    yield ServerSentEvent(event=SSEEvent.NODE_COMPLETE, data=final_payload)


@app.post("/api/agent/stream", response_class=EventSourceResponse)
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
