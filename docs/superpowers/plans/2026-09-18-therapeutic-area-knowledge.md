# Therapeutic Area / Product Knowledge Grounding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one optional, user-pasted `reference_material` field to a Roleplay Session that grounds both the persona's replies and the Performance Feedback evaluation, with empty/omitted values preserving today's behavior exactly.

**Architecture:** A new optional string on the shared `RoleplaySessionRequest` flows to `/chat` and `/evaluate` unchanged; `build_system_prompt` and `build_evaluation_prompt` each insert a delimited reference block only when the (trimmed) value is non-empty. The frontend gains a textarea + character counter and includes the field in the session object only when non-empty. Stateless; nothing stored.

**Tech Stack:** FastAPI + Pydantic 2, pytest (mocked boundaries), plain HTML/CSS/JS inline script. No build step.

**Spec:** `docs/superpowers/specs/2026-09-18-therapeutic-area-knowledge-design.md` (source of truth; decisions D1–D11).

## Global Constraints

- Empty, `null`, absent and whitespace-only `reference_material` → prompts byte-identical to today's; frontend omits the key when empty.
- Cap: `REFERENCE_MATERIAL_MAX_CHARS = 8000`, Pydantic `max_length` (422), mirrored by textarea `maxlength="8000"`. Mini ECHO guardrail, not a source requirement.
- `model_dump(exclude_none=True)` at the two existing call sites in `app/main.py`; the two existing exact-dict tests must pass unmodified.
- Persona block goes **before** `persona.safety_framing`, which must remain the last text of the prompt.
- Evaluator may quote/discuss figures that appear in the material; never introduce numbers not in it; never numeric scoring/weights/thresholds/rankings/certification.
- Do NOT touch: `app/tts.py`, `app/avatar_simli.py`, `app/avatar_provider.py`, `avatar-src/`, `static/dist/`, `static/stt-web-speech.js`, `app/personas/`, `scripts/bedrock_check.py`, the trailing synthetic user message in `build_evaluation_request_body`, `extract_evaluation`. No `npm run build`.
- Do NOT update `PROJECT_CONTEXT.md` as completed; do NOT merge or push.
- Run tests with `/Users/abdulrahman/Desktop/Mini_Echo_MVP/venv/bin/python -m pytest -q` from the worktree.

---

### Task 1: Request contract and route passthrough

**Files:**
- Modify: `app/main.py` (imports; `RoleplaySessionRequest`; two `model_dump()` calls)
- Test: `tests/test_main.py`

**Interfaces:**
- Produces: `RoleplaySessionRequest.reference_material: str | None`; `REFERENCE_MATERIAL_MAX_CHARS = 8000`; session dicts passed to `get_reply`/`get_evaluation` contain `reference_material` only when a non-null value was sent.

- [ ] **Step 1: Write failing tests** (append to `tests/test_main.py`)

