# Performance Feedback / Scoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a stateless, qualitative "Get Feedback" capability to an active Roleplay Session — one new Bedrock evaluation call over the existing in-memory transcript, returned as four dimension assessments + an overall summary + improvement recommendations, with zero numeric scoring, zero persistence, and zero risk to any currently verified behavior.

**Architecture:** A new, isolated module (`app/evaluation.py`) mirrors `app/bedrock.py`'s existing pure-function/impure-call split without touching it. A new route (`POST /evaluate`) in `app/main.py` follows the exact structure of every existing route. The only frontend change is one new button, one new results panel, and small additive hooks into three places in the existing inline script — no existing element, route, or JS function is modified beyond those exact, enumerated touch points.

**Tech Stack:** Python 3, FastAPI, pytest (mocked at the function boundary, network-free), plain JS in `static/index.html` (no build step involved — `avatar-src/doctor-avatar.js` is not touched).

**Spec:** `docs/superpowers/specs/2026-09-18-performance-feedback-design.md`

## Global Constraints

- No numeric score, percentage, star rating, letter grade, weighting formula, pass/fail threshold, ranking, or certification logic anywhere — in the Bedrock prompt, the result schema, the backend code, or the UI.
- Evaluation is stateless: reads the existing in-memory `conversation` array and `roleplaySession` object exactly as `/chat` already does; stores nothing; no database, no session store, no cross-session history.
- A malformed or unparseable Bedrock response must produce the same generic 503 every other route already uses — never a crash, never a leaked exception string, never a change to `conversation` or `roleplaySession`.
- `app/bedrock.py`'s existing functions (`build_request_body`, `build_system_prompt`, `get_reply`, `extract_reply_text`, `DEFAULT_SYSTEM_PROMPT`, `DIFFICULTY_INSTRUCTIONS`), `app/tts.py`, `app/avatar_simli.py`, `app/avatar_provider.py`, `app/personas/models.py`, `app/personas/registry.py`, `app/personas/__init__.py`, `avatar-src/doctor-avatar.js`, `static/dist/avatar-bundle.js`, `static/stt-web-speech.js`, and `scripts/bedrock_check.py` must not be modified at all.
- `static/index.html` changes only in the exact ways enumerated in Task 3 — no redesign, no unrelated markup/CSS/JS change.
- No Admin UI, LMS/CRM integration, compliance-monitoring/MLR/audit infrastructure, certification, credentialing, badges, leaderboards, or Pre-Call Plan functionality.
- Run `pytest -v` after every backend task; all tests must pass before moving to the next task.
- `PROJECT_CONTEXT.md` is updated only in the final task, after manual browser QA has actually been performed — not before.

---

## Task 1: `app/evaluation.py` — the evaluation module, in isolation

**Files:**
- Create: `app/evaluation.py`
- Create: `tests/test_evaluation.py`

**Interfaces:**
- Consumes: `app.bedrock.MODEL_ID`, `app.bedrock.REGION` (read-only imports, not modified), `app.personas.Persona`.
- Produces: `build_evaluation_prompt(persona, session) -> str`, `build_evaluation_request_body(messages, persona, session) -> dict`, `extract_evaluation(response_body) -> dict`, `get_evaluation(messages, persona, session) -> dict` — all consumed by Task 2.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_evaluation.py`:

```python
import json

import pytest

from app.evaluation import (
    build_evaluation_prompt,
    build_evaluation_request_body,
    extract_evaluation,
)
from app.personas import Persona

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
TEST_SESSION = {
    "scenario": "Test scenario",
    "objective": "Test objective",
    "mood": "Test mood",
    "difficulty": "medium",
}
VALID_EVALUATION = {
    "dimensions": {
        "message_accuracy": "Accurate and complete.",
        "objection_handling": "Handled well.",
        "rapport_building": "Warm and attentive.",
        "compliance_adherence": "Stayed on-label.",
    },
    "overall_summary": "Solid performance overall.",
    "improvement_recommendations": "Ask more open-ended questions.",
}


def _response_with_text(text):
    return {"content": [{"type": "text", "text": text}]}


def test_build_evaluation_prompt_includes_persona_and_session_context():
    prompt = build_evaluation_prompt(TEST_PERSONA, TEST_SESSION)

    assert "Dr. Test" in prompt
    assert "Test scenario" in prompt
    assert "Test objective" in prompt
    assert "pass/fail" in prompt.lower()


