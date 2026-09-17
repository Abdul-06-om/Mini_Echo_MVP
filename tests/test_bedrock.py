from app.bedrock import (
    DEFAULT_SYSTEM_PROMPT,
    build_request_body,
    build_system_prompt,
    extract_reply_text,
)
from app.personas import Persona

TEST_PERSONA = Persona(
    id="test_persona",
    name="Dr. Test",
    role_title="Test Role",
    base_description="BASE DESCRIPTION.",
    safety_framing="SAFETY FRAMING.",
)
TEST_SESSION = {
    "scenario": "Test scenario",
    "objective": "Test objective",
    "mood": "Test mood",
    "difficulty": "medium",
}


def test_build_request_body_has_correct_shape():
    messages = [{"role": "user", "content": "Hello there"}]

    body = build_request_body(messages)

    assert body == {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1024,
        "system": DEFAULT_SYSTEM_PROMPT,
        "messages": messages,
    }


def test_extract_reply_text_returns_the_text_field():
    response_body = {
        "content": [{"type": "text", "text": "Hello world today."}]
    }

    assert extract_reply_text(response_body) == "Hello world today."


def test_build_system_prompt_falls_back_to_default_without_persona_or_session():
    assert build_system_prompt(None, None) == DEFAULT_SYSTEM_PROMPT


def test_build_system_prompt_composes_persona_and_session_fields():
    prompt = build_system_prompt(TEST_PERSONA, TEST_SESSION)

    assert "BASE DESCRIPTION." in prompt
    assert "Test scenario" in prompt
    assert "Test objective" in prompt
    assert "Test mood" in prompt
    assert "SAFETY FRAMING." in prompt


def test_build_system_prompt_differs_by_difficulty():
    easy_prompt = build_system_prompt(TEST_PERSONA, {**TEST_SESSION, "difficulty": "easy"})
    hard_prompt = build_system_prompt(TEST_PERSONA, {**TEST_SESSION, "difficulty": "hard"})

    assert easy_prompt != hard_prompt


def test_build_request_body_uses_dynamic_prompt_when_session_provided():
    messages = [{"role": "user", "content": "Hi"}]

    body = build_request_body(messages, persona=TEST_PERSONA, session=TEST_SESSION)

    assert body["system"] != DEFAULT_SYSTEM_PROMPT
    assert "BASE DESCRIPTION." in body["system"]
    assert body["messages"] == messages
