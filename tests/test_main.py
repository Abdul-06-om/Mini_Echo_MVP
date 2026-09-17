from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.personas import PERSONAS

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


@patch("app.main.avatar_provider.create_session")
def test_avatar_session_returns_provider_result(mock_create_session):
    mock_create_session.return_value = {"session_token": "mocked-token"}

    response = client.post("/avatar/session")

    assert response.status_code == 200
    assert response.json() == {"session_token": "mocked-token"}


@patch("app.main.avatar_provider.create_session")
def test_avatar_session_returns_503_on_failure(mock_create_session):
    mock_create_session.side_effect = Exception("boom: sensitive Simli detail")

    response = client.post("/avatar/session")

    assert response.status_code == 503
    assert "sensitive Simli detail" not in response.text


@patch("app.main.list_voices")
def test_voices_returns_provider_list(mock_list_voices):
    mock_list_voices.return_value = [{"voice_id": "abc123", "name": "Sarah"}]

    response = client.get("/voices")

    assert response.status_code == 200
    assert response.json() == [{"voice_id": "abc123", "name": "Sarah"}]


@patch("app.main.synthesize_speech")
def test_tts_returns_audio_bytes(mock_synthesize_speech):
    mock_synthesize_speech.return_value = b"\x00\x01fake-pcm-audio"

    response = client.post("/tts", json={"text": "Hello there"})

    assert response.status_code == 200
    assert response.content == b"\x00\x01fake-pcm-audio"
    mock_synthesize_speech.assert_called_once_with("Hello there")


@patch("app.main.synthesize_speech")
def test_tts_passes_voice_id_when_provided(mock_synthesize_speech):
    mock_synthesize_speech.return_value = b"audio"

    response = client.post("/tts", json={"text": "Hi", "voice_id": "custom-voice"})

    assert response.status_code == 200
    mock_synthesize_speech.assert_called_once_with("Hi", "custom-voice")


@patch("app.main.synthesize_speech")
def test_tts_returns_503_on_failure(mock_synthesize_speech):
    mock_synthesize_speech.side_effect = Exception("boom: sensitive ElevenLabs detail")

    response = client.post("/tts", json={"text": "Hi"})

    assert response.status_code == 503
    assert "sensitive ElevenLabs detail" not in response.text


@patch("app.main.get_reply")
def test_chat_endpoint_with_roleplay_session_passes_persona_and_session(mock_get_reply):
    mock_get_reply.return_value = "In character reply"
    session_payload = {
        "persona_id": "dr_sarah_chen",
        "scenario": "Pharmaceutical sales call",
        "objective": "Introduce a new treatment and handle objections",
        "mood": "Skeptical, short on time",
        "difficulty": "medium",
    }

    response = client.post(
        "/chat",
        json={
            "messages": [{"role": "user", "content": "Hello doctor"}],
            "session": session_payload,
        },
    )

    assert response.status_code == 200
    assert response.json() == {"reply": "In character reply"}
    mock_get_reply.assert_called_once_with(
        [{"role": "user", "content": "Hello doctor"}],
        persona=PERSONAS["dr_sarah_chen"],
        session=session_payload,
    )


def test_chat_endpoint_rejects_unknown_persona_id():
    response = client.post(
        "/chat",
        json={
            "messages": [{"role": "user", "content": "Hi"}],
            "session": {
                "persona_id": "nonexistent_persona",
                "scenario": "x",
                "objective": "y",
                "mood": "z",
                "difficulty": "medium",
            },
        },
    )

    assert response.status_code == 400


def test_personas_returns_registered_personas():
    response = client.get("/personas")

    assert response.status_code == 200
    assert response.json() == [
        {"id": "dr_sarah_chen", "name": "Dr. Sarah Chen", "role_title": "General Practitioner"}
    ]