```python
SESSION_BASE = {
    "persona_id": "dr_sarah_chen",
    "scenario": "Pharmaceutical sales call",
    "objective": "Introduce a new treatment and handle objections",
    "mood": "Skeptical, short on time",
    "difficulty": "medium",
}


@patch("app.main.get_reply")
def test_chat_passes_reference_material_to_get_reply(mock_get_reply):
    mock_get_reply.return_value = "reply"
    session_payload = {**SESSION_BASE, "reference_material": "Zorivex: 32% response rate."}

    response = client.post(
        "/chat",
        json={"messages": [{"role": "user", "content": "Hi"}], "session": session_payload},
    )

    assert response.status_code == 200
    mock_get_reply.assert_called_once_with(
        [{"role": "user", "content": "Hi"}],
        persona=get_persona("dr_sarah_chen"),
        session=session_payload,
    )


@patch("app.main.get_reply")
def test_chat_null_reference_material_is_omitted_from_session_dict(mock_get_reply):
    mock_get_reply.return_value = "reply"

    response = client.post(
        "/chat",
        json={
            "messages": [{"role": "user", "content": "Hi"}],
            "session": {**SESSION_BASE, "reference_material": None},
        },
    )

    assert response.status_code == 200
    assert mock_get_reply.call_args.kwargs["session"] == SESSION_BASE


@patch("app.main.get_reply")
def test_chat_accepts_reference_material_at_the_cap(mock_get_reply):
    mock_get_reply.return_value = "reply"

    response = client.post(
        "/chat",
        json={
            "messages": [{"role": "user", "content": "Hi"}],
            "session": {**SESSION_BASE, "reference_material": "x" * 8000},
        },
    )

    assert response.status_code == 200


@patch("app.main.get_reply")
def test_chat_rejects_reference_material_over_the_cap(mock_get_reply):
    response = client.post(
        "/chat",
        json={
            "messages": [{"role": "user", "content": "Hi"}],
            "session": {**SESSION_BASE, "reference_material": "x" * 8001},
        },
    )

    assert response.status_code == 422
    mock_get_reply.assert_not_called()


@patch("app.main.get_evaluation")
def test_evaluate_passes_reference_material_to_get_evaluation(mock_get_evaluation):
    mock_get_evaluation.return_value = {"ok": True}
    session_payload = {**SESSION_BASE, "reference_material": "Zorivex: 32% response rate."}

    response = client.post(
        "/evaluate",
        json={"messages": [{"role": "user", "content": "Hi"}], "session": session_payload},
    )

    assert response.status_code == 200
    mock_get_evaluation.assert_called_once_with(
        [{"role": "user", "content": "Hi"}],
        get_persona("dr_sarah_chen"),
        session_payload,
    )


@patch("app.main.get_evaluation")
def test_evaluate_rejects_reference_material_over_the_cap(mock_get_evaluation):
    response = client.post(
        "/evaluate",
        json={
            "messages": [{"role": "user", "content": "Hi"}],
            "session": {**SESSION_BASE, "reference_material": "x" * 8001},
        },
    )

    assert response.status_code == 422
    mock_get_evaluation.assert_not_called()
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_main.py -q`
Expected: the passthrough tests and both over-cap tests FAIL (field currently ignored / no cap); all pre-existing tests pass.

- [ ] **Step 3: Implement** in `app/main.py`

`from pydantic import BaseModel, Field`; above `RoleplaySessionRequest` add `REFERENCE_MATERIAL_MAX_CHARS = 8000`; add to the model:

```python
    reference_material: str | None = Field(
        default=None, max_length=REFERENCE_MATERIAL_MAX_CHARS
    )
```

Change both `request.session.model_dump()` calls (in `/chat` and `/evaluate`) to `request.session.model_dump(exclude_none=True)`.

- [ ] **Step 4: Run to verify pass** — `pytest -q` → all pass (44 existing + 6 new).

- [ ] **Step 5: Commit** — `git add app/main.py tests/test_main.py && git commit -m "feat: accept optional reference_material on roleplay sessions"`

### Task 2: Persona prompt grounding

**Files:**
- Modify: `app/bedrock.py` (`build_system_prompt`; new `REFERENCE_MATERIAL_FRAMING`)
- Test: `tests/test_bedrock.py` (add `import pytest`; import `DIFFICULTY_INSTRUCTIONS`)

**Interfaces:**
- Consumes: session dict with optional `reference_material` (Task 1).
- Produces: `REFERENCE_MATERIAL_FRAMING: str`; `build_system_prompt(persona, session)` unchanged signature.

- [ ] **Step 1: Write failing tests** (append)

