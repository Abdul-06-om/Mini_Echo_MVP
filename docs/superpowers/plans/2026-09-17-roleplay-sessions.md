# Roleplay Sessions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user configure a structured roleplay (persona, scenario, objective, mood, difficulty) that becomes dynamic system-prompt context for the existing Bedrock conversation, shared by Text Chat and Live Voice, without touching either of those verified systems' call paths when no roleplay session is active.

**Architecture:** `app/personas.py` (new) holds a small persona registry. `app/bedrock.py`'s hardcoded system prompt becomes a pure `build_system_prompt(persona, session)` function, falling back byte-identically to today's prompt when no persona/session is given. `app/main.py`'s `/chat` route gains an optional `session` field and a new `GET /personas` route. `static/index.html` gains a "Start Roleplay" setup form that, once submitted, is included by the *existing* shared `sendToSarah()` pipeline on every subsequent `/chat` call — Live Voice and Text Chat pick this up for free since they already call that one function.

**Tech Stack:** Same as the rest of the project — FastAPI/pydantic backend, plain JS frontend, pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-09-17-roleplay-sessions-design.md`

## Global Constraints

- **Backward compatibility is load-bearing, not optional.** When a `/chat` request omits `session`, the backend must call `get_reply(messages)` with the exact same call signature as today — this is what keeps the three existing `/chat` tests in `tests/test_main.py` (`test_chat_endpoint_returns_ai_reply`, `test_chat_endpoint_passes_full_history_to_get_reply`, `test_chat_endpoint_returns_503_when_bedrock_fails`) passing **unmodified**. Only call `get_reply(messages, persona=persona, session=session_dict)` when a session was actually supplied.
- `SYSTEM_PROMPT` in `app/bedrock.py` is renamed to `DEFAULT_SYSTEM_PROMPT` (value unchanged) — this is a spec-mandated rename, not scope creep, and it means `tests/test_bedrock.py`'s existing import/usage of `SYSTEM_PROMPT` must be updated to `DEFAULT_SYSTEM_PROMPT` in the same task that renames it. `scripts/bedrock_check.py` does not reference `SYSTEM_PROMPT` at all (confirmed) — the frozen script is unaffected and must not be touched.
- No new API key, account, or AWS permission. No backend persistence — `RoleplaySessionRequest` is held client-side only, exactly like the existing `conversation` array.
- Do not modify: `app/avatar_simli.py`, `app/avatar_provider.py`, `app/tts.py`, `avatar-src/doctor-avatar.js`, `static/dist/avatar-bundle.js`, `static/stt-web-speech.js`, `scripts/bedrock_check.py`. No `npm run build` needed anywhere in this plan.
- `#chat` and `form#chat-form` each already have an explicit CSS `display: flex` rule at id-level specificity (confirmed in the current file). Per this project's own documented bug history ("Important fixes made" #2 in `PROJECT_CONTEXT.md`), a plain `hidden` attribute on either element would be silently overridden by that existing rule. Any code that shows/hides `#chat` or `#chat-form` for the roleplay setup flow **must** use `element.style.display` (inline styles always win), never the `hidden` attribute/property, for those two elements specifically.
- Backend tests follow this project's existing mocked-at-the-function-boundary pattern (see `tests/test_main.py`) and pure-function pattern (see `tests/test_bedrock.py`). No JS test infrastructure exists or is being added — frontend tasks are verified with `node --check` plus a manual QA pass, per established convention.
- Run `pytest -v` and confirm all tests (existing + new) pass before every commit that touches Python files.

---

## Task 1: Persona registry (`app/personas.py`)

**Files:**
- Create: `app/personas.py`
- Test: `tests/test_personas.py`

**Interfaces:**
- Produces: `Persona` (frozen dataclass: `id, name, role_title, base_description, safety_framing`, all `str`) and `PERSONAS: dict[str, Persona]`, keyed by `id`, containing exactly one entry: `"dr_sarah_chen"`. Task 2 imports `Persona` for its type hints; Task 3 imports `PERSONAS` to resolve `persona_id` in the `/chat` route and to build the `/personas` route's response.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_personas.py`:

