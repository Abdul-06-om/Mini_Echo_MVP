from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check_returns_ok():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_index_serves_html_page():
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


@patch("app.main.get_reply")
def test_chat_endpoint_returns_ai_reply(mock_get_reply):
    mock_get_reply.return_value = "Mocked AI reply"

    response = client.post("/chat", json={"message": "Hello"})

    assert response.status_code == 200
    assert response.json() == {"reply": "Mocked AI reply"}
    mock_get_reply.assert_called_once_with("Hello")
