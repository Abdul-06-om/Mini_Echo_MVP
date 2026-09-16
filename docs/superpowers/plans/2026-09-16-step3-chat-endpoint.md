# Step 3: /chat Endpoint (No Persona Yet) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `POST /chat` endpoint to the FastAPI app that takes one user message, sends it to AWS Bedrock, and returns the AI's reply as JSON — proving the web layer and the AI layer work together, before persona (Step 4), a frontend (Step 5), or conversation history (Step 6) are added.

**Architecture:** Bedrock-calling logic moves from the standalone diagnostic script (`scripts/bedrock_check.py`, built in Step 2, left untouched) into a new `app/bedrock.py` module that the FastAPI app can import. `app/main.py` gets one new route, `POST /chat`, backed by Pydantic request/response models. This endpoint intentionally accepts a single message field, not a conversation list — Step 6 is where the request shape changes to carry full history; building that now would be ahead of the plan's own staged design (see PROJECT.md section 6).

**Tech Stack:** Python 3, FastAPI, boto3, pytest (same stack as Steps 1-2; no new dependencies)

**Spec:** `/Users/abdulrahman/Desktop/Mini_Echo_MVP/PROJECT.md`

## Global Constraints

- Language: Python 3, dependencies managed via `venv` + `pip` (per spec section 4)
- Web framework: FastAPI, served by Uvicorn (per spec section 4)
- AI provider: AWS Bedrock via `boto3` (per spec section 4)
- Model to call: **`us.anthropic.claude-haiku-4-5-20251001-v1:0`**, region **`us-east-1`** — same values verified working in Step 2
- Request body shape for `invoke_model`: `{"anthropic_version": "bedrock-2023-05-31", "max_tokens": <int>, "messages": [{"role": "user", "content": <str>}]}`; response reply text is at `content[0]["text"]` — same shapes verified in Step 2
- No AWS credentials of any kind in code — `boto3` must use the default credential chain only
- Backend must remain stateless — no server-side session storage, no database, no conversation persistence (per spec section 1)
- **No persona/system prompt in this task** — that is Step 4's job. The AI has no special instructions yet; it just replies as the base model.
- **No conversation history in this task** — `/chat` takes exactly one message per request (field name `message`, a string) and returns exactly one reply (field name `reply`, a string). Step 6 is where the request shape changes to accept the full conversation so far. A reviewer should not treat single-message-only as a gap in this task — it is the plan's intended scope.
- No automated test may make a real network call to AWS (per spec section 2 — smoke tests per step, not a suite that depends on live credentials). The live Bedrock call is verified manually in this task, the same way Step 2 verified it.

---

### Task 1: POST /chat Endpoint

**Files:**
- Create: `app/bedrock.py`
- Modify: `app/main.py`
- Create: `tests/test_bedrock.py`
- Modify: `tests/test_main.py`

**Interfaces:**
- Consumes: nothing from earlier tasks beyond the existing `app = FastAPI()` instance in `app/main.py` (from Step 1) and the request/response shapes verified in Step 2.
- Produces: `app.bedrock.get_reply(message: str) -> str` — sends one message to Bedrock and returns the reply text. Later steps (persona in Step 4, conversation history in Step 6) will change this function's signature — that is expected and out of scope for this task.
- Produces: `app.bedrock.MODEL_ID` (str) and `app.bedrock.REGION` (str) — same convention as `scripts/bedrock_check.py`, but this is a separate, independent module (the app must not import from `scripts/`).
- Produces: `POST /chat` route on the existing `app` object. Request body: `{"message": "<string>"}`. Response body: `{"reply": "<string>"}`. HTTP 200 on success.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_bedrock.py`:
```python
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
```

Modify `tests/test_main.py` to add a mocked test for the new route, so the full file reads:
```python
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check_returns_ok():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@patch("app.main.get_reply")
def test_chat_endpoint_returns_ai_reply(mock_get_reply):
    mock_get_reply.return_value = "Mocked AI reply"

    response = client.post("/chat", json={"message": "Hello"})

    assert response.status_code == 200
    assert response.json() == {"reply": "Mocked AI reply"}
    mock_get_reply.assert_called_once_with("Hello")
```

This test mocks `get_reply` (patched where `app/main.py` looks it up) so it verifies the route's wiring — that `/chat` calls `get_reply` with the message and returns its result as JSON — without making a real network call to AWS.

- [ ] **Step 2: Run the tests and verify they fail**

Run:
```bash
pytest tests/test_bedrock.py tests/test_main.py -v
```

Expected: FAIL — `tests/test_bedrock.py` fails with `ModuleNotFoundError: No module named 'app.bedrock'` (it doesn't exist yet), and `tests/test_main.py::test_chat_endpoint_returns_ai_reply` fails (the `/chat` route doesn't exist yet, so the POST returns 404, or the `@patch("app.main.get_reply")` target doesn't exist and errors with `AttributeError`).

- [ ] **Step 3: Write the minimal implementation**

Create `app/bedrock.py`:
```python
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
```

Modify `app/main.py` so the full file reads:
```python
from fastapi import FastAPI
from pydantic import BaseModel

from app.bedrock import get_reply

app = FastAPI()


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    reply = get_reply(request.message)
    return ChatResponse(reply=reply)
```

- [ ] **Step 4: Run the tests and verify they pass**

Run:
```bash
pytest tests/test_bedrock.py tests/test_main.py -v
```

Expected: PASS — all 3 tests (`test_build_request_body_has_correct_shape`, `test_extract_reply_text_returns_the_text_field`, `test_health_check_returns_ok`, `test_chat_endpoint_returns_ai_reply` — 4 total) show PASSED.

- [ ] **Step 5: Run the full test suite**

Run:
```bash
pytest -v
```

Expected: PASS — 6 tests total: `test_main.py` (2: health check + chat endpoint), `test_bedrock_check.py` (2, from Step 2), `test_bedrock.py` (2, new this task). All PASSED, no failures.

- [ ] **Step 6: Manually run the server and verify the live endpoint**

Run:
```bash
source venv/bin/activate
uvicorn app.main:app --reload
```

In another terminal (or via `! curl ...`):
```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Say hello in exactly 3 words."}'
```

Expected: a JSON response like `{"reply":"Hello there friend!"}` — a real reply from Bedrock, not the mocked test value. No stack trace, no credential values printed. Stop the server afterward with `Ctrl+C`. If this fails with an AWS error, stop and report it — do not modify AWS credentials or account settings.

- [ ] **Step 7: Commit**

```bash
git add app tests
git commit -m "feat: add /chat endpoint calling Bedrock"
```

Expected: `git log --oneline -1` shows the new commit.
