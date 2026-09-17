# Persona Library Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the single-entry `app/personas.py` dict into a function-based Persona Library registry (`app/personas/`) with `category`, `voice_id`, and `face_id` fields, wire persona-specific voice selection into the Roleplay setup flow, and add `face_id` pass-through to the Simli avatar session endpoint — all without changing any behavior when no Roleplay Session is active.

**Architecture:** Replace `app/personas.py` with a small package (`models.py` for the `Persona` dataclass, `registry.py` for two functions — `get_persona`/`list_personas` — backed by the same in-memory dict pattern as today). Every existing caller is updated to use these two functions instead of reaching into a raw dict. `POST /avatar/session` gains an optional `face_id` field that defaults to today's hardcoded Simli face when omitted. The Roleplay setup form's submit handler gains one new line that defaults the voice `<select>` to the chosen persona's `voice_id`, still overridable by the user.

**Tech Stack:** Python 3, FastAPI, pytest (mocked at the function boundary, network-free), plain JS in `static/index.html` (no build step involved — `avatar-src/doctor-avatar.js` is not touched).

**Spec:** `docs/superpowers/specs/2026-09-17-persona-library-design.md`

## Global Constraints

- Dr. Sarah Chen must continue to work exactly as she does today, in every mode (Text Chat, Live Voice, inside or outside a Roleplay Session).
- A `/chat` request with no `session` field must never touch the persona registry and must keep returning `DEFAULT_SYSTEM_PROMPT`-based replies, byte-identical to today.
- A `POST /avatar/session` request with no `face_id` must produce the exact same outbound Simli request (`FACE_ID` constant) as today.
- `app/bedrock.py`, `app/tts.py`, `avatar-src/doctor-avatar.js`, `static/dist/avatar-bundle.js`, `static/stt-web-speech.js`, and `scripts/bedrock_check.py` must not be modified at all.
- No database, no Admin routes, no `default_mood`/`tags` fields, no Simli reconnect-on-persona-change logic, no UI redesign — all explicitly out of scope per the approved spec.
- Every existing test in `tests/test_main.py`, `tests/test_bedrock.py`, `tests/test_bedrock_check.py` must keep passing; `tests/test_personas.py` is extended, not weakened.
- Run `pytest -v` after every task; all tests must pass before moving to the next task.
- No `npm run build` is required anywhere in this plan (nothing under `avatar-src/` changes) — each task should explicitly confirm this rather than assume it.

---

## Task 1: Persona registry package (`app/personas/`) wired into `/chat` and `/personas`

**Files:**
- Create: `app/personas/__init__.py`
- Create: `app/personas/models.py`
- Create: `app/personas/registry.py`
- Delete: `app/personas.py`
- Modify: `app/main.py:15` (import), `app/main.py:70` (`/chat` persona lookup), `app/main.py:90-95` (`/personas` route)
- Modify: `tests/test_personas.py` (full rewrite)
- Modify: `tests/test_main.py:6` (import), `tests/test_main.py:126-151` (roleplay-session test), `tests/test_main.py:172-178` (`/personas` test)
- Modify: `tests/test_bedrock.py:9-15` (`TEST_PERSONA` fixture)

**Interfaces:**
- Consumes: nothing from earlier tasks (this is the first task).
- Produces:
  - `app.personas.Persona` — frozen dataclass: `id: str, name: str, role_title: str, category: str, base_description: str, safety_framing: str, voice_id: str, face_id: str`
  - `app.personas.get_persona(persona_id: str) -> Persona | None`
  - `app.personas.list_personas() -> list[Persona]`
  - `GET /personas` now returns `[{"id", "name", "role_title", "category", "voice_id", "face_id"}, ...]`

- [ ] **Step 1: Write the failing test for the new registry**

Replace the full contents of `tests/test_personas.py`:

