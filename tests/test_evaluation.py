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
    assert "Dr. Test" in body["system"]
    assert body["messages"][:-1] == messages
    assert body["messages"][-1]["role"] == "user"


MATERIAL = "Zorivex achieved a 32% response rate in its pivotal trial."


def test_build_evaluation_prompt_includes_reference_material():
    prompt = build_evaluation_prompt(
        TEST_PERSONA, {**TEST_SESSION, "reference_material": MATERIAL}
    )

    assert f"<reference_material>\n{MATERIAL}\n</reference_material>" in prompt
    assert "cannot be verified" in prompt
    assert "never introduce a number" in prompt
    assert "score, weight, rank, threshold, grade or certify" in prompt
    assert prompt.index("<reference_material>") < prompt.index(
        "Respond with a single JSON object"
    )


def test_build_evaluation_prompt_trims_reference_material():
    prompt = build_evaluation_prompt(
        TEST_PERSONA, {**TEST_SESSION, "reference_material": f"  \n{MATERIAL}\n  "}
    )

    assert f"<reference_material>\n{MATERIAL}\n</reference_material>" in prompt


@pytest.mark.parametrize("empty", [None, "", "   \n\t "])
def test_build_evaluation_prompt_ignores_empty_reference_material(empty):
    baseline = build_evaluation_prompt(TEST_PERSONA, TEST_SESSION)

    prompt = build_evaluation_prompt(
        TEST_PERSONA, {**TEST_SESSION, "reference_material": empty}
    )

    assert prompt == baseline
    assert "reference_material" not in baseline
    assert "Reference material" not in baseline


def test_build_evaluation_request_body_keeps_trailing_user_message_with_material():
    body = build_evaluation_request_body(
        [{"role": "assistant", "content": "Hi"}],
        TEST_PERSONA,
        {**TEST_SESSION, "reference_material": MATERIAL},
    )

    assert MATERIAL in body["system"]
    assert body["messages"][-1] == {
        "role": "user",
        "content": "Now produce the evaluation JSON object described above.",
    }


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


def test_extract_evaluation_strips_unexpected_fields():
    polluted = json.loads(json.dumps(VALID_EVALUATION))
    polluted["score"] = 95
    polluted["dimensions"]["extra_field"] = "should not survive"
    response_body = _response_with_text(json.dumps(polluted))

    result = extract_evaluation(response_body)

    assert result == VALID_EVALUATION
    assert "score" not in result
    assert "extra_field" not in result["dimensions"]