def test_build_evaluation_request_body_has_correct_shape():
    messages = [{"role": "user", "content": "Hello"}]

    body = build_evaluation_request_body(messages, TEST_PERSONA, TEST_SESSION)

    assert body["anthropic_version"] == "bedrock-2023-05-31"
    assert body["messages"] == messages
    assert "Dr. Test" in body["system"]


def test_extract_evaluation_parses_valid_json():
    response_body = _response_with_text(json.dumps(VALID_EVALUATION))

    assert extract_evaluation(response_body) == VALID_EVALUATION


def test_extract_evaluation_parses_json_in_markdown_fence():
    fenced = "```json\n" + json.dumps(VALID_EVALUATION) + "\n```"
    response_body = _response_with_text(fenced)

    assert extract_evaluation(response_body) == VALID_EVALUATION


def test_extract_evaluation_parses_json_with_preamble_before_fence():
    preambled = "Here's the evaluation:\n```json\n" + json.dumps(VALID_EVALUATION) + "\n```"
    response_body = _response_with_text(preambled)

    assert extract_evaluation(response_body) == VALID_EVALUATION


def test_extract_evaluation_raises_for_non_json_text():
    response_body = _response_with_text("This is not JSON at all.")

    with pytest.raises(ValueError):
        extract_evaluation(response_body)


def test_extract_evaluation_raises_for_non_object_json():
    response_body = _response_with_text(json.dumps(["not", "an", "object"]))

    with pytest.raises(ValueError):
        extract_evaluation(response_body)


def test_extract_evaluation_raises_for_missing_dimensions_key():
    incomplete = {k: v for k, v in VALID_EVALUATION.items() if k != "dimensions"}
    response_body = _response_with_text(json.dumps(incomplete))

    with pytest.raises(ValueError):
        extract_evaluation(response_body)


def test_extract_evaluation_raises_for_missing_dimension_field():
    incomplete = json.loads(json.dumps(VALID_EVALUATION))
    del incomplete["dimensions"]["compliance_adherence"]
    response_body = _response_with_text(json.dumps(incomplete))

    with pytest.raises(ValueError):
        extract_evaluation(response_body)


def test_extract_evaluation_raises_for_non_string_field_value():
    invalid = json.loads(json.dumps(VALID_EVALUATION))
    invalid["overall_summary"] = 7
    response_body = _response_with_text(json.dumps(invalid))

    with pytest.raises(ValueError):
        extract_evaluation(response_body)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `source venv/bin/activate && pytest tests/test_evaluation.py -v`
