import json

import boto3

MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
REGION = "us-east-1"
MAX_TOKENS = 1024

_client = boto3.client("bedrock-runtime", region_name=REGION)


def build_request_body(message: str) -> dict:
    return {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": MAX_TOKENS,
        "messages": [{"role": "user", "content": message}],
    }


def extract_reply_text(response_body: dict) -> str:
    return response_body["content"][0]["text"]


def get_reply(message: str) -> str:
    body = build_request_body(message)

    response = _client.invoke_model(
        modelId=MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body),
    )

    response_body = json.loads(response["body"].read())
    return extract_reply_text(response_body)