```python
from app.personas import Persona, get_persona, list_personas


def test_sarah_persona_is_registered():
    assert get_persona("dr_sarah_chen") is not None


def test_sarah_persona_has_expected_fields():
    sarah = get_persona("dr_sarah_chen")

    assert isinstance(sarah, Persona)
    assert sarah.id == "dr_sarah_chen"
    assert sarah.name == "Dr. Sarah Chen"
    assert sarah.role_title == "General Practitioner"
    assert sarah.category == "doctor"
    assert "Sarah Chen" in sarah.base_description
    assert "roleplay" in sarah.safety_framing.lower()
    assert sarah.voice_id == "EXAVITQu4vr4xnSDxMaL"
    assert sarah.face_id == "f0ba4efe-7946-45de-9955-c04a04c367b9"


def test_get_persona_returns_none_for_unknown_id():
    assert get_persona("nonexistent_persona") is None


def test_list_personas_includes_sarah():
    personas = list_personas()

    assert any(p.id == "dr_sarah_chen" for p in personas)
    assert all(isinstance(p, Persona) for p in personas)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `source venv/bin/activate && pytest tests/test_personas.py -v`
Expected: FAIL — `ImportError: cannot import name 'get_persona' from 'app.personas'` (today `app/personas.py` only exposes `Persona` and `PERSONAS`).

- [ ] **Step 3: Delete the old single-file registry**

Run: `git rm app/personas.py`

- [ ] **Step 4: Create the models module**

Create `app/personas/models.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class Persona:
    id: str
    name: str
    role_title: str
    category: str
    base_description: str
    safety_framing: str
    voice_id: str
    face_id: str
```

- [ ] **Step 5: Create the registry module**

Create `app/personas/registry.py`:

```python
from app.personas.models import Persona

_PERSONAS: dict[str, Persona] = {
    "dr_sarah_chen": Persona(
        id="dr_sarah_chen",
        name="Dr. Sarah Chen",
        role_title="General Practitioner",
        category="doctor",
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
        voice_id="EXAVITQu4vr4xnSDxMaL",
        face_id="f0ba4efe-7946-45de-9955-c04a04c367b9",
    ),
}


def get_persona(persona_id: str) -> Persona | None:
    return _PERSONAS.get(persona_id)


def list_personas() -> list[Persona]:
    return list(_PERSONAS.values())
```

Note: `base_description`, `safety_framing`, `voice_id` (`tts.DEFAULT_VOICE_ID`'s current value), and `face_id` (`avatar_simli.FACE_ID`'s current value) are copied verbatim from today's `app/personas.py`, `app/tts.py`, and `app/avatar_simli.py` — no wording or value changes.

- [ ] **Step 6: Create the package `__init__.py`**

Create `app/personas/__init__.py`:

```python
from app.personas.models import Persona
from app.personas.registry import get_persona, list_personas

__all__ = ["Persona", "get_persona", "list_personas"]
```

This re-export is what keeps `app/bedrock.py`'s existing `from app.personas import Persona` working unmodified — `app/bedrock.py` is not touched by this plan at all.

- [ ] **Step 7: Run the registry test to verify it passes**

Run: `source venv/bin/activate && pytest tests/test_personas.py -v`
Expected: PASS (4 tests).

- [ ] **Step 8: Update `app/main.py` to use the new registry functions**

In `app/main.py`, change the import (currently line 15):

```python
from app.personas import get_persona, list_personas
```

In the `/chat` route, change:

```python
        persona = PERSONAS.get(request.session.persona_id)
```

to:

```python
        persona = get_persona(request.session.persona_id)
```

Replace the `/personas` route body with:

```python
@app.get("/personas")
def personas():
    return [
        {
            "id": p.id,
            "name": p.name,
            "role_title": p.role_title,
            "category": p.category,
            "voice_id": p.voice_id,
            "face_id": p.face_id,
        }
        for p in list_personas()
    ]
```

- [ ] **Step 9: Update `tests/test_main.py` for the new import and response shape**

Change the import (currently line 6):

```python
from app.personas import get_persona
```

Change the roleplay-session test's assertion (currently referencing `PERSONAS["dr_sarah_chen"]` around line 149):

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
        persona=get_persona("dr_sarah_chen"),
        session=session_payload,
    )
```

Replace the `/personas` test:

```python
def test_personas_returns_registered_personas():
    response = client.get("/personas")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": "dr_sarah_chen",
            "name": "Dr. Sarah Chen",
            "role_title": "General Practitioner",
            "category": "doctor",
            "voice_id": "EXAVITQu4vr4xnSDxMaL",
            "face_id": "f0ba4efe-7946-45de-9955-c04a04c367b9",
        }
    ]
```

- [ ] **Step 10: Update `tests/test_bedrock.py`'s `TEST_PERSONA` fixture**

`Persona` now requires `category`, `voice_id`, and `face_id`. Update the fixture (currently lines 9-15):

