import json

import pytest

from app.evaluation import (
    build_evaluation_prompt,
    build_evaluation_request_body,
    extract_evaluation,
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
VALID_EVALUATION = {
    "dimensions": {
        "message_accuracy": "Accurate and complete.",
        "objection_handling": "Handled well.",
        "rapport_building": "Warm and attentive.",
        "compliance_adherence": "Stayed on-label.",
    },
    "overall_summary": "Solid performance overall.",
    "improvement_recommendations": "Ask more open-ended questions.",
}


def _response_with_text(text):
    return {"content": [{"type": "text", "text": text}]}


def test_build_evaluation_prompt_includes_persona_and_session_context():
    prompt = build_evaluation_prompt(TEST_PERSONA, TEST_SESSION)

    assert "Dr. Test" in prompt
    assert "Test scenario" in prompt
    assert "Test objective" in prompt
    assert "pass/fail" in prompt.lower()


def test_build_evaluation_request_body_has_correct_shape():
    messages = [{"role": "user", "content": "Hello"}]

    body = build_evaluation_request_body(messages, TEST_PERSONA, TEST_SESSION)

    assert body["anthropic_version"] == "bedrock-2023-05-31"
    assert body["messages"] == messages
    assert "Dr. Test" in body["system"]


def test_extract_evaluation_parses_valid_json():
    response_body = _response_with_text(json.dumps(VALID_EVALUATION))

    assert extract_evaluation(response_body) == VALID_EVALUATION


def test_extract_evaluation_parses_json_in_markdown_fence():
    fenced = "```json\n" + json.dumps(VALID_EVALUATION) + "\n```"
    response_body = _response_with_text(fenced)

    assert extract_evaluation(response_body) == VALID_EVALUATION


def test_extract_evaluation_parses_json_with_preamble_before_fence():
    preambled = "Here's the evaluation:\n```json\n" + json.dumps(VALID_EVALUATION) + "\n```"
    response_body = _response_with_text(preambled)

    assert extract_evaluation(response_body) == VALID_EVALUATION


def test_extract_evaluation_raises_for_non_json_text():
    response_body = _response_with_text("This is not JSON at all.")

    with pytest.raises(ValueError):
        extract_evaluation(response_body)


def test_extract_evaluation_raises_for_non_object_json():
    response_body = _response_with_text(json.dumps(["not", "an", "object"]))

    with pytest.raises(ValueError):
        extract_evaluation(response_body)


def test_extract_evaluation_raises_for_missing_dimensions_key():
    incomplete = {k: v for k, v in VALID_EVALUATION.items() if k != "dimensions"}
    response_body = _response_with_text(json.dumps(incomplete))

    with pytest.raises(ValueError):
        extract_evaluation(response_body)


def test_extract_evaluation_raises_for_missing_dimension_field():
    incomplete = json.loads(json.dumps(VALID_EVALUATION))
    del incomplete["dimensions"]["compliance_adherence"]
    response_body = _response_with_text(json.dumps(incomplete))

    with pytest.raises(ValueError):
        extract_evaluation(response_body)


def test_extract_evaluation_raises_for_non_string_field_value():
    invalid = json.loads(json.dumps(VALID_EVALUATION))
    invalid["overall_summary"] = 7
    response_body = _response_with_text(json.dumps(invalid))

    with pytest.raises(ValueError):
        extract_evaluation(response_body)
