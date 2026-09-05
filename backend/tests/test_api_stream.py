import json

import pytest
from app.enums import SSEEvent
from app.main import app
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_agent_stream_sse_endpoint() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "user_text": "Збери кошик для пікніка на 6 людей до 2500 грн, один вегетаріанець",
            "thread_id": "test-session-123",
        }
        async with client.stream("POST", "/api/agent/stream", json=payload) as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers["content-type"]

            lines = []
            async for line in response.aiter_lines():
                if line.strip():
                    lines.append(line.strip())

            event_names = [line.replace("event: ", "") for line in lines if line.startswith("event: ")]
            data_lines = [line.replace("data: ", "") for line in lines if line.startswith("data: ")]

            assert SSEEvent.SESSION_INFO in event_names
            assert SSEEvent.THINKING_STEP in event_names
            assert SSEEvent.NODE_COMPLETE in event_names
            thinking_data = [
                json.loads(lines[index + 1].replace("data: ", ""))
                for index, line in enumerate(lines[:-1])
                if line == f"event: {SSEEvent.THINKING_STEP}"
            ]
            assert {item["node"] for item in thinking_data} >= {
                "stt",
                "parse_intent",
                "plan_domain_logic",
                "mcp_fetch",
                "check_constraints",
                "create_cart",
                "tts",
            }

            # Verify session_info payload
            session_data = json.loads(data_lines[0])
            assert session_data["thread_id"] == "test-session-123"

            # Verify node_complete payload
            last_data = json.loads(data_lines[-1])
            assert "cart_url" in last_data
            assert "summary" in last_data
            assert "audio_url" in last_data
            assert last_data["cart_url"].startswith("https://silpo.ua/cart")
            assert last_data["audio_url"] is None


@pytest.mark.asyncio
async def test_agent_stream_sse_carries_audio_url_for_voice_request(monkeypatch) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "TTS_MOCK_MODE", True)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "user_text": "Збери кошик для пікніка на 6 людей до 2500 грн",
            "thread_id": "test-session-audio",
            "audio_base64": "dm9pY2UtaW5wdXQ=",  # base64 of b"voice-input"
        }
        async with client.stream("POST", "/api/agent/stream", json=payload) as response:
            assert response.status_code == 200
            lines = []
            async for line in response.aiter_lines():
                if line.strip():
                    lines.append(line.strip())

            data_lines = [line.replace("data: ", "") for line in lines if line.startswith("data: ")]
            last_data = json.loads(data_lines[-1])
            assert last_data["audio_url"] == "/static/audio/mock_response.wav"