```python
TEST_PERSONA = Persona(
    id="test_persona",
    name="Dr. Test",
    role_title="Test Role",
    category="doctor",
    base_description="BASE DESCRIPTION.",
    safety_framing="SAFETY FRAMING.",
    voice_id="test-voice-id",
    face_id="test-face-id",
)
```

No other change to `tests/test_bedrock.py` — every function it tests (`build_request_body`, `build_system_prompt`, `extract_reply_text`) is untouched by this plan, and none of them read `category`/`voice_id`/`face_id`, so no assertion elsewhere in that file changes.

- [ ] **Step 11: Run the full test suite**

Run: `source venv/bin/activate && pytest -v`
Expected: all tests PASS, including every test in `test_main.py`, `test_bedrock.py`, `test_bedrock_check.py`, and the 4 tests in `test_personas.py`. This is the backward-compatibility check for this task: `test_chat_endpoint_returns_ai_reply`, `test_chat_endpoint_passes_full_history_to_get_reply`, and `test_chat_endpoint_returns_503_when_bedrock_fails` (all exercising `/chat` with no `session`) must pass unmodified, proving the no-session path is untouched.

- [ ] **Step 12: Commit**

```bash
git add app/personas/ app/main.py tests/test_personas.py tests/test_main.py tests/test_bedrock.py
git commit -m "$(cat <<'EOF'
refactor: replace personas.py dict with a function-based registry package

Persona gains category/voice_id/face_id fields. app/main.py now calls
get_persona()/list_personas() instead of reaching into a raw dict —
the seam a future database-backed registry swaps behind without
touching any caller. No behavior change for requests without a
roleplay session.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: `face_id` pass-through on `POST /avatar/session`

**Files:**
- Modify: `app/avatar_provider.py` (Protocol signature)
- Modify: `app/avatar_simli.py` (`create_session` signature and body)
- Modify: `app/main.py` (new request model, `/avatar/session` route)
- Modify: `tests/test_main.py` (avatar-session tests)

**Interfaces:**
- Consumes: nothing from Task 1 directly (this task is independent of the registry change — no persona is looked up here yet, per the spec's decision to defer sending a persona-specific `face_id` from the frontend to a future milestone).
- Produces:
  - `AvatarProvider.create_session(self, face_id: str | None = None) -> dict`
  - `SimliAvatarProvider.create_session(self, face_id: str | None = None) -> dict` — posts `face_id or FACE_ID` as `"faceId"`.
  - `POST /avatar/session` accepts an optional JSON body `{"face_id": str | None}`; omitting the body or `face_id` behaves exactly as today.

- [ ] **Step 1: Write the failing tests**

In `tests/test_main.py`, update the existing `test_avatar_session_returns_provider_result` to also assert the call arguments, and add a new test for explicit `face_id`:

```python
@patch("app.main.avatar_provider.create_session")
def test_avatar_session_returns_provider_result(mock_create_session):
    mock_create_session.return_value = {"session_token": "mocked-token"}

    response = client.post("/avatar/session")

    assert response.status_code == 200
    assert response.json() == {"session_token": "mocked-token"}
    mock_create_session.assert_called_once_with(None)


@patch("app.main.avatar_provider.create_session")
def test_avatar_session_passes_face_id_when_provided(mock_create_session):
    mock_create_session.return_value = {"session_token": "mocked-token"}

    response = client.post("/avatar/session", json={"face_id": "custom-face-id"})

    assert response.status_code == 200
    mock_create_session.assert_called_once_with("custom-face-id")
```

(`test_avatar_session_returns_503_on_failure` is unchanged — leave it exactly as-is.)

- [ ] **Step 2: Run the tests to verify they fail**

Run: `source venv/bin/activate && pytest tests/test_main.py -k avatar_session -v`
Expected: FAIL — `mock_create_session.assert_called_once_with(None)` fails because the current route calls `avatar_provider.create_session()` with no arguments, and the `face_id`-passing test fails the same way (the current route ignores any request body).

- [ ] **Step 3: Update the `AvatarProvider` protocol**

In `app/avatar_provider.py`, change:

```python
from typing import Protocol


class AvatarProvider(Protocol):
    def create_session(self, face_id: str | None = None) -> dict:
        """Create a new avatar session and return connection info for the frontend."""
        ...
