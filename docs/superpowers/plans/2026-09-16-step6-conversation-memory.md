# Step 6: Conversation Memory Within a Session Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the AI remember earlier messages in the same browser session — by having the frontend send the *whole* conversation so far on every request, instead of just the latest message.

**Architecture:** This is the change PROJECT.md's architecture section always described (`/chat` receiving "the whole conversation") and that Steps 3-4's reviews specifically pre-validated: `build_request_body` and `get_reply` move from taking one `message: str` to taking `messages: list[dict]` (a list of `{"role": "user"|"assistant", "content": str}` turns, the shape Bedrock's Messages API already expects). `/chat`'s request shape changes from `{"message": str}` to `{"messages": [...]}`. On the frontend, a JS array (`conversation`) accumulates every user message and AI reply as they happen, and the *whole* array is sent with each new request. **The backend still stores nothing** — the browser tab is the only place this history lives, matching spec section 1's "Key simplicity decision" (stateless backend, conversation lost on refresh) exactly. This is a breaking change to `/chat`'s request contract — that's expected, not a bug; it's what Steps 3-4's plans explicitly staged for this step.

**Tech Stack:** Python 3, FastAPI, boto3, plain JS (no new dependencies; same stack as Steps 1-5)

**Spec:** `/Users/abdulrahman/Desktop/Mini_Echo_MVP/PROJECT.md`

## Global Constraints

- Backend remains stateless — no database, no server-side session store. The full conversation is sent by the browser on every request and held nowhere else (per spec section 1).
- `/chat`'s new request contract: `{"messages": [{"role": "user"|"assistant", "content": "<string>"}, ...]}`. Response contract unchanged: `{"reply": "<string>"}`.
- `role` is constrained to exactly `"user"` or `"assistant"` (via Pydantic `Literal`) — this is cheap type safety, not scope creep, since it directly matches what Bedrock's API accepts.
- No message-length or history-length cap in this task — that's a deferred hardening item from earlier reviews, still out of scope here (would belong to Step 7 or later, not this step).
- No persona change — `SYSTEM_PROMPT` in `app/bedrock.py` is untouched by this task.
- No new error handling — Step 7's job, same as before.
- No automated test may make a real network call to AWS — the live multi-turn memory check is manual, same as Steps 2-5.

---

### Task 1: Send and Use Full Conversation History

**Files:**
- Modify: `app/bedrock.py`
- Modify: `app/main.py`
- Modify: `tests/test_bedrock.py`
- Modify: `tests/test_main.py`
- Modify: `static/index.html`

**Interfaces:**
- Produces: `app.bedrock.build_request_body(messages: list[dict]) -> dict` — **signature changed** from Step 4's `build_request_body(message: str)`. Callers now pass the full conversation as a list of `{"role": ..., "content": ...}` dicts.
- Produces: `app.bedrock.get_reply(messages: list[dict]) -> str` — **signature changed** from Step 3's `get_reply(message: str)`, for the same reason.
- Produces: `app.main.ChatMessage` (Pydantic model: `role: Literal["user", "assistant"]`, `content: str`) and `app.main.ChatRequest.messages: list[ChatMessage]` — replaces Step 3's `ChatRequest.message: str`.
- Consumes (frontend): the existing `POST /chat` route, now with the new request shape.

- [ ] **Step 1: Write the failing tests**

Modify `tests/test_bedrock.py` so the full file reads:
```python
from app.bedrock import SYSTEM_PROMPT, build_request_body, extract_reply_text


def test_build_request_body_has_correct_shape():
    messages = [{"role": "user", "content": "Hello there"}]

    body = build_request_body(messages)

    assert body == {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1024,
        "system": SYSTEM_PROMPT,
        "messages": messages,
    }


def test_extract_reply_text_returns_the_text_field():
    response_body = {
        "content": [{"type": "text", "text": "Hello world today."}]
    }

    assert extract_reply_text(response_body) == "Hello world today."
```

Modify `tests/test_main.py` so the full file reads:
```python
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check_returns_ok():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_index_serves_html_page():
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


@patch("app.main.get_reply")
def test_chat_endpoint_returns_ai_reply(mock_get_reply):
    mock_get_reply.return_value = "Mocked AI reply"

    response = client.post("/chat", json={"messages": [{"role": "user", "content": "Hello"}]})

    assert response.status_code == 200
    assert response.json() == {"reply": "Mocked AI reply"}
    mock_get_reply.assert_called_once_with([{"role": "user", "content": "Hello"}])


@patch("app.main.get_reply")
def test_chat_endpoint_passes_full_history_to_get_reply(mock_get_reply):
    mock_get_reply.return_value = "Second reply"
    history = [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello! How can I help?"},
        {"role": "user", "content": "I have a headache"},
    ]

    response = client.post("/chat", json={"messages": history})

    assert response.status_code == 200
    assert response.json() == {"reply": "Second reply"}
    mock_get_reply.assert_called_once_with(history)
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:
```bash
pytest tests/test_bedrock.py tests/test_main.py -v
```

Expected: FAIL — `test_build_request_body_has_correct_shape` fails because `build_request_body` still expects a string, not a list; `test_chat_endpoint_returns_ai_reply` and `test_chat_endpoint_passes_full_history_to_get_reply` fail because `/chat` still expects `{"message": str}`, so posting `{"messages": [...]}` returns a 422 validation error instead of 200.

- [ ] **Step 3: Update the Bedrock module**

Modify `app/bedrock.py` so the full file reads:
```python
import json

import boto3

MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
REGION = "us-east-1"
MAX_TOKENS = 1024

SYSTEM_PROMPT = (
    "You are Dr. Sarah Chen, a friendly and experienced general "
    "practitioner taking part in a training roleplay conversation. "
    "Speak warmly and professionally, ask relevant follow-up questions, "
    "and respond the way a real GP would in a consultation. This is a "
    "roleplay for practice and learning purposes only, not real medical "
    "care: do not provide actual diagnoses or medical advice, and if the "
    "user describes a real medical emergency, tell them to contact real "
    "emergency services immediately."
)

_client = boto3.client("bedrock-runtime", region_name=REGION)


def build_request_body(messages: list) -> dict:
    return {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": MAX_TOKENS,
        "system": SYSTEM_PROMPT,
        "messages": messages,
    }


def extract_reply_text(response_body: dict) -> str:
    return response_body["content"][0]["text"]


def get_reply(messages: list) -> str:
    body = build_request_body(messages)

    response = _client.invoke_model(
        modelId=MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body),
    )

    response_body = json.loads(response["body"].read())
    return extract_reply_text(response_body)
