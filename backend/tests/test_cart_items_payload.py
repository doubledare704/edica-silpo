import json

import pytest
from app.main import app
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_agent_stream_node_complete_includes_picked_items() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "user_text": "Збери кошик для пікніка на 6 людей до 2500 грн",
            "thread_id": "test-session-items",
        }
        async with client.stream("POST", "/api/agent/stream", json=payload) as response:
            assert response.status_code == 200
            lines = [line.strip() async for line in response.aiter_lines() if line.strip()]

            data_lines = [line.replace("data: ", "") for line in lines if line.startswith("data: ")]
            last_data = json.loads(data_lines[-1])

            assert "items" in last_data
            assert isinstance(last_data["items"], list)
            assert len(last_data["items"]) > 0
            first = last_data["items"][0]
            assert "title" in first
            assert "price" in first
            assert "quantity" in first
