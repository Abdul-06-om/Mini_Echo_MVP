import pytest

from app.bedrock import (
    DEFAULT_SYSTEM_PROMPT,
    DIFFICULTY_INSTRUCTIONS,
    SPOKEN_REPLY_INSTRUCTION,
    build_request_body,
    build_system_prompt,
    extract_reply_text,
)
from app.personas import Persona

TEST_PERSONA = Persona(
    id="test_persona",
    name="Dr. Test",
    role_title="Test Role",
    category="doctor",
    base_description="BASE DESCRIPTION.",
    safety_framing="SAFETY FRAMING.",
    voice_id="test-voice-id",
    face_id="test-face-id",
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


MATERIAL = "Zorivex achieved a 32% response rate in its pivotal trial."


def test_build_system_prompt_asks_for_short_spoken_replies_before_safety_framing():
    prompt = build_system_prompt(TEST_PERSONA, TEST_SESSION)

    assert SPOKEN_REPLY_INSTRUCTION in prompt
    assert "one to three sentences" in SPOKEN_REPLY_INSTRUCTION
    assert prompt.index(SPOKEN_REPLY_INSTRUCTION) < prompt.index("SAFETY FRAMING.")
    assert SPOKEN_REPLY_INSTRUCTION not in DEFAULT_SYSTEM_PROMPT


def test_build_system_prompt_without_reference_material_is_unchanged():
    assert build_system_prompt(TEST_PERSONA, TEST_SESSION) == (
        "BASE DESCRIPTION.\n\n"
        "Scenario: Test scenario\n"
        "Conversation objective: Test objective\n"
        "Persona mood/behavior for this conversation: Test mood\n"
        f"Difficulty: {DIFFICULTY_INSTRUCTIONS['medium']}\n\n"
        f"{SPOKEN_REPLY_INSTRUCTION}\n\n"
        "SAFETY FRAMING."
    )


def test_build_system_prompt_includes_reference_material_before_safety_framing():
    prompt = build_system_prompt(
        TEST_PERSONA, {**TEST_SESSION, "reference_material": MATERIAL}
    )

    assert f"<reference_material>\n{MATERIAL}\n</reference_material>" in prompt
    assert "do not recite" in prompt
    assert prompt.index("<reference_material>") < prompt.index("SAFETY FRAMING.")
    assert prompt.endswith("SAFETY FRAMING.")


def test_build_system_prompt_trims_reference_material():
    prompt = build_system_prompt(
        TEST_PERSONA, {**TEST_SESSION, "reference_material": f"  \n{MATERIAL}\n  "}
    )

    assert f"<reference_material>\n{MATERIAL}\n</reference_material>" in prompt


@pytest.mark.parametrize("empty", [None, "", "   \n\t "])
def test_build_system_prompt_ignores_empty_reference_material(empty):
    baseline = build_system_prompt(TEST_PERSONA, TEST_SESSION)

    prompt = build_system_prompt(
        TEST_PERSONA, {**TEST_SESSION, "reference_material": empty}
    )

    assert prompt == baseline


def test_build_system_prompt_without_persona_ignores_reference_material():
    session = {**TEST_SESSION, "reference_material": MATERIAL}

    assert build_system_prompt(None, session) == DEFAULT_SYSTEM_PROMPT
