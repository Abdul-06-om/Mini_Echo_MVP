import json

import boto3

from app.personas import Persona

MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
REGION = "us-east-1"
MAX_TOKENS = 1024

DEFAULT_SYSTEM_PROMPT = (
    "You are Dr. Sarah Chen, a friendly and experienced general "
    "practitioner taking part in a training roleplay conversation. "
    "Speak warmly and professionally, ask relevant follow-up questions, "
    "and respond the way a real GP would in a consultation. This is a "
    "roleplay for practice and learning purposes only, not real medical "
    "care: do not provide actual diagnoses or medical advice, and if the "
    "user describes a real medical emergency, tell them to contact real "
    "emergency services immediately."
)

DIFFICULTY_INSTRUCTIONS = {
    "easy": (
        "Be receptive and cooperative; raise at most one mild objection "
        "and accept a reasonable response to it."
    ),
    "medium": (
        "Be professionally skeptical; raise two or three realistic "
        "objections before being persuaded, consistent with the mood "
        "described above."
    ),
    "hard": (
        "Be highly resistant and time-pressured; raise multiple firm "
        "objections, push back on weak reasoning, and only concede if the "
        "user's argument is genuinely strong."
    ),
}

_client = boto3.client("bedrock-runtime", region_name=REGION)


def build_system_prompt(persona: Persona | None, session: dict | None) -> str:
    if persona is None or session is None:
        return DEFAULT_SYSTEM_PROMPT

    difficulty_instruction = DIFFICULTY_INSTRUCTIONS[session["difficulty"]]
    return (
        f"{persona.base_description}\n\n"
        f"Scenario: {session['scenario']}\n"
        f"Conversation objective: {session['objective']}\n"
        f"Persona mood/behavior for this conversation: {session['mood']}\n"
        f"Difficulty: {difficulty_instruction}\n\n"
        f"{persona.safety_framing}"
    )


def build_request_body(
    messages: list,
    persona: Persona | None = None,
    session: dict | None = None,
) -> dict:
    return {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": MAX_TOKENS,
        "system": build_system_prompt(persona, session),
        "messages": messages,
    }


def extract_reply_text(response_body: dict) -> str:
    return response_body["content"][0]["text"]


def get_reply(
    messages: list,
    persona: Persona | None = None,
    session: dict | None = None,
) -> str:
    body = build_request_body(messages, persona, session)

    response = _client.invoke_model(
        modelId=MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body),
    )

    response_body = json.loads(response["body"].read())
    return extract_reply_text(response_body)