```

- [ ] **Step 4: Update `SimliAvatarProvider.create_session`**

In `app/avatar_simli.py`, change the method signature and body:

```python
    def create_session(self, face_id: str | None = None) -> dict:
        response = httpx.post(
            TOKEN_URL,
            json={
                "faceId": face_id or FACE_ID,
                "handleSilence": True,
                "maxSessionLength": 600,
                "maxIdleTime": 180,
            },
            headers={
                "Content-Type": "application/json",
                "x-simli-api-key": self.api_key,
            },
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
```

Every other field (`handleSilence`, `maxSessionLength`, `maxIdleTime`, headers, timeout, `FACE_ID` constant itself) is unchanged.

- [ ] **Step 5: Update `app/main.py`'s `/avatar/session` route**

Add a request model near the other request models (alongside `TTSRequest`):

```python
class AvatarSessionRequest(BaseModel):
    face_id: str | None = None
```

Change the route:

```python
@app.post("/avatar/session")
def avatar_session(request: AvatarSessionRequest | None = None):
    face_id = request.face_id if request else None
    try:
        return avatar_provider.create_session(face_id)
    except Exception:
        logger.exception("Avatar session creation failed")
        raise HTTPException(
            status_code=503,
            detail="The avatar service is temporarily unavailable. Please try again.",
        )
```

- [ ] **Step 6: Run the avatar-session tests to verify they pass**

Run: `source venv/bin/activate && pytest tests/test_main.py -k avatar_session -v`
Expected: PASS (3 tests: default, explicit `face_id`, 503-on-failure).

- [ ] **Step 7: Run the full test suite**

Run: `source venv/bin/activate && pytest -v`
Expected: all tests PASS. This confirms `client.post("/avatar/session")` with no body — exactly what the frontend's page-load `avatar.connect()` call sends today — still returns 200 and now provably calls the provider with `None`, reproducing today's exact outbound Simli request.

- [ ] **Step 8: Confirm no frontend build is needed**

Run: `git status avatar-src/ static/dist/`
Expected: no changes — this task touches only `app/` files, so `avatar-src/doctor-avatar.js` and the committed `static/dist/avatar-bundle.js` are untouched and `npm run build` is not required.

- [ ] **Step 9: Commit**

```bash
git add app/avatar_provider.py app/avatar_simli.py app/main.py tests/test_main.py
git commit -m "$(cat <<'EOF'
feat: add optional face_id pass-through to POST /avatar/session

Simli's face is now settable per-request at the API layer, defaulting
to today's constant when omitted. No caller sends a non-default
face_id yet, and the avatar connection lifecycle (when connect()
fires, session duration) is unchanged — per-persona face switching
is deliberately deferred to a future milestone once multiple real
Simli faces are provisioned.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Persona-default voice selection in the Roleplay setup form

**Files:**
- Modify: `static/index.html` (inline `<script>` block only — the `roleplay-setup` submit handler)

**Interfaces:**
- Consumes: `GET /personas`'s new `voice_id` field (Task 1), the existing `voices` array (populated by the existing `populateVoices()`), the existing `voiceSelect` element and `localStorage` key `'voiceId'` (both already used by the existing voice-selection code), the existing `roleplaySetupForm` submit handler and `selectedPersona` lookup.
- Produces: no new exported interface — this is the final consumer of `voice_id` in this milestone's data flow.

- [ ] **Step 1: Locate the exact insertion point**

Run: `grep -n "roleplaySession = {" static/index.html`
Expected: one match, inside the `roleplaySetupForm.addEventListener('submit', ...)` handler, immediately after the `scenario`/`objective`/`mood` validation and before the `activePersonaName.textContent = ...` line.

- [ ] **Step 2: Add the persona-voice default**

Insert immediately after the `roleplaySession = { ... };` assignment and before `activePersonaName.textContent = selectedPersona.name;`:

```javascript
      if (selectedPersona.voice_id && voices.some((v) => v.voice_id === selectedPersona.voice_id)) {
        voiceSelect.value = selectedPersona.voice_id;
        localStorage.setItem('voiceId', selectedPersona.voice_id);
      }

```

This does not touch `voiceSelect`'s existing `change` listener, `populateVoices()`, or any `/tts` call — all of them already just read `voiceSelect.value`, so a user picking a different voice after this default is set is respected exactly as it is today for a manual selection.

- [ ] **Step 3: Diff the change to prove nothing else in the script blocks moved**

Run: `git diff static/index.html`
Expected: exactly one hunk, adding the 4 lines above (plus a blank line) inside the `roleplaySetupForm` submit handler. No other line in either `<script>` block should appear in the diff — if it does, stop and investigate before continuing.

- [ ] **Step 4: Confirm no frontend build is needed**

Run: `git status avatar-src/ static/dist/`
Expected: no changes — this task only touches inline script in `static/index.html`, not `avatar-src/doctor-avatar.js`, so `npm run build` is not required.

- [ ] **Step 5: Note manual verification (no automated JS test exists)**

This project has no JS test infrastructure by deliberate long-standing convention (`PROJECT_CONTEXT.md`, "Tests and how to run them"). The behavior added here — starting a roleplay sets the voice dropdown to the persona's default voice, still changeable afterward — is covered in the final manual browser QA checklist (Task 5). No action here beyond noting it; do not add a JS test framework to work around this.

- [ ] **Step 6: Commit**

```bash
git add static/index.html
git commit -m "$(cat <<'EOF'
feat: default the voice selector to the persona's voice on roleplay start

Starting a roleplay now sets #voice-select to the chosen persona's
voice_id (when present among the fetched ElevenLabs voices) and
persists it like a manual selection would. The user can still pick a
different voice afterward — no change to how the dropdown or /tts
calls work.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Update `PROJECT_CONTEXT.md`

**Files:**
- Modify: `PROJECT_CONTEXT.md`

**Interfaces:**
- Consumes: the final state of Tasks 1-3 (this task documents what was actually built, so it must run after the code changes, not before).
- Produces: no code interface — documentation only, required by this project's own `CLAUDE.md` rule ("Update `PROJECT_CONTEXT.md` whenever a change alters architecture...").

- [ ] **Step 1: Update the architecture file tree**

In the `## Architecture and key files` code block, change:

```
  personas.py         Persona registry (HCP identity + safety framing)
```

to:

```
  personas/           Persona Library: models.py (Persona dataclass) +
                       registry.py (get_persona()/list_personas(), the
                       only functions any caller uses — never a raw dict)
```

- [ ] **Step 2: Update the "Roleplay Sessions" section's persona registry description**

Replace the paragraph starting "**Persona registry** (`app/personas.py`, `PERSONAS: dict[str, Persona]`)..." with:

```
**Persona registry** (`app/personas/`, a Persona Library — `models.py`'s
`Persona` dataclass + `registry.py`'s `get_persona(id)`/`list_personas()`):
a `Persona` is `{id, name, role_title, category, base_description,
safety_framing, voice_id, face_id}`. Every caller (`app/main.py`) goes
through `get_persona`/`list_personas` — never a raw dict — so moving the
registry to a database later only means rewriting the inside of
`registry.py`; no caller changes. `voice_id` is used to default the
Roleplay setup form's voice selector (still user-overridable); `face_id`
is modeled and accepted by `POST /avatar/session` at the API level, but
every persona currently points at the same verified Simli face — see
"Known issues / open items" for why. Dr. Sarah Chen is still the only
entry today, structurally no different from any future persona.
```

- [ ] **Step 3: Update the Simli integration section**

In `## Simli live avatar integration`, after the sentence describing `SimliAvatarProvider.create_session()`, add:

```
`create_session(face_id: str | None = None)` accepts an optional
per-request face override, defaulting to `FACE_ID` when omitted.
`POST /avatar/session` exposes this as an optional `face_id` field on its
request body. No caller sends a non-default value yet — the frontend's
`avatar.connect()` still fires once at page load, before any persona is
selected, exactly as before this field existed.
```

- [ ] **Step 4: Add a new "Known issues / open items" bullet**

In `## Known issues / open items`, add:

```
- Persona-specific Simli faces are modeled (`Persona.face_id`,
  `POST /avatar/session`'s optional `face_id`) but not yet wired end to
  end: every persona currently shares one verified Simli face, and
  `avatar.connect()` still fires once at page load before any persona is
  chosen. Switching faces per persona requires either delaying that call
  or adding reconnect-on-persona-change logic to `doctor-avatar.js` —
  neither exists yet, deliberately deferred until multiple real Simli
  face IDs are provisioned.
```

- [ ] **Step 5: Update "Next planned feature"**

Replace the `## Next planned feature` section's content with:

```
None currently planned. Persona Library (a function-based persona
registry with `category`/`voice_id`/`face_id`, persona-default voice
selection in the Roleplay setup form, and `face_id` modeled through
`POST /avatar/session`) was the previously-planned next feature — see
"Roleplay Sessions" above for the registry and
`docs/superpowers/specs/2026-09-17-persona-library-design.md` for the
full design rationale — and is now built and verified (pytest for the
backend; the voice-default behavior via manual browser QA). Nothing is
queued up after it. A follow-up milestone is expected once multiple real
Simli face IDs are provisioned, to wire per-persona face switching and
safe Simli reconnection.
```

- [ ] **Step 6: Update the Tests section's test count**

In `## Tests and how to run them`, update the sentence "24 tests, all passing..." to the new total after Tasks 1-2's additions (4 tests added/changed net in `test_personas.py`: 2 existing + 2 new; 2 new in `test_main.py`'s avatar-session coverage) — run `pytest --collect-only -q | tail -1` to get the exact new count and use that number rather than guessing.

