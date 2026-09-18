import json

import boto3

from app.bedrock import MODEL_ID, REGION
from app.personas import Persona

EVALUATION_MAX_TOKENS = 1024

_client = boto3.client("bedrock-runtime", region_name=REGION)

REQUIRED_FIELDS = (
    "message_accuracy",
    "objection_handling",
    "rapport_building",
    "compliance_adherence",
)


def build_evaluation_prompt(persona: Persona, session: dict) -> str:
    return (
        "You are an impartial evaluator reviewing a completed training "
        f"roleplay conversation. Do not continue the roleplay or respond "
        f"as {persona.name}. The user was practicing a conversation with "
        f"{persona.name}, {persona.role_title}, in this scenario: "
        f"{session['scenario']}. Their objective was: {session['objective']}. "
        f"Evaluate only the user's turns (not {persona.name}'s) in the "
        "conversation below.\n\n"
        "Respond with a single JSON object and nothing else — no markdown "
        "formatting, no code fences, no commentary before or after it — "
        "containing exactly these string fields: "
        '"dimensions": {"message_accuracy", "objection_handling", '
        '"rapport_building", "compliance_adherence"}, "overall_summary", '
        '"improvement_recommendations". Each value must be a short plain-text '
        "assessment. Do not include any numeric scores, ratings, percentages, "
        "grades, or pass/fail judgments anywhere in your response — "
        "qualitative text only."
    )


def build_evaluation_request_body(
    messages: list, persona: Persona, session: dict
) -> dict:
    return {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": EVALUATION_MAX_TOKENS,
        "system": build_evaluation_prompt(persona, session),
        "messages": messages,
    }


def extract_evaluation(response_body: dict) -> dict:
    text = response_body["content"][0]["text"].strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise ValueError("Malformed evaluation response: not valid JSON")
        try:
            result = json.loads(text[start : end + 1])
        except json.JSONDecodeError as error:
            raise ValueError("Malformed evaluation response: not valid JSON") from error

    if not isinstance(result, dict):
        raise ValueError("Malformed evaluation response: not a JSON object")

    dimensions = result.get("dimensions")
    if not isinstance(dimensions, dict):
        raise ValueError("Malformed evaluation response: missing dimensions")

    for field in REQUIRED_FIELDS:
        if not isinstance(dimensions.get(field), str):
            raise ValueError(f"Malformed evaluation response: missing {field}")

    for field in ("overall_summary", "improvement_recommendations"):
        if not isinstance(result.get(field), str):
            raise ValueError(f"Malformed evaluation response: missing {field}")

    return result


def get_evaluation(messages: list, persona: Persona, session: dict) -> dict:
    body = build_evaluation_request_body(messages, persona, session)

    response = _client.invoke_model(
        modelId=MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body),
    )

    response_body = json.loads(response["body"].read())
    return extract_evaluation(response_body)
