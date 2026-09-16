# Step 4: Add the Persona Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the AI behind `/chat` actually play the fixed healthcare persona (a general practitioner), instead of replying as a generic assistant — by giving Bedrock a system prompt.

**Architecture:** Exactly one new piece: a `SYSTEM_PROMPT` constant in `app/bedrock.py`, included as the `"system"` key in the request body `build_request_body` already sends to Bedrock. This is the extension point the Step 3 final review specifically identified as clean ("the system prompt belongs as a `system` key inside `build_request_body`; `get_reply`'s signature unchanged"). No route, schema, or test-mocking changes to `app/main.py` are needed — the persona lives entirely inside `app/bedrock.py`.

**Tech Stack:** Python 3, boto3 (no new dependencies; same stack as Steps 1-3)

**Spec:** `/Users/abdulrahman/Desktop/Mini_Echo_MVP/PROJECT.md`

## Global Constraints

- Language: Python 3, dependencies managed via `venv` + `pip` (per spec section 4)
- AI provider: AWS Bedrock via `boto3`, model `us.anthropic.claude-haiku-4-5-20251001-v1:0`, region `us-east-1` (unchanged from Steps 2-3)
- One fixed persona only — a "helpful general practitioner" (per spec section 2, "In scope"). No persona selection, no multiple personas (explicitly out of scope per spec section 2).
- The persona's system prompt must make clear this is a roleplay/training conversation, not real medical care, and must instruct the AI to direct the user to real emergency services if they describe an actual emergency. (This is a property of the persona's instructions, not the separate UI disclaimer banner — that banner is Step 7's job and is a different, additional safeguard.)
- `get_reply(message: str) -> str`'s public signature does not change in this task (per Step 3's plan, its signature only changes in Step 6 when conversation history is added) — the persona is added purely inside `build_request_body`.
- Backend must remain stateless (per spec section 1) — the system prompt is a constant, not per-user state.
- No automated test may make a real network call to AWS — the live persona check is manual, same as Steps 2-3.

---

### Task 1: Persona System Prompt

**Files:**
- Modify: `app/bedrock.py`
- Modify: `tests/test_bedrock.py`

**Interfaces:**
- Consumes: the existing `build_request_body(message: str) -> dict` and `get_reply(message: str) -> str` from Step 3 — their signatures do not change.
- Produces: `app.bedrock.SYSTEM_PROMPT` (str) — later steps (Step 6's conversation history, and any future persona-related work) can reference this constant rather than redefining persona text.
- Produces: `build_request_body`'s return dict now includes a `"system"` key alongside the existing `"anthropic_version"`, `"max_tokens"`, and `"messages"` keys.

- [ ] **Step 1: Write the failing test**

Modify `tests/test_bedrock.py` so the full file reads:
```python
from app.bedrock import SYSTEM_PROMPT, build_request_body, extract_reply_text


def test_build_request_body_has_correct_shape():
    body = build_request_body("Hello there")

    assert body == {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1024,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": "Hello there"}],
    }


def test_extract_reply_text_returns_the_text_field():
    response_body = {
        "content": [{"type": "text", "text": "Hello world today."}]
    }

    assert extract_reply_text(response_body) == "Hello world today."
```

- [ ] **Step 2: Run the test and verify it fails**

Run:
```bash
pytest tests/test_bedrock.py -v
```

Expected: FAIL — `ImportError: cannot import name 'SYSTEM_PROMPT' from 'app.bedrock'` (it doesn't exist yet), or `test_build_request_body_has_correct_shape` fails because the actual return value has no `"system"` key.

- [ ] **Step 3: Write the minimal implementation**

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


def build_request_body(message: str) -> dict:
    return {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": MAX_TOKENS,
        "system": SYSTEM_PROMPT,
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

- [ ] **Step 4: Run the test and verify it passes**

Run:
```bash
pytest tests/test_bedrock.py -v
```

Expected: PASS — both tests in `tests/test_bedrock.py` show PASSED.

- [ ] **Step 5: Run the full test suite**

Run:
```bash
pytest -v
```

Expected: PASS — all 6 tests (unchanged count from Step 3: `test_bedrock.py` x2, `test_bedrock_check.py` x2, `test_main.py` x2) show PASSED. `test_main.py::test_chat_endpoint_returns_ai_reply` still passes unmodified, since it mocks `get_reply` entirely and never touches `build_request_body`.

- [ ] **Step 6: Manually verify the persona comes through in a live reply**

If the server from Step 3's manual testing is still running, it will auto-reload (started with `--reload`); otherwise start it:
```bash
source venv/bin/activate
uvicorn app.main:app --reload
```

Run:
```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hi doctor, I have had a mild headache since this morning, what should I do?"}'
```

Expected: a JSON reply that sounds like a GP responding in a consultation (e.g. asks a follow-up question, or gives general, cautious, non-diagnostic guidance) — not a generic "I'm an AI assistant" style reply. This is a judgment call, not an exact string match: read the reply and confirm it plausibly sounds like the persona. If it doesn't sound like the persona at all, report that as a concern rather than deciding on your own whether to adjust the prompt wording.

- [ ] **Step 7: Commit**

```bash
git add app/bedrock.py tests/test_bedrock.py
git commit -m "feat: add general practitioner persona to Bedrock requests"
```

Expected: `git log --oneline -1` shows the new commit.