```python
MATERIAL = "Zorivex achieved a 32% response rate in its pivotal trial."


def test_build_system_prompt_without_reference_material_is_unchanged():
    assert build_system_prompt(TEST_PERSONA, TEST_SESSION) == (
        "BASE DESCRIPTION.\n\n"
        "Scenario: Test scenario\n"
        "Conversation objective: Test objective\n"
        "Persona mood/behavior for this conversation: Test mood\n"
        f"Difficulty: {DIFFICULTY_INSTRUCTIONS['medium']}\n\n"
        "SAFETY FRAMING."
    )


def test_build_system_prompt_includes_reference_material_before_safety_framing():
    prompt = build_system_prompt(
        TEST_PERSONA, {**TEST_SESSION, "reference_material": MATERIAL}
    )

    assert f"<reference_material>\n{MATERIAL}\n</reference_material>" in prompt
    assert "do not recite" in prompt
    assert prompt.index("<reference_material>") < prompt.index("SAFETY FRAMING.")
    assert prompt.endswith("SAFETY FRAMING.")


def test_build_system_prompt_trims_reference_material():
    prompt = build_system_prompt(
        TEST_PERSONA, {**TEST_SESSION, "reference_material": f"  \n{MATERIAL}\n  "}
    )

    assert f"<reference_material>\n{MATERIAL}\n</reference_material>" in prompt


@pytest.mark.parametrize("empty", [None, "", "   \n\t "])
def test_build_system_prompt_ignores_empty_reference_material(empty):
    baseline = build_system_prompt(TEST_PERSONA, TEST_SESSION)

    prompt = build_system_prompt(
        TEST_PERSONA, {**TEST_SESSION, "reference_material": empty}
    )

    assert prompt == baseline


def test_build_system_prompt_without_persona_ignores_reference_material():
    session = {**TEST_SESSION, "reference_material": MATERIAL}

    assert build_system_prompt(None, session) == DEFAULT_SYSTEM_PROMPT
```

- [ ] **Step 2: Run** — `pytest tests/test_bedrock.py -q` → the includes/trims tests FAIL; the "unchanged", "empty", and "without persona" tests already pass (regression guards).

- [ ] **Step 3: Implement** in `app/bedrock.py` — add `REFERENCE_MATERIAL_FRAMING` and the `reference_block` logic exactly as in the spec's "Persona prompt" section; the block is inserted between the `Difficulty:` line's trailing `\n\n` and `persona.safety_framing`.

- [ ] **Step 4: Run** — `pytest -q` → all pass.

- [ ] **Step 5: Commit** — `git add app/bedrock.py tests/test_bedrock.py && git commit -m "feat: ground persona system prompt in reference material"`

### Task 3: Evaluation prompt grounding

**Files:**
- Modify: `app/evaluation.py` (`build_evaluation_prompt`)
- Test: `tests/test_evaluation.py`

**Interfaces:**
- Consumes: session dict with optional `reference_material`.
- Produces: `build_evaluation_prompt(persona, session)` unchanged signature; paragraph inserted between the "Evaluate only the user's turns…" sentence and "Respond with a single JSON object…".

- [ ] **Step 1: Write failing tests** (append)

```python
MATERIAL = "Zorivex achieved a 32% response rate in its pivotal trial."


def test_build_evaluation_prompt_includes_reference_material():
    prompt = build_evaluation_prompt(
        TEST_PERSONA, {**TEST_SESSION, "reference_material": MATERIAL}
    )

    assert f"<reference_material>\n{MATERIAL}\n</reference_material>" in prompt
    assert "cannot be verified" in prompt
    assert "never introduce a number" in prompt
    assert "score, weight, rank, threshold, grade or certify" in prompt
    assert prompt.index("<reference_material>") < prompt.index(
        "Respond with a single JSON object"
    )


@pytest.mark.parametrize("empty", [None, "", "   \n\t "])
def test_build_evaluation_prompt_ignores_empty_reference_material(empty):
    baseline = build_evaluation_prompt(TEST_PERSONA, TEST_SESSION)

    prompt = build_evaluation_prompt(
        TEST_PERSONA, {**TEST_SESSION, "reference_material": empty}
    )

    assert prompt == baseline
    assert "reference_material" not in baseline
    assert "Reference material" not in baseline


def test_build_evaluation_request_body_keeps_trailing_user_message_with_material():
    body = build_evaluation_request_body(
        [{"role": "assistant", "content": "Hi"}],
        TEST_PERSONA,
        {**TEST_SESSION, "reference_material": MATERIAL},
    )

    assert MATERIAL in body["system"]
    assert body["messages"][-1] == {
        "role": "user",
        "content": "Now produce the evaluation JSON object described above.",
    }
```

