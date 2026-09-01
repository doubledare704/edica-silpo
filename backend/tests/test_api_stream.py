import json

import pytest
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

            assert "session_info" in event_names
            assert "thinking_step" in event_names
            assert "node_complete" in event_names

            # Verify session_info payload
            session_data = json.loads(data_lines[0])
            assert session_data["thread_id"] == "test-session-123"

            # Verify node_complete payload
            last_data = json.loads(data_lines[-1])
            assert "cart_url" in last_data
            assert "summary" in last_data
            assert last_data["cart_url"].startswith("https://silpo.ua/cart")
