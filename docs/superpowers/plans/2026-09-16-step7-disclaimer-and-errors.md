# Step 7: Disclaimer + Graceful Errors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The last step of the MVP. Add a visible disclaimer banner, and make both the backend and frontend fail gracefully when the Bedrock call fails — instead of leaking raw AWS error details to the client, or corrupting the browser's conversation state.

**Architecture:** Two independent, small changes to files that already exist — no new files.
1. **Backend** (`app/main.py`): wrap the existing `get_reply(messages)` call in a `try/except`. On failure, log the real exception server-side (via Python's standard `logging` module — visible in the server console, never sent to the client) and return a clean `503` with a generic message, via FastAPI's `HTTPException`. This directly addresses a security note raised in Step 3's and Step 6's final reviews: never return raw `botocore`/AWS exception text to the browser (it can embed account IDs and ARNs).
2. **Frontend** (`static/index.html`): add a visible disclaimer banner (a distinct styled element, not just body text). Add error handling around the `fetch('/chat', ...)` call: on a failed request, show a friendly error message in the chat area — and, critically, **roll back the optimistically-pushed user turn** from the `conversation` array on failure. This directly fixes the specific bug Step 6's final review identified: without this rollback, a failed request leaves an unanswered user turn in the array, and the next message would create two consecutive `"user"` turns, which Bedrock's alternating-role requirement rejects — silently wedging the whole session with repeated 422s until the page is refreshed.

**Tech Stack:** Python's standard `logging` module, FastAPI's `HTTPException` (no new dependencies; same stack as Steps 1-6)

**Spec:** `/Users/abdulrahman/Desktop/Mini_Echo_MVP/PROJECT.md`

## Global Constraints

- The client must never receive raw exception text from a failed Bedrock call — only a generic, friendly message. The real error is logged server-side only (per spec section 2's "in scope: Basic error handling").
- The disclaimer must be a distinct, visible UI element — not just descriptive paragraph text (per spec section 2, "in scope: A visible disclaimer that this is not real medical advice").
- On a failed `/chat` request, the frontend must not leave the `conversation` array in a state where two consecutive `"user"` turns could occur on the next attempt. The just-pushed user turn must be rolled back (removed from the array) on failure; it's fine for the failed message to remain visible in the chat *display* (so the user can see what they tried to send) as long as it's not left dangling in the array sent to the backend.
- No message-length or history-length cap in this task — still out of scope, still deferred beyond the MVP (per Steps 6/7 planning history).
- No persona/`SYSTEM_PROMPT` changes in this task — this task's file changes don't touch that constant at all.
- Backend remains stateless (per spec section 1) — logging a server-side error is not conversation state; nothing is persisted.
- This is the final step of the 7-step MVP (per spec section 6) — no functionality beyond disclaimer + graceful errors belongs in this task.

---

### Task 1: Disclaimer Banner and Graceful Error Handling

**Files:**
- Modify: `app/main.py`
- Modify: `static/index.html`
- Modify: `tests/test_main.py`

**Interfaces:**
- Consumes: the existing `get_reply(messages: list) -> str` from Step 6 (unchanged signature) and the existing `POST /chat` contract (unchanged request/response shape on the *success* path).
- Produces: `POST /chat` now also returns HTTP `503` with body `{"detail": "The AI service is temporarily unavailable. Please try again."}` when `get_reply` raises any exception.
- Produces: a `#disclaimer` element in `static/index.html`, and a `.message.error` styling class for error bubbles shown in the chat area.

- [ ] **Step 1: Write the failing test**

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


@patch("app.main.get_reply")
def test_chat_endpoint_returns_503_when_bedrock_fails(mock_get_reply):
    mock_get_reply.side_effect = Exception("boom: sensitive AWS detail")

    response = client.post("/chat", json={"messages": [{"role": "user", "content": "Hello"}]})

    assert response.status_code == 503
    assert response.json() == {
        "detail": "The AI service is temporarily unavailable. Please try again."
    }
    assert "sensitive AWS detail" not in response.text
```

- [ ] **Step 2: Run the test and verify it fails**

Run:
```bash
pytest tests/test_main.py -v
```

Expected: FAIL — `test_chat_endpoint_returns_503_when_bedrock_fails` fails, because there's no `try/except` around `get_reply` yet. Since FastAPI's `TestClient` re-raises unhandled exceptions by default (rather than turning them into a 500 response), the test will actually error out with the mocked `Exception("boom: sensitive AWS detail")` propagating up through the test itself — that error is the expected "fail," not a normal assertion failure.

- [ ] **Step 3: Add backend error handling**

Modify `app/main.py` so the full file reads:
```python
import logging
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.bedrock import get_reply

logger = logging.getLogger(__name__)

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

    try:
        reply = get_reply(messages)
    except Exception:
        logger.exception("Bedrock call failed")
        raise HTTPException(
            status_code=503,
            detail="The AI service is temporarily unavailable. Please try again.",
        )

    return ChatResponse(reply=reply)
```

- [ ] **Step 4: Run the test and verify it passes**

Run:
```bash
pytest tests/test_main.py -v
```

Expected: PASS — all tests in `tests/test_main.py`, including `test_chat_endpoint_returns_503_when_bedrock_fails`, show PASSED.

- [ ] **Step 5: Run the full test suite**

Run:
```bash
pytest -v
```

Expected: PASS — 9 tests total (Step 6's 8 plus this task's new `test_chat_endpoint_returns_503_when_bedrock_fails`), all PASSED.

- [ ] **Step 6: Add the disclaimer banner and frontend error handling**

Modify `static/index.html` so the full file reads:
```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Mini ECHO</title>
<style>
  body {
    font-family: system-ui, sans-serif;
    max-width: 640px;
    margin: 2rem auto;
    padding: 0 1rem;
  }
  h1 {
    font-size: 1.25rem;
  }
  #disclaimer {
    background: #fff3cd;
    border: 1px solid #ffe69c;
    color: #664d03;
    padding: 0.75rem 1rem;
    border-radius: 8px;
    margin-bottom: 1rem;
    font-size: 0.9rem;
  }
  #chat {
    border: 1px solid #ccc;
    border-radius: 8px;
    height: 400px;
    overflow-y: auto;
    padding: 1rem;
    margin-bottom: 1rem;
  }
  .message {
    margin-bottom: 0.75rem;
  }
  .message.user {
    text-align: right;
  }
  .message .bubble {
    display: inline-block;
    padding: 0.5rem 0.75rem;
    border-radius: 8px;
    max-width: 80%;
  }
  .message.user .bubble {
    background: #d1e7ff;
  }
  .message.ai .bubble {
    background: #f0f0f0;
  }
  .message.error .bubble {
    background: #ffe0e0;
    color: #900;
  }
  form {
    display: flex;
    gap: 0.5rem;
  }
  input {
    flex: 1;
    padding: 0.5rem;
  }
  button {
    padding: 0.5rem 1rem;
  }