Expected: FAIL at collection — `ModuleNotFoundError: No module named 'app.evaluation'` (the module doesn't exist yet).

- [ ] **Step 3: Create `app/evaluation.py`**

```python
import json

import boto3

from app.bedrock import MODEL_ID, REGION
from app.personas import Persona

EVALUATION_MAX_TOKENS = 1024

_client = boto3.client("bedrock-runtime", region_name=REGION)

REQUIRED_FIELDS = (
    "message_accuracy",
    "objection_handling",
    "rapport_building",
    "compliance_adherence",
)


def build_evaluation_prompt(persona: Persona, session: dict) -> str:
    return (
        "You are an impartial evaluator reviewing a completed training "
        f"roleplay conversation. Do not continue the roleplay or respond "
        f"as {persona.name}. The user was practicing a conversation with "
        f"{persona.name}, {persona.role_title}, in this scenario: "
        f"{session['scenario']}. Their objective was: {session['objective']}. "
        f"Evaluate only the user's turns (not {persona.name}'s) in the "
        "conversation below.\n\n"
        "Respond with a single JSON object and nothing else — no markdown "
        "formatting, no code fences, no commentary before or after it — "
        "containing exactly these string fields: "
        '"dimensions": {"message_accuracy", "objection_handling", '
        '"rapport_building", "compliance_adherence"}, "overall_summary", '
        '"improvement_recommendations". Each value must be a short plain-text '
        "assessment. Do not include any numeric scores, ratings, percentages, "
        "grades, or pass/fail judgments anywhere in your response — "
        "qualitative text only."
    )


def build_evaluation_request_body(
    messages: list, persona: Persona, session: dict
) -> dict:
    return {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": EVALUATION_MAX_TOKENS,
        "system": build_evaluation_prompt(persona, session),
        "messages": messages,
    }


def extract_evaluation(response_body: dict) -> dict:
    text = response_body["content"][0]["text"].strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise ValueError("Malformed evaluation response: not valid JSON")
        try:
            result = json.loads(text[start : end + 1])
        except json.JSONDecodeError as error:
            raise ValueError("Malformed evaluation response: not valid JSON") from error

    if not isinstance(result, dict):
        raise ValueError("Malformed evaluation response: not a JSON object")

    dimensions = result.get("dimensions")
    if not isinstance(dimensions, dict):
        raise ValueError("Malformed evaluation response: missing dimensions")

    for field in REQUIRED_FIELDS:
        if not isinstance(dimensions.get(field), str):
            raise ValueError(f"Malformed evaluation response: missing {field}")

    for field in ("overall_summary", "improvement_recommendations"):
        if not isinstance(result.get(field), str):
            raise ValueError(f"Malformed evaluation response: missing {field}")

    return result


def get_evaluation(messages: list, persona: Persona, session: dict) -> dict:
    body = build_evaluation_request_body(messages, persona, session)

    response = _client.invoke_model(
        modelId=MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body),
    )

    response_body = json.loads(response["body"].read())
    return extract_evaluation(response_body)
```

Note: `_client` is a second, independent `boto3.client` — `app/bedrock.py` is only read from (`MODEL_ID`, `REGION`), never modified, and its own `_client` is untouched.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `source venv/bin/activate && pytest tests/test_evaluation.py -v`
Expected: PASS (10 tests).

- [ ] **Step 5: Run the full test suite**

Run: `source venv/bin/activate && pytest -v`
Expected: all tests PASS (39 total: 29 existing + 10 new). This confirms `app/bedrock.py`'s own tests are completely unaffected by this new, isolated module.

- [ ] **Step 6: Commit**

```bash
git add app/evaluation.py tests/test_evaluation.py
git commit -m "$(cat <<'EOF'
feat: add stateless Bedrock evaluation module

app/evaluation.py mirrors app/bedrock.py's pure-function/impure-call
split without modifying it — a second, independent boto3 client,
its own prompt builder, and extract_evaluation() with a deterministic
safe-failure path (raises ValueError on anything malformed, including
a fallback that recovers JSON preceded by a preamble before a
markdown fence). No numeric score, weighting, or threshold anywhere.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: `POST /evaluate` route

**Files:**
- Modify: `app/main.py`
- Modify: `tests/test_main.py`

**Interfaces:**
- Consumes: `app.evaluation.get_evaluation` (Task 1), `app.personas.get_persona` (existing), `RoleplaySessionRequest`/`ChatMessage` (existing, defined in `app/main.py`).
- Produces: `POST /evaluate` — body `{"messages": [...], "session": {...}}` (`session` required, not optional), returns the evaluation dict verbatim on success; 400 on unknown `persona_id`; 422 if `session` is omitted; 503 on any Bedrock/parsing failure.

- [ ] **Step 1: Write the failing tests**

In `tests/test_main.py`, add these four tests (after the existing `/personas`/roleplay tests):

```python
@patch("app.main.get_evaluation")
def test_evaluate_endpoint_returns_evaluation_result(mock_get_evaluation):
    mock_get_evaluation.return_value = {
        "dimensions": {
            "message_accuracy": "Accurate.",
            "objection_handling": "Handled well.",
            "rapport_building": "Warm.",
            "compliance_adherence": "On-label.",
        },
        "overall_summary": "Solid performance.",
        "improvement_recommendations": "Ask more open-ended questions.",
    }
    session_payload = {
        "persona_id": "dr_sarah_chen",
        "scenario": "Pharmaceutical sales call",
        "objective": "Introduce a new treatment and handle objections",
        "mood": "Skeptical, short on time",
        "difficulty": "medium",
    }

    response = client.post(
        "/evaluate",
        json={
            "messages": [{"role": "user", "content": "Hello doctor"}],
            "session": session_payload,
        },
    )

    assert response.status_code == 200
    assert response.json() == mock_get_evaluation.return_value
    mock_get_evaluation.assert_called_once_with(
        [{"role": "user", "content": "Hello doctor"}],
        get_persona("dr_sarah_chen"),
        session_payload,
    )


def test_evaluate_endpoint_rejects_unknown_persona_id():
    response = client.post(
        "/evaluate",
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


@patch("app.main.get_evaluation")
def test_evaluate_endpoint_returns_503_when_evaluation_fails(mock_get_evaluation):
    mock_get_evaluation.side_effect = Exception("boom: sensitive AWS detail")
    session_payload = {
        "persona_id": "dr_sarah_chen",
        "scenario": "x",
        "objective": "y",
        "mood": "z",
        "difficulty": "medium",
    }

    response = client.post(
        "/evaluate",
        json={
            "messages": [{"role": "user", "content": "Hi"}],
            "session": session_payload,
        },
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "The evaluation service is temporarily unavailable. Please try again."
    }
    assert "sensitive AWS detail" not in response.text


def test_evaluate_endpoint_requires_session():
    response = client.post(
        "/evaluate",
        json={"messages": [{"role": "user", "content": "Hi"}]},
    )

    assert response.status_code == 422
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `source venv/bin/activate && pytest tests/test_main.py -k evaluate -v`
Expected: FAIL — `/evaluate` doesn't exist yet, so every request returns 404, not the expected status codes.

- [ ] **Step 3: Add the import, request model, and route to `app/main.py`**

Add to the imports (alongside the existing `from app.bedrock import get_reply`):

```python
from app.evaluation import get_evaluation
```

Add the request model (alongside `TTSRequest`/`AvatarSessionRequest`):

```python
class EvaluateRequest(BaseModel):
    messages: list[ChatMessage]
    session: RoleplaySessionRequest
```

Add the route (after `/personas`, before `/avatar/session`, or any position among the existing routes — order doesn't matter to FastAPI):

```python
@app.post("/evaluate")
def evaluate(request: EvaluateRequest):
    messages = [{"role": m.role, "content": m.content} for m in request.messages]

    persona = get_persona(request.session.persona_id)
    if persona is None:
        raise HTTPException(status_code=400, detail="Unknown persona_id.")

    try:
        result = get_evaluation(messages, persona, request.session.model_dump())
    except Exception:
        logger.exception("Evaluation failed")
        raise HTTPException(
            status_code=503,
            detail="The evaluation service is temporarily unavailable. Please try again.",
        )

    return result
```

Note `session: RoleplaySessionRequest` here is **required** — unlike `ChatRequest.session`, which is `RoleplaySessionRequest | None = None`. Do not make it optional; a missing `session` should 422, per the tests above.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `source venv/bin/activate && pytest tests/test_main.py -k evaluate -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Run the full test suite**

Run: `source venv/bin/activate && pytest -v`
Expected: all tests PASS (43 total: 39 from Task 1 + 4 new). This confirms `/chat`, `/personas`, `/voices`, `/tts`, `/avatar/session` are all unaffected — run `pytest tests/test_main.py -v` specifically and confirm every pre-existing test in that file (not just the new ones) still passes with its original assertions.

- [ ] **Step 6: Commit**

```bash
git add app/main.py tests/test_main.py
git commit -m "$(cat <<'EOF'
feat: add POST /evaluate route

Wires app.evaluation.get_evaluation into a new, additive route
following the exact structure of every existing route (persona
lookup + 400 on unknown id, try/except -> generic 503, never
leaking upstream exception text). session is required, unlike
/chat's optional session, since evaluation only applies to an
active Roleplay Session. /chat and every other route are untouched.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Frontend — "Get Feedback" button and results panel

**Files:**
- Modify: `static/index.html` (CSS, markup, and inline `<script>` only)

**Interfaces:**
- Consumes: `POST /evaluate` (Task 2), the existing `conversation`/`roleplaySession`/`isSending` variables and `newRoleplayBtn`/`roleplaySetupForm` elements/handlers already in the inline script.
- Produces: no new interface for other tasks to consume — this is the final consumer of `/evaluate` in this milestone.

- [ ] **Step 1: Locate the exact insertion points**

Run these to confirm each anchor still matches exactly what this task expects before editing:
```bash
grep -n "#new-roleplay-btn:focus-visible" static/index.html
grep -n '<button type="button" id="new-roleplay-btn"' static/index.html
grep -n '</form>' static/index.html
grep -n "const newRoleplayBtn = " static/index.html
grep -n "newRoleplayBtn.hidden = false;" static/index.html
grep -n "newRoleplayBtn.hidden = true;" static/index.html
grep -n "input.focus();" static/index.html
```

- [ ] **Step 2: Add CSS**

Immediately after the existing `#new-roleplay-btn:focus-visible { ... }` rule block, add:

```css
  #get-feedback-btn {
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
  #get-feedback-btn:hover:not(:disabled) {
    border-color: var(--accent-dim);
    color: var(--text);
  }
  #get-feedback-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
  #get-feedback-btn:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }

  #feedback-panel {
    margin-top: 1rem;
    padding: 1rem 1.25rem;
    background: var(--panel);
    border: 1px solid var(--panel-border);
    border-radius: var(--radius-md);
    color: var(--text);
    font-family: 'Inter', sans-serif;
    font-size: 0.9rem;
  }
  #feedback-panel h3 {
    margin: 0 0 0.75rem;
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1rem;
    color: var(--accent);
  }
  #feedback-content dt {
    color: var(--text-dim);
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-top: 0.75rem;
  }
  #feedback-content dd {
    margin: 0.2rem 0 0;
  }
  #feedback-content .feedback-error {
    color: var(--danger);
  }
  #feedback-close-btn {
    margin-top: 1rem;
    padding: 0.35rem 0.85rem;
    border: 1px solid var(--panel-border);
    border-radius: 999px;
    background: transparent;
    color: var(--text-dim);
    font-family: 'Inter', sans-serif;
    font-size: 0.75rem;
    cursor: pointer;
  }
```

No existing CSS rule is modified — only new selectors are added, all reusing existing custom properties (`--panel-border`, `--text-dim`, `--accent`, `--panel`, `--radius-md`, `--text`, `--danger`) rather than introducing new ones.

- [ ] **Step 3: Add markup**

Immediately after `<button type="button" id="new-roleplay-btn" hidden>New Roleplay</button>`, add:

```html
      <button type="button" id="get-feedback-btn" hidden disabled>Get Feedback</button>
```

Immediately after the closing `</form>` tag of `#chat-form` (the second `</form>` in the file, following `#roleplay-setup`'s own `</form>` — confirm via the Step 1 grep which line this is), add:

```html
      <div id="feedback-panel" style="display: none;">
        <h3>Performance Feedback</h3>
        <div id="feedback-content"></div>
        <button type="button" id="feedback-close-btn">Close</button>
      </div>
```

- [ ] **Step 4: Add JS element references and the button-state helper**

Immediately after `const newRoleplayBtn = document.getElementById('new-roleplay-btn');`, add:

```javascript
    const getFeedbackBtn = document.getElementById('get-feedback-btn');
    const feedbackPanel = document.getElementById('feedback-panel');
    const feedbackContent = document.getElementById('feedback-content');
    const feedbackCloseBtn = document.getElementById('feedback-close-btn');

    function updateFeedbackButtonState() {
      getFeedbackBtn.disabled = isSending || conversation.length === 0;
    }
```

- [ ] **Step 5: Hook into the roleplay-start handler**

Immediately after `newRoleplayBtn.hidden = false;` (inside `roleplaySetupForm`'s submit handler), add:

```javascript
      getFeedbackBtn.hidden = false;
      updateFeedbackButtonState();
```

- [ ] **Step 6: Hook into the "New Roleplay" reset handler**

Immediately after `newRoleplayBtn.hidden = true;` — this line appears exactly once in the file, inside `newRoleplayBtn`'s own click handler (distinct from `newRoleplayBtn.hidden = false;`, a different line touched in Step 5) — add:

```javascript
      getFeedbackBtn.hidden = true;
      feedbackPanel.style.display = 'none';
      updateFeedbackButtonState();
```

- [ ] **Step 7: Hook into `sendToSarah`'s existing `finally` block**

Immediately after `input.focus();` (inside `sendToSarah`'s `finally` block), add:

```javascript
      updateFeedbackButtonState();
```

- [ ] **Step 8: Add the "Get Feedback" and "Close" click handlers**

Add this new block after `sendToSarah`'s definition and the `form.addEventListener('submit', ...)` block (i.e., in the same region as the other top-level event listener registrations):

```javascript
    getFeedbackBtn.addEventListener('click', async () => {
      getFeedbackBtn.disabled = true;
      const originalText = getFeedbackBtn.textContent;
      getFeedbackBtn.textContent = 'Evaluating…';

      try {
        const response = await fetch('/evaluate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ messages: conversation, session: roleplaySession }),
        });

        if (!response.ok) {
          throw new Error('Evaluation request failed with status ' + response.status);
        }

        const result = await response.json();
        feedbackContent.replaceChildren();
        const dl = document.createElement('dl');
        const fields = [
          ['Message Accuracy', result.dimensions.message_accuracy],
          ['Objection Handling', result.dimensions.objection_handling],
          ['Rapport Building', result.dimensions.rapport_building],
          ['Compliance Adherence', result.dimensions.compliance_adherence],
          ['Overall Summary', result.overall_summary],
          ['Improvement Recommendations', result.improvement_recommendations],
        ];
        fields.forEach(([label, value]) => {
          const dt = document.createElement('dt');
          dt.textContent = label;
          const dd = document.createElement('dd');
          dd.textContent = value;
          dl.appendChild(dt);
          dl.appendChild(dd);
        });
        feedbackContent.appendChild(dl);
      } catch (error) {
        feedbackContent.replaceChildren();
        const errorLine = document.createElement('p');
        errorLine.className = 'feedback-error';
        errorLine.textContent = 'Something went wrong generating feedback. Please try again.';
        feedbackContent.appendChild(errorLine);
      } finally {
        feedbackPanel.style.display = 'block';
        getFeedbackBtn.textContent = originalText;
        updateFeedbackButtonState();
      }
    });

    feedbackCloseBtn.addEventListener('click', () => {
      feedbackPanel.style.display = 'none';
    });
```

Note: dimension/summary/recommendation text is rendered via `textContent`, never `innerHTML`, for every dynamic (Bedrock-generated) value — the same XSS-safe pattern `addMessage()` already uses for chat bubbles. `replaceChildren()` (not `innerHTML = ''`) clears prior content, matching the pattern already used by `personaSelect.replaceChildren()` elsewhere in this file.

- [ ] **Step 9: Diff the change to prove scope**

Run: `git diff static/index.html`
Expected: every hunk in the diff corresponds exactly to one of Steps 2-8 above — new CSS rules, the two new markup elements, the new const/function block, three single-line-or-few-line additions at the three named hook points, and the two new event listener blocks. No existing CSS rule, markup element, or JS line outside those exact points should appear as changed. If anything else appears in the diff, stop and investigate before continuing.

- [ ] **Step 10: Confirm no frontend build is needed**

Run: `git status avatar-src/ static/dist/`
Expected: no changes — `avatar-src/doctor-avatar.js` is untouched, so `npm run build` is not required.

- [ ] **Step 11: Commit**

```bash
git add static/index.html
git commit -m "$(cat <<'EOF'
feat: add Get Feedback button and results panel

Minimal additive UI for the new /evaluate endpoint: one button
(shown/hidden alongside New Roleplay, disabled until the
conversation has content or a request is in flight) and one
results panel (rendered via textContent, matching the existing
XSS-safe chat-bubble pattern). New Roleplay's existing reset gains
one addition — hiding the feedback panel and button — so stale
feedback from a discarded conversation can't linger on screen.
No other existing markup, CSS, or JS is touched.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Full regression suite and manual browser QA

**Files:** none (verification only).

**Interfaces:** consumes the complete Task 1-3 implementation.

- [ ] **Step 1: Full automated test suite**

Run: `source venv/bin/activate && pytest -v`
Expected: 100% pass. Record the exact final count (`pytest --collect-only -q | tail -1`) for Task 5.

- [ ] **Step 2: Confirm no unintended files changed**

Run: `git diff main -- app/bedrock.py app/tts.py app/avatar_provider.py app/avatar_simli.py app/personas/models.py app/personas/registry.py app/personas/__init__.py avatar-src/ static/dist/ static/stt-web-speech.js scripts/bedrock_check.py`
Expected: empty diff.

- [ ] **Step 3: Start the app for manual QA**

Run: `source venv/bin/activate && uvicorn app.main:app --reload`
Tell the user the app is running at `http://127.0.0.1:8000/` (or another free port if that one is occupied by an unrelated process — check first) and hand off to the checklist below.

- [ ] **Step 4: Manual browser QA checklist (user performs this)**

**Core feature:**
- [ ] Start a Roleplay Session with any persona. Confirm "Get Feedback" is present but disabled before any message is sent.
- [ ] Send at least one message. Confirm "Get Feedback" becomes enabled.
- [ ] Click "Get Feedback." Confirm a results panel appears containing all four dimension assessments (Message Accuracy, Objection Handling, Rapport Building, Compliance Adherence), an Overall Summary, and Improvement Recommendations — as plain qualitative text, with **no number, percentage, gauge, star rating, or pass/fail judgment anywhere in the panel**.
- [ ] Click "Close." Confirm the panel disappears and Text Chat still works normally afterward.

**Regression — must be unaffected by this feature existing:**
- [ ] Confirm Live Voice still works across multiple consecutive turns, both before and after using "Get Feedback" at least once in the same session.
- [ ] Confirm the Simli avatar, ElevenLabs audio, and audio-unlock all continue to work exactly as before.
- [ ] Click "New Roleplay" after having used "Get Feedback." Confirm the session and conversation fully reset **and** the feedback panel is no longer visible in the new roleplay.
- [ ] Repeat the "Get Feedback" flow with each of the three registered personas (Dr. Sarah Chen, Dr. Marcus Reyes, Dr. Priya Nair) to confirm the feature works generically.
- [ ] If a failure can be induced (e.g., a transient network issue while the "Get Feedback" request is in flight), confirm the panel shows the inline error message and that the conversation and roleplay session remain fully usable immediately afterward.
- [ ] Load the page fresh and use plain Text Chat **without** starting a roleplay. Confirm this path is completely unaffected — no "Get Feedback" button ever appears outside an active roleplay.

- [ ] **Step 5: Report results**

Summarize the automated test count/pass status, the untouched-file diff result, and the outcome of each manual QA item before proceeding to Task 5.

---

## Task 5: Update `PROJECT_CONTEXT.md` (only after manual QA passes)

**Files:**
- Modify: `PROJECT_CONTEXT.md`

**Interfaces:** consumes the verified outcome of Task 4 — this task must not run until Task 4's manual QA has actually been performed and reported.

- [ ] **Step 1: Add a "Performance Feedback" section**

Add a new `## Performance Feedback` section (positioned after `## Roleplay Sessions`, before `## ElevenLabs TTS integration`, matching this file's existing chronological-by-milestone ordering), documenting: the new `app/evaluation.py` module and its four functions; the `POST /evaluate` route (required `session`, 400 on unknown persona, 503 on any Bedrock/parsing failure); the qualitative-only result schema (four dimensions + overall summary + recommendations, explicitly no numeric score anywhere, and why — citing the same source-grounding rationale from the design spec); the new `#get-feedback-btn`/`#feedback-panel` UI and exactly what it does and doesn't touch; and a reference to `docs/superpowers/specs/2026-09-18-performance-feedback-design.md` for the full rationale.

- [ ] **Step 2: Add a "Manually verified" statement**

Using the real current date from this session's own date context (not a guessed or reused date), state that this milestone has been manually verified end-to-end by the user in Chrome, enumerating exactly what was confirmed in Task 4's manual QA (feedback generation for all three personas, qualitative-only content, regression-free Text Chat/Live Voice/Simli/ElevenLabs/audio-unlock, correct panel reset on New Roleplay) — following the same "Manually verified end-to-end... (date): ..." convention already used for every prior milestone in this file. Do not write this statement until Task 4's manual QA has actually been reported back.

- [ ] **Step 3: Update "Features currently working"**

Add one bullet for Performance Feedback, matching the style of the existing bullets for Roleplay Sessions and Persona Library.

- [ ] **Step 4: Update "Next planned feature"**

Describe Performance Feedback as the now-completed milestone, reference the spec path, and state nothing is queued up after it (unless told otherwise at the time this task is executed).

- [ ] **Step 5: Update the test count**

Run `source venv/bin/activate && pytest --collect-only -q | tail -1` and update the "Tests and how to run them" section's test-count sentence to the real number returned.

- [ ] **Step 6: Run the full test suite**

Run: `source venv/bin/activate && pytest -v`
Expected: unaffected (docs-only change) — same pass count as Task 4 Step 1.

- [ ] **Step 7: Commit**

```bash
git add PROJECT_CONTEXT.md
git commit -m "$(cat <<'EOF'
docs: document Performance Feedback in PROJECT_CONTEXT.md

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```