```python
from app.personas import PERSONAS, Persona


def test_sarah_persona_is_registered():
    assert "dr_sarah_chen" in PERSONAS


def test_sarah_persona_has_expected_fields():
    sarah = PERSONAS["dr_sarah_chen"]

    assert isinstance(sarah, Persona)
    assert sarah.id == "dr_sarah_chen"
    assert sarah.name == "Dr. Sarah Chen"
    assert sarah.role_title == "General Practitioner"
    assert "Sarah Chen" in sarah.base_description
    assert "roleplay" in sarah.safety_framing.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_personas.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.personas'`

- [ ] **Step 3: Write the implementation**

Create `app/personas.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class Persona:
    id: str
    name: str
    role_title: str
    base_description: str
    safety_framing: str


PERSONAS: dict[str, Persona] = {
    "dr_sarah_chen": Persona(
        id="dr_sarah_chen",
        name="Dr. Sarah Chen",
        role_title="General Practitioner",
        base_description=(
            "You are Dr. Sarah Chen, a friendly and experienced general "
            "practitioner taking part in a training roleplay conversation. "
            "Speak warmly and professionally, ask relevant follow-up "
            "questions, and respond the way a real GP would in a "
            "consultation."
        ),
        safety_framing=(
            "This is a roleplay for practice and learning purposes only, "
            "not real medical care: do not provide actual diagnoses or "
            "medical advice, and if the user describes a real medical "
            "emergency, tell them to contact real emergency services "
            "immediately."
        ),
    ),
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_personas.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add app/personas.py tests/test_personas.py
git commit -m "$(cat <<'EOF'
feat: add persona registry

Introduces a Persona dataclass and a PERSONAS registry, starting with
Dr. Sarah Chen (today's only persona) split into base_description and
safety_framing. Structurally Sarah is no different from any future
persona — adding one later is one dict entry, not a mechanism change.
Not yet wired into anything else.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_011enm4huJZrm62Y5i61PM2t
EOF
)"
```

---

## Task 2: Dynamic system prompt (`app/bedrock.py`)

**Files:**
- Modify: `app/bedrock.py`
- Modify: `tests/test_bedrock.py`

**Interfaces:**
- Consumes: `Persona` from `app.personas` (Task 1).
- Produces: `DEFAULT_SYSTEM_PROMPT` (renamed from `SYSTEM_PROMPT`, value unchanged), `DIFFICULTY_INSTRUCTIONS: dict[str, str]`, `build_system_prompt(persona: Persona | None, session: dict | None) -> str`, and updated signatures `build_request_body(messages: list, persona: Persona | None = None, session: dict | None = None) -> dict` / `get_reply(messages: list, persona: Persona | None = None, session: dict | None = None) -> str`. Task 3's `/chat` route calls these with keyword args `persona=` / `session=` (a plain `dict`, not the pydantic model) when a roleplay session is active, and with no extra args at all when it isn't.

- [ ] **Step 1: Write the failing tests**

Replace the full contents of `tests/test_bedrock.py` with:

```python
from app.bedrock import (
    DEFAULT_SYSTEM_PROMPT,
    build_request_body,
    build_system_prompt,
    extract_reply_text,
)
from app.personas import Persona

TEST_PERSONA = Persona(
    id="test_persona",
    name="Dr. Test",
    role_title="Test Role",
    base_description="BASE DESCRIPTION.",
    safety_framing="SAFETY FRAMING.",
)
TEST_SESSION = {
    "scenario": "Test scenario",
    "objective": "Test objective",
    "mood": "Test mood",
    "difficulty": "medium",
}


def test_build_request_body_has_correct_shape():
    messages = [{"role": "user", "content": "Hello there"}]

    body = build_request_body(messages)

    assert body == {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1024,
        "system": DEFAULT_SYSTEM_PROMPT,
        "messages": messages,
    }


def test_extract_reply_text_returns_the_text_field():
    response_body = {
        "content": [{"type": "text", "text": "Hello world today."}]
    }

    assert extract_reply_text(response_body) == "Hello world today."


def test_build_system_prompt_falls_back_to_default_without_persona_or_session():
    assert build_system_prompt(None, None) == DEFAULT_SYSTEM_PROMPT


def test_build_system_prompt_composes_persona_and_session_fields():
    prompt = build_system_prompt(TEST_PERSONA, TEST_SESSION)

    assert "BASE DESCRIPTION." in prompt
    assert "Test scenario" in prompt
    assert "Test objective" in prompt
    assert "Test mood" in prompt
    assert "SAFETY FRAMING." in prompt


def test_build_system_prompt_differs_by_difficulty():
    easy_prompt = build_system_prompt(TEST_PERSONA, {**TEST_SESSION, "difficulty": "easy"})
    hard_prompt = build_system_prompt(TEST_PERSONA, {**TEST_SESSION, "difficulty": "hard"})

    assert easy_prompt != hard_prompt


def test_build_request_body_uses_dynamic_prompt_when_session_provided():
    messages = [{"role": "user", "content": "Hi"}]

    body = build_request_body(messages, persona=TEST_PERSONA, session=TEST_SESSION)

    assert body["system"] != DEFAULT_SYSTEM_PROMPT
    assert "BASE DESCRIPTION." in body["system"]
    assert body["messages"] == messages
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_bedrock.py -v`
Expected: FAIL — `ImportError: cannot import name 'DEFAULT_SYSTEM_PROMPT'` (and `build_system_prompt` doesn't exist yet).

- [ ] **Step 3: Write the implementation**

Replace the full contents of `app/bedrock.py` with:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_bedrock.py tests/test_personas.py -v`
Expected: 8 passed (2 from Task 1 + 6 here)

- [ ] **Step 5: Run the full suite to confirm no regressions elsewhere**

Run: `pytest -v`
Expected: all tests pass, including the untouched `tests/test_bedrock_check.py` and every existing `tests/test_main.py` test (main.py hasn't been touched yet in this plan, so these should be unaffected).

- [ ] **Step 6: Commit**

```bash
git add app/bedrock.py tests/test_bedrock.py
git commit -m "$(cat <<'EOF'
feat: make the Bedrock system prompt persona/session-aware

SYSTEM_PROMPT (renamed DEFAULT_SYSTEM_PROMPT, value unchanged) is now
the fallback used when no persona/session is supplied. New
build_system_prompt(persona, session) composes a dynamic prompt from
a Persona plus scenario/objective/mood/difficulty when both are
given. build_request_body and get_reply gain optional persona/session
parameters; called with neither, their behavior is unchanged.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_011enm4huJZrm62Y5i61PM2t
EOF
)"
```

---

## Task 3: `/chat` session field and `GET /personas` (`app/main.py`)

**Files:**
- Modify: `app/main.py`
- Modify: `tests/test_main.py`

**Interfaces:**
- Consumes: `PERSONAS` from `app.personas` (Task 1); `get_reply`'s new optional `persona`/`session` parameters (Task 2).
- Produces: `GET /personas` → `[{"id", "name", "role_title"}, ...]` (Task 5's frontend consumes this to populate the persona picker). `POST /chat` accepts an optional `session` object shaped `{"persona_id", "scenario", "objective", "mood", "difficulty"}` (Task 5's frontend sends this once a roleplay has started).

- [ ] **Step 1: Write the failing tests**

In `tests/test_main.py`, add this import near the top (alongside the existing `from app.main import app`):

```python
from app.personas import PERSONAS
```

Then add these tests at the end of the file:

```python
@patch("app.main.get_reply")
def test_chat_endpoint_with_roleplay_session_passes_persona_and_session(mock_get_reply):
    mock_get_reply.return_value = "In character reply"
    session_payload = {
        "persona_id": "dr_sarah_chen",
        "scenario": "Pharmaceutical sales call",
        "objective": "Introduce a new treatment and handle objections",
        "mood": "Skeptical, short on time",
        "difficulty": "medium",
    }

    response = client.post(
        "/chat",
        json={
            "messages": [{"role": "user", "content": "Hello doctor"}],
            "session": session_payload,
        },
    )

    assert response.status_code == 200
    assert response.json() == {"reply": "In character reply"}
    mock_get_reply.assert_called_once_with(
        [{"role": "user", "content": "Hello doctor"}],
        persona=PERSONAS["dr_sarah_chen"],
        session=session_payload,
    )


def test_chat_endpoint_rejects_unknown_persona_id():
    response = client.post(
        "/chat",
        json={
            "messages": [{"role": "user", "content": "Hi"}],
            "session": {
                "persona_id": "nonexistent_persona",
                "scenario": "x",
                "objective": "y",
                "mood": "z",
                "difficulty": "medium",
            },
        },
    )

    assert response.status_code == 400


