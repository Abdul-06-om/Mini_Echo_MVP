# Step 5: Basic Chat Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A static HTML page you can open in a browser, type a message into, and get a real reply from the AI persona — using the `/chat` endpoint built in Steps 3-4.

**Architecture:** The page is served by the *same* FastAPI app, from a new `GET /` route returning `static/index.html`, instead of being opened as a standalone `file://` page. This was a specific recommendation from Step 3's final review: opening the HTML file directly would hit a browser CORS error when it tries to `fetch()` the backend on another origin/port; serving it from the same FastAPI app avoids that entirely, with no CORS middleware needed. The page is one self-contained file — inline `<style>` and inline `<script>`, plain JavaScript, no build step, no framework.

**Tech Stack:** FastAPI (`FileResponse`), plain HTML/CSS/JS (per spec section 4 — no frontend framework, no build tools)

**Spec:** `/Users/abdulrahman/Desktop/Mini_Echo_MVP/PROJECT.md`

## Global Constraints

- Frontend: plain HTML + CSS + vanilla JavaScript only — no React/Vue/build tools (per spec section 4)
- The page is served from the FastAPI app itself (`GET /`), not opened as a local file — this avoids a CORS error when calling `/chat`
- `/chat`'s request/response contract is unchanged from Step 3-4: `{"message": "<string>"}` in, `{"reply": "<string>"}` out. The frontend sends only the current message, not prior history — Step 6 is where conversation history is added, on both the frontend and backend together. **Do not add any history-sending logic in this task** — it's staged for Step 6.
- **No error handling for a failed `/chat` call in this task** (e.g. network error, non-200 response) — Step 7 ("Disclaimer + graceful errors") is explicitly where that's added. A failed request in this task may simply not display a reply; that's acceptable for now.
- **No visible disclaimer banner in this task** — also Step 7's job (per spec section 6, feature breakdown). The page's descriptive text may mention this is a roleplay, but a dedicated disclaimer UI element is out of scope here.
- Backend must remain stateless (per spec section 1) — this task adds no server-side storage; any "conversation so far" shown on the page lives only in the browser tab's own JavaScript state and is not sent back to the server as history yet.
- Known, expected limitation for manual testing (not a bug to fix in this task): because the backend has no conversation memory until Step 6, the AI will not remember earlier messages in the same browser session — each reply is generated fresh. The chat transcript on screen will still show the full back-and-forth (that's just the page displaying what was typed/received), but the AI itself won't reference its own earlier replies yet.

---

### Task 1: Serve a Chat Page from FastAPI

**Files:**
- Create: `static/index.html`
- Modify: `app/main.py`
- Modify: `tests/test_main.py`

**Interfaces:**
- Consumes: the existing `POST /chat` endpoint (Steps 3-4), contract unchanged.
- Produces: `GET /` route on the existing `app` object, returning `static/index.html` as `text/html`.

- [ ] **Step 1: Write the failing test**

Modify `tests/test_main.py` to add a new test. The full file should read:
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

    response = client.post("/chat", json={"message": "Hello"})

    assert response.status_code == 200
    assert response.json() == {"reply": "Mocked AI reply"}
    mock_get_reply.assert_called_once_with("Hello")
```

- [ ] **Step 2: Run the test and verify it fails**

Run:
```bash
pytest tests/test_main.py -v
```

Expected: FAIL — `test_index_serves_html_page` fails with a 404, since there is no `GET /` route yet.

- [ ] **Step 3: Write the frontend page**

Create `static/index.html`:
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
  <p>Roleplay conversation with an AI general practitioner. This is practice only, not real medical advice.</p>
  <div id="chat"></div>
  <form id="chat-form">
    <input id="message-input" type="text" placeholder="Type a message..." autocomplete="off" required>
    <button type="submit">Send</button>
  </form>

  <script>
    const chat = document.getElementById('chat');
    const form = document.getElementById('chat-form');
    const input = document.getElementById('message-input');

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
      const message = input.value.trim();
      if (!message) return;

      addMessage(message, 'user');
      input.value = '';

      const response = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: message }),
      });

      const data = await response.json();
      addMessage(data.reply, 'ai');
    });
  </script>
</body>
</html>
```

- [ ] **Step 4: Wire up the route**

Modify `app/main.py` so the full file reads:
```python
from fastapi import FastAPI
from fastapi.responses import FileResponse
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


@app.get("/")
def index():
    return FileResponse("static/index.html")


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    reply = get_reply(request.message)
    return ChatResponse(reply=reply)
```

- [ ] **Step 5: Run the test and verify it passes**

Run:
```bash
pytest tests/test_main.py -v
```

Expected: PASS — `test_health_check_returns_ok`, `test_index_serves_html_page`, and `test_chat_endpoint_returns_ai_reply` all show PASSED.

- [ ] **Step 6: Run the full test suite**

Run:
```bash
pytest -v
```

Expected: PASS — 7 tests total (Step 4's 6 plus this task's new `test_index_serves_html_page`), all PASSED.

- [ ] **Step 7: Manually chat in the browser**

If a server is already running in the background from an earlier step (started with `--reload`), it will pick up these changes automatically; otherwise start it:
```bash
source venv/bin/activate
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/` in a browser. Type a message (e.g. "Hi doctor, I've had a mild headache since this morning") and click Send.

Expected: your message appears in the chat area, then a reply from the AI persona appears shortly after. Try a second message — the transcript on screen will show both exchanges, but remember (per this plan's Global Constraints) the AI itself won't actually reference the first message yet; that's expected until Step 6 adds conversation history. Report what you saw, including whether the page looked and behaved reasonably, not just whether a reply appeared.

- [ ] **Step 8: Commit**

```bash
git add static app/main.py tests/test_main.py
git commit -m "feat: add basic chat frontend served by FastAPI"
```

Expected: `git log --oneline -1` shows the new commit.