</style>
</head>
<body>
  <h1>Mini ECHO</h1>
  <div id="disclaimer">This is an AI roleplay for practice only — not real medical advice. In a real emergency, contact emergency services immediately.</div>
  <div id="chat"></div>
  <form id="chat-form">
    <input id="message-input" type="text" placeholder="Type a message..." autocomplete="off" required>
    <button type="submit">Send</button>
  </form>

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

        if (!response.ok) {
          throw new Error('Request failed with status ' + response.status);
        }

        const data = await response.json();
        conversation.push({ role: 'assistant', content: data.reply });
        addMessage(data.reply, 'ai');
      } catch (error) {
        conversation.pop();
        addMessage('Something went wrong. Please try again.', 'error');
      } finally {
        isSending = false;
        input.disabled = false;
        button.disabled = false;
        input.focus();
      }
    });
  </script>
</body>
</html>
```

There is no automated test for this file's JavaScript (a static page, not covered by pytest) — this is expected and matches Steps 5-6's precedent.

- [ ] **Step 7: Manually verify both the failure path and the happy path against the live server**

If a server is already running in the background from an earlier step (started with `--reload`), it will pick up these changes automatically; otherwise start it:
```bash
source venv/bin/activate
uvicorn app.main:app --reload
```

**Simulate a real failure safely** (without touching AWS credentials or account settings, which remain off-limits): send an empty `messages` array. Pydantic accepts this (an empty list is valid), so it reaches `get_reply([])`, which makes a real call to Bedrock — and Bedrock's API rejects an empty messages list, giving a genuine live failure to exercise the new error handling:
```bash
curl -i -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": []}'
```

Expected: HTTP `503`, body `{"detail":"The AI service is temporarily unavailable. Please try again."}` — no AWS/botocore exception text anywhere in the response. Then check the server's console output (or `/tmp/mini-echo-server.log` if that's where it's logging) for a logged traceback from `logger.exception("Bedrock call failed")` — confirming the real error IS captured server-side for debugging, just never sent to the client.

**Then confirm the happy path still works**, to make sure the error handling didn't break normal use:
```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Hello"}]}'
```

Expected: HTTP `200` with a real AI reply, same as before.

The interactive browser check (confirming the disclaimer banner is visibly styled and prominent, and that a simulated frontend failure shows a friendly red error bubble without breaking the ability to send further messages) should be done by the human user afterward — neither the implementer nor the controller has real browser access in this environment. Say so plainly in the report.

- [ ] **Step 8: Commit**

```bash
git add app/main.py static/index.html tests/test_main.py
git commit -m "feat: add disclaimer banner and graceful error handling"
```

Expected: `git log --oneline -1` shows the new commit. This completes the 7-step MVP build order from PROJECT.md.