def test_personas_returns_registered_personas():
    response = client.get("/personas")

    assert response.status_code == 200
    assert response.json() == [
        {"id": "dr_sarah_chen", "name": "Dr. Sarah Chen", "role_title": "General Practitioner"}
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_main.py -v`
Expected: FAIL — the two new `/chat` tests fail because `ChatRequest` doesn't accept a `session` field yet (pydantic will 422 on the extra field being silently ignored, so `get_reply` won't be called with the expected args, or the unknown-persona test won't get a 400); `test_personas_returns_registered_personas` fails with 404 (`GET /personas` doesn't exist yet).

- [ ] **Step 3: Write the implementation**

In `app/main.py`, add the import (alongside the existing `from app.bedrock import get_reply`):

```python
from app.personas import PERSONAS
```

Replace:

```python
class ChatRequest(BaseModel):
    messages: list[ChatMessage]
```

with:

```python
class RoleplaySessionRequest(BaseModel):
    persona_id: str
    scenario: str
    objective: str
    mood: str
    difficulty: Literal["easy", "medium", "hard"]


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    session: RoleplaySessionRequest | None = None
```

Replace the `/chat` route:

```python
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

with:

```python
@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    messages = [{"role": m.role, "content": m.content} for m in request.messages]

    persona = None
    session_dict = None
    if request.session is not None:
        persona = PERSONAS.get(request.session.persona_id)
        if persona is None:
            raise HTTPException(status_code=400, detail="Unknown persona_id.")
        session_dict = request.session.model_dump()

    try:
        if persona is not None:
            reply = get_reply(messages, persona=persona, session=session_dict)
        else:
            reply = get_reply(messages)
    except Exception:
        logger.exception("Bedrock call failed")
        raise HTTPException(
            status_code=503,
            detail="The AI service is temporarily unavailable. Please try again.",
        )

    return ChatResponse(reply=reply)
```

Add a new route, placed after `/chat` and before `/avatar/session`:

```python
@app.get("/personas")
def personas():
    return [
        {"id": p.id, "name": p.name, "role_title": p.role_title}
        for p in PERSONAS.values()
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_main.py -v`
Expected: all tests pass, including the three pre-existing `/chat` tests (`test_chat_endpoint_returns_ai_reply`, `test_chat_endpoint_passes_full_history_to_get_reply`, `test_chat_endpoint_returns_503_when_bedrock_fails`) **unmodified** — confirm by checking `git diff tests/test_main.py` shows no changes to those three test bodies, only additions.

- [ ] **Step 5: Run the full suite**

Run: `pytest -v`
Expected: all tests pass — should now be 24 (15 original + 2 new in `tests/test_personas.py` + 4 net-new in `tests/test_bedrock.py` [2 existing kept, 4 added] + 3 net-new in `tests/test_main.py`). Verify the actual count `pytest` prints rather than assuming this number.

- [ ] **Step 6: Commit**

```bash
git add app/main.py tests/test_main.py
git commit -m "$(cat <<'EOF'
feat: add optional roleplay session to /chat and a /personas route

ChatRequest.session is optional — omitted, /chat calls get_reply exactly
as before (verified: the three pre-existing /chat tests pass unmodified).
When present, the route resolves persona_id against the persona registry
(400 on an unknown id) and passes the resolved Persona plus the session
dict through to get_reply. GET /personas lists available personas for
the frontend picker, mirroring GET /voices's existing shape/pattern.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_011enm4huJZrm62Y5i61PM2t
EOF
)"
```

---

## Task 4: Roleplay setup UI — markup and CSS only (`static/index.html`)

**Files:**
- Modify: `static/index.html` (CSS `<style>` block and markup only — no `<script>` changes in this task)

**Interfaces:**
- Consumes: nothing new (pure markup/CSS).
- Produces: a `<form id="roleplay-setup">` with `#persona-select`, `#scenario-input`, `#objective-input`, `#mood-input`, `#difficulty-select`, and a submit button `#start-roleplay-btn`; a `#new-roleplay-btn` (starts `hidden`); `id="active-persona-name"`/`id="active-persona-role"` added to the existing persona-name/role divs. None of these have JS behavior yet — inert until Task 5. `#chat` and `form#chat-form` start with an inline `style="display: none;"` (see Global Constraints on why the `hidden` attribute would not work here).

- [ ] **Step 1: Add the roleplay setup CSS**

Find this existing block (the last rule before `#chat`'s own rule):

```css
  #disclaimer .dot {
    width: 6px;
    height: 6px;
    margin-top: 0.4em;
    border-radius: 50%;
    background: var(--warn);
    flex-shrink: 0;
  }
```

Add immediately after it (before the blank line and `#chat {`):

```css

  #roleplay-setup {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    background: var(--panel);
    border: 1px solid var(--panel-border);
    border-radius: var(--radius-md);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    padding: 1.5rem;
    margin-bottom: 1rem;
  }
  .roleplay-setup-title {
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 600;
    font-size: 1.05rem;
    margin: 0;
  }
  .roleplay-field {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    font-size: 0.78rem;
    color: var(--text-dim);
  }
  .roleplay-field input[type="text"],
  .roleplay-field select {
    appearance: none;
    -webkit-appearance: none;
    background: var(--bg-base-2);
    border: 1px solid var(--panel-border);
    color: var(--text);
    font-family: 'Inter', sans-serif;
    font-size: 0.85rem;
    padding: 0.55rem 0.75rem;
    border-radius: var(--radius-sm);
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
  }
  .roleplay-field input[type="text"]:focus,
  .roleplay-field select:focus {
    outline: none;
    border-color: var(--accent-dim);
    box-shadow: 0 0 0 3px var(--accent-soft);
  }
  .roleplay-field select option {
    background: var(--bg-base-2);
    color: var(--text);
  }
  #start-roleplay-btn {
    align-self: flex-start;
    margin-top: 0.3rem;
    padding: 0.6rem 1.4rem;
    border: none;
    border-radius: 999px;
    background: var(--accent);
    color: #08211d;
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 600;
    font-size: 0.85rem;
    cursor: pointer;
    transition: transform 0.15s ease;
  }
  #start-roleplay-btn:hover { transform: scale(1.03); }
  #start-roleplay-btn:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }

  #new-roleplay-btn {
    margin-top: 0.6rem;
    padding: 0.35rem 0.85rem;
    border: 1px solid var(--panel-border);
    border-radius: 999px;
    background: transparent;
    color: var(--text-dim);
    font-family: 'Inter', sans-serif;
    font-size: 0.75rem;
    cursor: pointer;
    transition: border-color 0.2s ease, color 0.2s ease;
  }
  #new-roleplay-btn:hover {
    border-color: var(--accent-dim);
    color: var(--text);
  }
  #new-roleplay-btn:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }
```

- [ ] **Step 2: Add `id`s to the existing persona-name/role divs and the "New Roleplay" button**

Find:

```html
      <div class="persona-name">Dr. Sarah Chen</div>
      <div class="persona-role">General Practitioner</div>
      <label class="voice-label">Voice
```

Replace with:

```html
      <div class="persona-name" id="active-persona-name">Dr. Sarah Chen</div>
      <div class="persona-role" id="active-persona-role">General Practitioner</div>
      <button type="button" id="new-roleplay-btn" hidden>New Roleplay</button>
      <label class="voice-label">Voice
```

(`#new-roleplay-btn` has no explicit CSS `display` rule of its own — see Step 1's CSS — so the plain `hidden` attribute/property works correctly for it; this is different from `#chat`/`form#chat-form` below, which do have a conflicting rule.)

- [ ] **Step 3: Add the roleplay setup form, and hide the chat log/composer by default**

Find:

```html
    <div id="chat-panel">
      <div id="disclaimer">
        <span class="dot"></span>
        This is an AI roleplay for practice only — not real medical advice. In a real emergency, contact emergency services immediately.
      </div>
      <div id="chat"></div>
      <form id="chat-form">
```

Replace with:

```html
    <div id="chat-panel">
      <div id="disclaimer">
        <span class="dot"></span>
        This is an AI roleplay for practice only — not real medical advice. In a real emergency, contact emergency services immediately.
      </div>
      <form id="roleplay-setup">
        <h2 class="roleplay-setup-title">Start a Roleplay</h2>
        <label class="roleplay-field">HCP Persona
          <span class="select-wrap"><select id="persona-select"></select></span>
        </label>
        <label class="roleplay-field">Scenario
          <input id="scenario-input" type="text" placeholder="e.g. Pharmaceutical sales call" required>
        </label>
        <label class="roleplay-field">Conversation Objective
          <input id="objective-input" type="text" placeholder="e.g. Introduce a new treatment and handle objections" required>
        </label>
        <label class="roleplay-field">Persona Mood / Behavior
          <input id="mood-input" type="text" placeholder="e.g. Skeptical, short on time" required>
        </label>
        <label class="roleplay-field">Difficulty
          <span class="select-wrap">
            <select id="difficulty-select">
              <option value="easy">Easy</option>
              <option value="medium" selected>Medium</option>
              <option value="hard">Hard</option>
            </select>
          </span>
        </label>
        <button type="submit" id="start-roleplay-btn">Start Roleplay</button>
      </form>
      <div id="chat" style="display: none;"></div>
      <form id="chat-form" style="display: none;">
```

- [ ] **Step 4: Verify the `<script>` blocks are untouched**

```bash
git diff static/index.html
```

Expected: every changed line is inside the `<style>` block or the markup shown above — nothing inside either `<script>` block changed.

- [ ] **Step 5: Confirm the page serves the new markup**

```bash
source venv/bin/activate
uvicorn app.main:app &
sleep 1
curl -s http://127.0.0.1:8000/ | grep -c 'id="roleplay-setup"'
curl -s http://127.0.0.1:8000/ | grep -c 'id="persona-select"'
kill %1
```

Expected: `1` for each.

- [ ] **Step 6: Commit**

```bash
git add static/index.html
git commit -m "$(cat <<'EOF'
feat: add roleplay setup form markup and styling

CSS and markup only, additive and inert — no JS wired yet. #chat and
form#chat-form get an inline style="display: none;" rather than a
hidden attribute, because both already have an explicit CSS
display:flex rule at id-level specificity that would silently
override a plain hidden attribute (the same class of bug already
documented and fixed once in this project for the avatar video/poster
toggle).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_011enm4huJZrm62Y5i61PM2t
EOF
)"
```

---

## Task 5: Wire the roleplay setup flow (`static/index.html`)

**Files:**
- Modify: `static/index.html` (inline `<script>` block only)

**Interfaces:**
- Consumes: `GET /personas` and `POST /chat`'s optional `session` field (Task 3); the markup/ids from Task 4; the existing `sendToSarah(message)`, `conversation`, `chat`, `form` from earlier in the script.
- Produces: a page-level `roleplaySession` variable (`null` until a roleplay starts) that `sendToSarah` includes in its `/chat` request body — this is the one integration point where Text Chat and Live Voice both pick up roleplay context "for free," since both already call `sendToSarah`.

- [ ] **Step 1: Add new DOM references**

Find:

```js
    const avatarPanel = document.getElementById('avatar-panel');
    const avatarStateBadge = document.getElementById('avatar-state-badge');
    let isSending = false;
    let conversation = [];
    let voices = [];
```

Replace with:

```js
    const avatarPanel = document.getElementById('avatar-panel');
    const avatarStateBadge = document.getElementById('avatar-state-badge');
    const roleplaySetupForm = document.getElementById('roleplay-setup');
    const personaSelect = document.getElementById('persona-select');
    const scenarioInput = document.getElementById('scenario-input');
    const objectiveInput = document.getElementById('objective-input');
    const moodInput = document.getElementById('mood-input');
    const difficultySelect = document.getElementById('difficulty-select');
    const newRoleplayBtn = document.getElementById('new-roleplay-btn');
    const activePersonaName = document.getElementById('active-persona-name');
    const activePersonaRole = document.getElementById('active-persona-role');
    let isSending = false;
    let conversation = [];
    let voices = [];
    let personas = [];
    let roleplaySession = null;
```

- [ ] **Step 2: Add persona loading and the setup/new-roleplay handlers**

Find:

```js
    voiceSelect.addEventListener('change', () => {
      localStorage.setItem('voiceId', voiceSelect.value);
    });

    populateVoices();
```

Replace with:

```js
    voiceSelect.addEventListener('change', () => {
      localStorage.setItem('voiceId', voiceSelect.value);
    });

    populateVoices();

    async function populatePersonas() {
      try {
        const response = await fetch('/personas');
        if (!response.ok) throw new Error('Failed to load personas');
        personas = await response.json();
      } catch (error) {
        console.error('Failed to load personas', error);
        personas = [];
      }

      personaSelect.replaceChildren();
      personas.forEach((persona) => {
        const option = document.createElement('option');
        option.value = persona.id;
        option.textContent = persona.name + ' — ' + persona.role_title;
        personaSelect.appendChild(option);
      });
    }

    populatePersonas();

    roleplaySetupForm.addEventListener('submit', (event) => {
      event.preventDefault();

      const selectedPersona = personas.find((p) => p.id === personaSelect.value);
      if (!selectedPersona) return;

      roleplaySession = {
        persona_id: selectedPersona.id,
        scenario: scenarioInput.value.trim(),
        objective: objectiveInput.value.trim(),
        mood: moodInput.value.trim(),
        difficulty: difficultySelect.value,
      };

      activePersonaName.textContent = selectedPersona.name;
      activePersonaRole.textContent = selectedPersona.role_title;

      roleplaySetupForm.style.display = 'none';
      chat.style.display = 'flex';
      form.style.display = 'flex';
      newRoleplayBtn.hidden = false;
    });

    newRoleplayBtn.addEventListener('click', () => {
      roleplaySession = null;
      conversation = [];
      chat.replaceChildren();

      roleplaySetupForm.style.display = 'flex';
      chat.style.display = 'none';
      form.style.display = 'none';
      newRoleplayBtn.hidden = true;
    });
```

- [ ] **Step 3: Include the roleplay session in `sendToSarah`'s request**

Find (inside `sendToSarah`):

```js
        const response = await fetch('/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ messages: conversation }),
        });
```

Replace with:

```js
        const chatRequestBody = { messages: conversation };
        if (roleplaySession) {
          chatRequestBody.session = roleplaySession;
        }

        const response = await fetch('/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(chatRequestBody),
        });
```

- [ ] **Step 4: Syntax-check the inline script**

```bash
awk '/^  <script>$/{flag=1; next} /^  <\/script>$/{flag=0} flag' static/index.html > /tmp/roleplay-inline-check.js
node --check /tmp/roleplay-inline-check.js
rm /tmp/roleplay-inline-check.js
```

Expected: no output, exit 0.

- [ ] **Step 5: Confirm the server still serves correctly**

```bash
source venv/bin/activate
uvicorn app.main:app &
sleep 1
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/
curl -s http://127.0.0.1:8000/personas | grep -c 'dr_sarah_chen'
kill %1
```

Expected: `200`, then `1`.

- [ ] **Step 6: Commit**

```bash
git add static/index.html
git commit -m "$(cat <<'EOF'
feat: wire the roleplay setup flow into the shared chat pipeline

Populates the persona picker from GET /personas. Submitting "Start
Roleplay" stores the config in a page-level roleplaySession variable,
updates the avatar panel's persona name/role, and reveals the
existing chat log/composer. sendToSarah — the single pipeline both
Text Chat and Live Voice already call — includes roleplaySession in
its /chat request body when one is active, so both modes pick up
roleplay context without any mode-specific wiring. "New Roleplay"
resets both the session and the conversation array together.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_011enm4huJZrm62Y5i61PM2t
EOF
)"
```

---

## Task 6: Regression check, manual QA handoff, and PROJECT_CONTEXT.md update

**Files:**
- Modify: `PROJECT_CONTEXT.md`

**Interfaces:**
- Consumes: nothing new — this task verifies and documents Tasks 1-5.

- [ ] **Step 1: Run the full backend test suite**

```bash
source venv/bin/activate
pytest -v
```

Expected: every test passes — the 15 pre-existing tests (untouched in behavior), plus Task 1-3's new tests. If anything fails, stop and investigate before continuing.

- [ ] **Step 2: Hand off the manual browser verification script**

This cannot be executed in this environment — no real browser is available here (per `CLAUDE.md`). Present this exact checklist to the user to run in Chrome:

1. Run `uvicorn app.main:app --reload`, open `http://127.0.0.1:8000/`.
2. Confirm the "Start a Roleplay" form appears above the chat area, and the chat log/composer are not visible yet.
3. Confirm the persona dropdown shows "Dr. Sarah Chen — General Practitioner".
4. Try clicking "Start Roleplay" with Scenario/Objective/Mood left empty — confirm the browser's native validation blocks submission (required-field prompts).
5. Fill in Scenario "Pharmaceutical sales call", Objective "Introduce a new treatment and handle the physician's objections", Mood "Skeptical, short on time", Difficulty "Medium" (matching the milestone's example), and click "Start Roleplay". Confirm: the setup form disappears, the chat log and composer appear, the avatar panel's persona name/role still read "Dr. Sarah Chen" / "General Practitioner", and a "New Roleplay" button is now visible.
6. Send a text message (e.g., "Hi Dr. Chen, do you have a few minutes?") and confirm Sarah's reply reads as in-character for the configured scenario/objective/mood/difficulty (skeptical, time-pressured), not generically friendly the way the old fixed prompt was.
7. Switch to Live Voice mode (mic button) and confirm a spoken turn also reflects the same roleplay persona/scenario — i.e., that voice and text are clearly having the *same* conversation with the *same* configured character.
8. Click "New Roleplay". Confirm the chat log clears, the composer/mic hide, and the setup form reappears.
9. Start a second roleplay with different Scenario/Objective/Mood/Difficulty values and confirm the new values are reflected in Sarah's behavior (different framing from step 6).
10. Confirm nothing about Live Voice's mic permission flow, turn-taking loop, or audio playback regressed — repeat a couple of turns of the Live Voice QA from the previous milestone if anything seems off.

Report back which of these pass/fail; this feature isn't "done" until step 6/7 (in-character behavior actually changes with the configured roleplay) is confirmed by the user in their own browser.

- [ ] **Step 3: Update `PROJECT_CONTEXT.md`**

Insert a new `## Roleplay Sessions` section after the existing `## Live Voice Conversation integration` section (adjust placement only if the file's structure has shifted). Use this text as the actual content:

```markdown
## Roleplay Sessions

A user can configure a structured roleplay before chatting: HCP persona,
scenario, conversation objective, persona mood/behavior, and difficulty
(easy/medium/hard). Once started, this becomes dynamic system-prompt
context for the *same* Bedrock conversation Text Chat and Live Voice
already share — no new conversation pipeline, no backend persistence.

**Persona registry** (`app/personas.py`, `PERSONAS: dict[str, Persona]`):
a `Persona` is `{id, name, role_title, base_description, safety_framing}`.
Dr. Sarah Chen is the only entry today, structurally no different from any
future persona — adding one is one dict entry. `safety_framing` lives on
the persona (not globally) so a future non-medical HCP persona can carry
different disclaimer language.

**Dynamic system prompt** (`app/bedrock.py`): `build_system_prompt(persona,
session)` composes persona + scenario + objective + mood + a
difficulty-specific instruction (from `DIFFICULTY_INSTRUCTIONS`) into the
prompt Bedrock receives. Called with `persona=None, session=None`, it
returns `DEFAULT_SYSTEM_PROMPT` — today's original hardcoded prompt,
unchanged — which is what keeps `/chat` backward compatible: a request
that omits `session` behaves exactly as it did before this feature
existed.

**Session model**: held client-side only, exactly like the existing
`conversation` array — no session ID, no server-side store, per this
project's stateless-backend decision. `POST /chat`'s `session` field is
optional; the frontend sends it once a roleplay has been started via the
new setup form. `GET /personas` lists available personas for that form's
picker, mirroring `GET /voices`'s existing shape/pattern.

**Shared across Text Chat and Live Voice**: both already call the one
`sendToSarah(message)` pipeline (see "Live Voice Conversation
integration" above); that function includes the active `roleplaySession`
in every `/chat` call, so neither mode needed its own roleplay wiring.
Starting a new roleplay (the "New Roleplay" button) resets both the
session and the conversation array together — a persona swap mid-
transcript wouldn't be a coherent conversation.

**Extensibility, deliberately not built yet**: scoring, compliance
detection, document/RAG grounding, and Admin persona management are all
out of scope for this milestone. Because `objective`/`difficulty`/
`scenario` are structured fields (not buried in prompt text), and personas
are already a separate typed registry from sessions, each of those can
attach later — a new endpoint or a new parameter to `build_system_prompt`
— without reworking how sessions flow through the app. See
`docs/superpowers/specs/2026-09-17-roleplay-sessions-design.md` for the
full rationale.
```

Also add `app/personas.py` to the file tree under "Architecture and key files", and add one line to "Features currently working (verified)" noting Roleplay Sessions once Step 2's manual QA is confirmed (mirror how Live Voice Conversation was added there in the previous milestone) — only after the user confirms, not before, matching this project's standing rule not to claim UI/behavior "works" without that confirmation.

- [ ] **Step 4: Commit**

```bash
git add PROJECT_CONTEXT.md
git commit -m "$(cat <<'EOF'
docs: document Roleplay Sessions in PROJECT_CONTEXT.md

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_011enm4huJZrm62Y5i61PM2t
EOF
)"
```