- [ ] **Step 7: Commit**

```bash
git add PROJECT_CONTEXT.md
git commit -m "$(cat <<'EOF'
docs: document the Persona Library in PROJECT_CONTEXT.md

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Final automated test pass and manual browser QA

**Files:** none (verification only).

**Interfaces:** consumes the complete implementation from Tasks 1-4.

- [ ] **Step 1: Full automated test suite**

Run: `source venv/bin/activate && pytest -v`
Expected: 100% pass, zero failures, zero errors. Record the final test count and confirm it matches what was written into `PROJECT_CONTEXT.md` in Task 4, Step 6.

- [ ] **Step 2: Confirm no unintended files changed**

Run: `git log --stat -5` and `git diff main -- app/bedrock.py app/tts.py avatar-src/ static/dist/ static/stt-web-speech.js scripts/bedrock_check.py`
Expected: the diff is empty — none of these files appear in any commit from this plan, confirming the Global Constraints held.

- [ ] **Step 3: Start the app for manual QA**

Run: `source venv/bin/activate && uvicorn app.main:app --reload`
Tell the user the app is running at `http://127.0.0.1:8000/` and hand off to the manual checklist below — this part cannot be done by the agent, per this project's standing rule that no real browser is available in this environment.

- [ ] **Step 4: Manual browser QA checklist (user performs this)**

