import pytest
from fastapi.testclient import TestClient
from vero.server import app

def test_server_api_health():
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "vero"}

def test_server_static_studio_mount():
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "html" in response.headers.get("content-type", "").lower()

def test_server_chat_stream_endpoint():
    from unittest.mock import patch, MagicMock
    with patch("vero.server.VeroAgent") as mock_agent_cls:
        mock_instance = MagicMock()
        mock_instance.ask_stream.return_value = [
            {"type": "stage", "stage": "retrieval", "message": "Grounding schemas..."},
            {"type": "complete", "result": {"question": "test", "data": None}}
        ]
        mock_agent_cls.return_value = mock_instance

        client = TestClient(app)
        response = client.post("/api/chat/stream", json={"question": "Show revenue"})
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")
        content = response.text
        assert "Grounding schemas..." in content
        assert "complete" in content
