from app.bedrock import build_request_body, extract_reply_text


def test_build_request_body_has_correct_shape():
    body = build_request_body("Hello there")

    assert body == {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": "Hello there"}],
    }


def test_extract_reply_text_returns_the_text_field():
    response_body = {
        "content": [{"type": "text", "text": "Hello world today."}]
    }

    assert extract_reply_text(response_body) == "Hello world today."