**Plain Text Chat (no Roleplay Session) — must be byte-identical to the pre-existing baseline:**
- [ ] Load the page. Avatar connects and renders (idle state) exactly as before.
- [ ] Send a plain-text message without starting a roleplay. Confirm the reply is generated, spoken via ElevenLabs, and lip-synced by Simli.
- [ ] Confirm the avatar/state cycle (`connecting → idle → thinking → speaking → idle`) behaves as before.
- [ ] Confirm the voice `<select>` still defaults to whatever `localStorage` held from a previous session (or ElevenLabs' first voice), unaffected by this change, since no roleplay was started.

**Live Voice (no Roleplay Session):**
- [ ] Toggle the mic button, speak, confirm transcription, reply, audio, and the `listening → thinking → speaking → listening` loop all work as before.

**Roleplay Sessions (new behavior under test):**
- [ ] Open the "Start a Roleplay" form. Confirm the persona dropdown still populates and still shows "Dr. Sarah Chen — General Practitioner" (proving `/personas`'s additive fields didn't break existing rendering).
- [ ] Before submitting, manually change the voice `<select>` to a non-default voice.
- [ ] Fill in scenario/objective/mood, select a difficulty, and click "Start Roleplay."
- [ ] Confirm the voice `<select>` is now reset to Dr. Sarah Chen's configured voice (ElevenLabs "Sarah" — `EXAVITQu4vr4xnSDxMaL`), not the one manually picked in the previous step.
- [ ] Send a chat message inside the roleplay. Confirm the reply reflects the scenario/objective/mood/difficulty as before, audio plays in the persona's (Sarah's) voice, and Simli video/lip-sync work.
- [ ] After the roleplay has started, manually change the voice `<select>` again to a different voice and send another message — confirm the new voice is used for that reply's audio (proving the override still works, not just the default).
- [ ] Click "New Roleplay." Confirm the session and conversation reset exactly as before.
- [ ] Repeat the roleplay flow using Live Voice instead of typed Text Chat for at least two consecutive turns — confirm the `listening → thinking → speaking → listening` loop still works inside an active roleplay, and Sarah's own speech is not picked back up as the user's next turn.

- [ ] **Step 5: Report results to the user**

Summarize: automated test count/pass status, confirmation that the four untouched-file diffs were empty, and the outcome of each manual QA checklist item (or hand the checklist to the user directly to run and report back, since no browser exists in this environment).
