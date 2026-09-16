import json

import boto3

MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
REGION = "us-east-1"
TEST_MESSAGE = "Say hello in exactly 3 words."


def build_request_body(message: str) -> dict:
    return {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 50,
        "messages": [{"role": "user", "content": message}],
    }


def extract_reply_text(response_body: dict) -> str:
    return response_body["content"][0]["text"]


def main() -> None:
    client = boto3.client("bedrock-runtime", region_name=REGION)
    body = build_request_body(TEST_MESSAGE)

    response = client.invoke_model(
        modelId=MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body),
    )

    response_body = json.loads(response["body"].read())
    reply = extract_reply_text(response_body)

    print(f"Sent: {TEST_MESSAGE}")
    print(f"Bedrock replied: {reply}")


if __name__ == "__main__":
    main()