- [ ] **Step 2: Run** — `pytest tests/test_evaluation.py -q` → the includes test FAILS; the others pass.

- [ ] **Step 3: Implement** in `app/evaluation.py` — normalize `(session.get("reference_material") or "").strip()`; when non-empty, insert the spec's "Evaluation prompt" paragraph (with the final numeric wording from D7) between the two existing prompt segments; when empty, the returned string must be byte-identical to today's.

- [ ] **Step 4: Run** — `pytest -q` → all pass.

- [ ] **Step 5: Commit** — `git add app/evaluation.py tests/test_evaluation.py && git commit -m "feat: ground evaluation prompt in reference material"`

### Task 4: Frontend textarea, counter, session wiring

**Files:**
- Modify: `static/index.html` (CSS selector lists + two small rules; markup; inline script)

**Interfaces:**
- Consumes: `roleplaySession` object construction in the setup `submit` handler.
- Produces: `roleplaySession.reference_material` only when the trimmed textarea is non-empty.

- [ ] **Step 1: CSS** — add `.roleplay-field textarea` to the base and `:focus` selector lists next to `input[type="text"], select`; add `.roleplay-field textarea { resize: vertical; min-height: 6rem; line-height: 1.4; }` and `.roleplay-field-hint { font-size: 0.72rem; line-height: 1.35; color: var(--text-dim); }`.
- [ ] **Step 2: Markup** — the spec's `<label class="roleplay-field">Reference Material (optional)` block, after the Difficulty label and before the Start button, with a comment noting `8000` mirrors `REFERENCE_MATERIAL_MAX_CHARS`.
- [ ] **Step 3: Script** — (1) `referenceMaterialInput`/`referenceMaterialCount` lookups beside the other setup-form lookups; (2) in the submit handler, `const referenceMaterial = referenceMaterialInput.value.trim();` and after `roleplaySession = {...}`: `if (referenceMaterial) roleplaySession.reference_material = referenceMaterial;`; (3) an `input` listener plus one initial call writing `referenceMaterialInput.value.length` into the counter.
- [ ] **Step 4: Prove scope** — `git diff static/index.html` shows only these CSS/markup/script items; `git diff --stat` shows no change under `avatar-src/`, `static/dist/`, `static/stt-web-speech.js`.
- [ ] **Step 5: Verify served** — start the app, `curl -s localhost:PORT/ | grep -c reference-material-input`; run `pytest -q`.
- [ ] **Step 6: Commit** — `git add static/index.html && git commit -m "feat: add reference material field to roleplay setup"`

### Task 5: Whole-branch review and readiness

- [ ] Run the full suite; expected: 44 existing + new tests, all passing.
- [ ] Byte-identity check: import the pre-change `build_system_prompt`/`build_evaluation_prompt` from `git show HEAD~N:` copies (the `6498290` versions) and compare outputs against the new functions for absent/`None`/empty/whitespace values across all personas and difficulties.
- [ ] `curl` checks against the running server: over-cap → 422 on `/chat` and `/evaluate`; at-cap accepted past validation.
- [ ] Review the full `git diff 6498290..HEAD` against the spec; confirm protected files unchanged; fix real findings; rerun tests.
- [ ] Leave the server running on a free port for manual QA. Do not merge, push, or touch `PROJECT_CONTEXT.md`.