```

- [ ] **Step 4: Update the route**

Modify `app/main.py` so the full file reads:
```python
from typing import Literal

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.bedrock import get_reply

app = FastAPI()


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


class ChatResponse(BaseModel):
    reply: str


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/")
def index():
    return FileResponse("static/index.html")


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    messages = [{"role": m.role, "content": m.content} for m in request.messages]
    reply = get_reply(messages)
    return ChatResponse(reply=reply)
```

- [ ] **Step 5: Run the tests and verify they pass**

Run:
```bash
pytest tests/test_bedrock.py tests/test_main.py -v
```

Expected: PASS — all tests in both files show PASSED.

- [ ] **Step 6: Run the full test suite**

Run:
```bash
pytest -v
```

Expected: PASS — 8 tests total (Step 5's 7 plus this task's new `test_chat_endpoint_passes_full_history_to_get_reply`), all PASSED. `tests/test_bedrock_check.py` (Step 2's frozen script tests) are unaffected — `scripts/bedrock_check.py` is a separate, untouched module.

- [ ] **Step 7: Update the frontend to send and accumulate history**

Modify `static/index.html` so the `<script>` block reads (rest of the file — HTML, CSS — unchanged):
```html
  <script>
    const chat = document.getElementById('chat');
    const form = document.getElementById('chat-form');
    const input = document.getElementById('message-input');
    const button = form.querySelector('button');
    let isSending = false;
    let conversation = [];

    function addMessage(text, sender) {
      const div = document.createElement('div');
      div.className = 'message ' + sender;
      const bubble = document.createElement('span');
      bubble.className = 'bubble';
      bubble.textContent = text;
      div.appendChild(bubble);
      chat.appendChild(div);
      chat.scrollTop = chat.scrollHeight;
    }

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (isSending) return;

      const message = input.value.trim();
      if (!message) return;

      isSending = true;
      input.disabled = true;
      button.disabled = true;

      try {
        addMessage(message, 'user');
        input.value = '';
        conversation.push({ role: 'user', content: message });

        const response = await fetch('/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ messages: conversation }),
        });

        const data = await response.json();
        conversation.push({ role: 'assistant', content: data.reply });
        addMessage(data.reply, 'ai');
      } finally {
        isSending = false;
        input.disabled = false;
        button.disabled = false;
        input.focus();
      }
    });
  </script>
```

There is no automated test for this file's JavaScript (a static page, not covered by pytest) — this is expected and matches Step 5's precedent.

- [ ] **Step 8: Manually verify the AI actually remembers context**

If a server is already running in the background from an earlier step (started with `--reload`), it will pick up these changes automatically; otherwise start it:
```bash
source venv/bin/activate
uvicorn app.main:app --reload
```

Run this curl sequence to prove multi-turn memory works at the API level:
```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [
    {"role": "user", "content": "My name is Alex."},
    {"role": "assistant", "content": "Nice to meet you, Alex! How can I help you today?"},
    {"role": "user", "content": "What is my name?"}
  ]}'
```

Expected: the reply text should mention "Alex" — proving the AI is actually using the conversation history it was given, not just answering the last message in isolation. This is a judgment call: read the reply and confirm it plausibly references the earlier turn. If it doesn't, report that as a concern rather than deciding on your own how to adjust anything.

The interactive browser check (typing a real back-and-forth conversation and confirming the AI remembers it) should be done by the human user afterward — neither the implementer nor the controller has real browser access in this environment. Say so plainly in the report rather than claiming a visual browser test was performed.

- [ ] **Step 9: Commit**

```bash
git add app/bedrock.py app/main.py tests/test_bedrock.py tests/test_main.py static/index.html
git commit -m "feat: add conversation memory within a session"
```

Expected: `git log --oneline -1` shows the new commit.
