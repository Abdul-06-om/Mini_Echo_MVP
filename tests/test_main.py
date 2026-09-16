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

    response = client.post("/chat", json={"messages": [{"role": "user", "content": "Hello"}]})

    assert response.status_code == 200
    assert response.json() == {"reply": "Mocked AI reply"}
    mock_get_reply.assert_called_once_with([{"role": "user", "content": "Hello"}])


@patch("app.main.get_reply")
def test_chat_endpoint_passes_full_history_to_get_reply(mock_get_reply):
    mock_get_reply.return_value = "Second reply"
    history = [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello! How can I help?"},
        {"role": "user", "content": "I have a headache"},
    ]

    response = client.post("/chat", json={"messages": history})

    assert response.status_code == 200
    assert response.json() == {"reply": "Second reply"}
    mock_get_reply.assert_called_once_with(history)


@patch("app.main.get_reply")
def test_chat_endpoint_returns_503_when_bedrock_fails(mock_get_reply):
    mock_get_reply.side_effect = Exception("boom: sensitive AWS detail")

    response = client.post("/chat", json={"messages": [{"role": "user", "content": "Hello"}]})

    assert response.status_code == 503
    assert response.json() == {
        "detail": "The AI service is temporarily unavailable. Please try again."
    }
    assert "sensitive AWS detail" not in response.text
