# HCP Specialty Personas Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add exactly two new doctor personas — Dr. Marcus Reyes (Cardiologist) and Dr. Priya Nair (Oncologist) — to the existing `app/personas/registry.py`, using the already-built, already-tested function-based Persona Library mechanism, with zero changes to any other code path.

**Architecture:** This is a pure data addition. Two new entries go into the existing `_PERSONAS` dict, both under the existing `category="doctor"` value, both using already-verified ElevenLabs voice IDs and the existing shared Simli `face_id`. No new functions, no new fields, no new files, no frontend change — `get_persona`/`list_personas`, `build_system_prompt`, `POST /avatar/session`, and the Roleplay setup form's persona/voice-defaulting logic all already work generically for any number of personas.

**Tech Stack:** Python 3, FastAPI, pytest (mocked at the function boundary, network-free) — unchanged from the rest of the project.

**Spec:** `docs/superpowers/specs/2026-09-18-hcp-specialty-personas-design.md`

## Global Constraints

- Dr. Sarah Chen's existing registry entry (`id, name, role_title, category, base_description, safety_framing, voice_id, face_id`) must not change in any way.
- Exactly two new personas are added: `dr_marcus_reyes` (Cardiologist) and `dr_priya_nair` (Oncologist). No other persona, role, or category.
- Both new personas use `category="doctor"` — no new category value is introduced anywhere.
- `voice_id` values are the already-verified ElevenLabs IDs from the spec: Cardiologist → `IKne3meq5aSn9XLyUdCD` ("Charlie"), Oncologist → `SAz9YHcvj6GT2YYXdXww` ("River"). Do not substitute or invent any other value.
- `face_id` for both new personas is the existing shared constant `f0ba4efe-7946-45de-9955-c04a04c367b9` — the same value Dr. Sarah Chen's entry already uses. No face-switching or reconnect logic is added anywhere.
- `app/main.py`, `app/bedrock.py`, `app/tts.py`, `app/avatar_provider.py`, `app/avatar_simli.py`, `app/personas/models.py`, `app/personas/__init__.py`, `avatar-src/doctor-avatar.js`, `static/dist/avatar-bundle.js`, `static/stt-web-speech.js`, `static/index.html`, `scripts/bedrock_check.py` must not be modified at all in this plan.
- No database, no Admin routes, no scoring/compliance, no AI Tutor, no simultaneous multi-stakeholder scenes, no new frontend state, no UI redesign — all explicitly out of scope per the approved spec.
- Run `pytest -v` after every task; all tests must pass before moving to the next task.
- `PROJECT_CONTEXT.md` is updated only in the final task, after manual browser QA has actually been performed — not before.

---

## Task 1: Add the two new persona registry entries, with tests

**Files:**
- Modify: `app/personas/registry.py`
- Modify: `tests/test_personas.py`
- Modify: `tests/test_main.py`

**Interfaces:**
- Consumes: `app.personas.models.Persona` (unchanged, existing dataclass), `app.personas.registry.get_persona`/`list_personas` (unchanged signatures).
- Produces: `get_persona("dr_marcus_reyes")` and `get_persona("dr_priya_nair")` now return populated `Persona` instances; `list_personas()` now returns 3 entries in insertion order (Sarah, Marcus, Priya); `GET /personas` now returns a 3-element JSON array in that same order.

- [ ] **Step 1: Write the failing tests for the two new personas**

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


def test_dr_marcus_reyes_has_expected_fields():
    marcus = get_persona("dr_marcus_reyes")

    assert isinstance(marcus, Persona)
    assert marcus.id == "dr_marcus_reyes"
    assert marcus.name == "Dr. Marcus Reyes"
    assert marcus.role_title == "Cardiologist"
    assert marcus.category == "doctor"
    assert "cardiologist" in marcus.base_description.lower()
    assert "roleplay" in marcus.safety_framing.lower()
    assert marcus.voice_id == "IKne3meq5aSn9XLyUdCD"
    assert marcus.face_id == "f0ba4efe-7946-45de-9955-c04a04c367b9"


def test_dr_priya_nair_has_expected_fields():
    priya = get_persona("dr_priya_nair")

    assert isinstance(priya, Persona)
    assert priya.id == "dr_priya_nair"
    assert priya.name == "Dr. Priya Nair"
    assert priya.role_title == "Oncologist"
    assert priya.category == "doctor"
    assert "oncologist" in priya.base_description.lower()
    assert "roleplay" in priya.safety_framing.lower()
    assert priya.voice_id == "SAz9YHcvj6GT2YYXdXww"
    assert priya.face_id == "f0ba4efe-7946-45de-9955-c04a04c367b9"


def test_get_persona_returns_none_for_unknown_id():
    assert get_persona("nonexistent_persona") is None


def test_list_personas_includes_sarah():
    personas = list_personas()

    assert len(personas) == 3
    assert any(p.id == "dr_sarah_chen" for p in personas)
    assert any(p.id == "dr_marcus_reyes" for p in personas)
    assert any(p.id == "dr_priya_nair" for p in personas)
    assert all(isinstance(p, Persona) for p in personas)
```

- [ ] **Step 2: Run the tests to verify the new ones fail**

Run: `source venv/bin/activate && pytest tests/test_personas.py -v`
Expected: `test_dr_marcus_reyes_has_expected_fields` and `test_dr_priya_nair_has_expected_fields` FAIL (both personas don't exist yet — `get_persona` returns `None`, causing an `AttributeError` on `.id`). `test_list_personas_includes_sarah` also FAILS (`len(personas) == 3` is false — it's currently 1). The three pre-existing Sarah/unknown-id tests still PASS.

- [ ] **Step 3: Add the two new entries to the registry**

In `app/personas/registry.py`, add these two entries to the `_PERSONAS` dict, immediately after the existing `"dr_sarah_chen"` entry (inside the same dict literal, as sibling keys):

```python
    "dr_marcus_reyes": Persona(
        id="dr_marcus_reyes",
        name="Dr. Marcus Reyes",
        role_title="Cardiologist",
        category="doctor",
        base_description=(
            "You are Dr. Marcus Reyes, an experienced cardiologist "
            "taking part in a training roleplay conversation. Speak "
            "precisely and efficiently, focus on clinical outcomes and "
            "mechanism of action, and respond the way a real "
            "cardiologist evaluating a new treatment would in a "
            "consultation."
        ),
        safety_framing=(
            "This is a roleplay for practice and learning purposes "
            "only, not real medical care: do not provide actual "
            "cardiology diagnoses or treatment advice, and if the user "
            "describes a real medical emergency, tell them to contact "
            "real emergency services immediately."
        ),
        voice_id="IKne3meq5aSn9XLyUdCD",
        face_id="f0ba4efe-7946-45de-9955-c04a04c367b9",
    ),
    "dr_priya_nair": Persona(
        id="dr_priya_nair",
        name="Dr. Priya Nair",
        role_title="Oncologist",
        category="doctor",
        base_description=(
            "You are Dr. Priya Nair, an experienced oncologist taking "
            "part in a training roleplay conversation. Speak carefully "
            "and thoughtfully, focus on safety data and treatment "
            "evidence, and respond the way a real oncologist evaluating "
            "a new therapy would in a consultation."
        ),
        safety_framing=(
            "This is a roleplay for practice and learning purposes "
            "only, not real medical care: do not provide actual "
            "oncology diagnoses or treatment advice, and if the user "
            "describes a real medical emergency, tell them to contact "
            "real emergency services immediately."
        ),
        voice_id="SAz9YHcvj6GT2YYXdXww",
        face_id="f0ba4efe-7946-45de-9955-c04a04c367b9",
    ),
```

The existing `"dr_sarah_chen"` entry, `get_persona`, and `list_personas` function bodies are not touched — only two new sibling dict entries are added.

- [ ] **Step 4: Run the tests to verify they now pass**

Run: `source venv/bin/activate && pytest tests/test_personas.py -v`
Expected: PASS (6 tests: 2 Sarah tests, 2 new persona tests, 1 unknown-id test, 1 list-personas test).

- [ ] **Step 5: Update `tests/test_main.py`'s `/personas` test for the 3-persona response**

Replace `test_personas_returns_registered_personas` (currently expects a 1-element list) with:

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
        },
        {
            "id": "dr_marcus_reyes",
            "name": "Dr. Marcus Reyes",
            "role_title": "Cardiologist",
            "category": "doctor",
            "voice_id": "IKne3meq5aSn9XLyUdCD",
            "face_id": "f0ba4efe-7946-45de-9955-c04a04c367b9",
        },
        {
            "id": "dr_priya_nair",
            "name": "Dr. Priya Nair",
            "role_title": "Oncologist",
            "category": "doctor",
            "voice_id": "SAz9YHcvj6GT2YYXdXww",
            "face_id": "f0ba4efe-7946-45de-9955-c04a04c367b9",
        },
    ]
```

No other test in `tests/test_main.py` changes — `test_chat_endpoint_with_roleplay_session_passes_persona_and_session` and `test_chat_endpoint_rejects_unknown_persona_id` both explicitly reference `"dr_sarah_chen"` or an unknown id, and are unaffected by additional personas existing.

- [ ] **Step 6: Run the full test suite**

Run: `source venv/bin/activate && pytest -v`
Expected: all tests PASS. This confirms the addition didn't disturb `test_bedrock.py` (uses its own synthetic `TEST_PERSONA` fixture, independent of the registry), `test_bedrock_check.py`, or any other `test_main.py` test — including the no-`session` `/chat` tests and the roleplay-session-with-Sarah test, proving backward compatibility holds with 3 personas registered instead of 1.

- [ ] **Step 7: Commit**

```bash
git add app/personas/registry.py tests/test_personas.py tests/test_main.py
git commit -m "$(cat <<'EOF'
feat: add Dr. Marcus Reyes and Dr. Priya Nair HCP personas

Two new doctor-category personas (Cardiologist, Oncologist) added to
the existing Persona Library registry, sourced directly from the
market analysis document's Tier 1 "Specialty Controls: Configurable
by HCP specialty (Cardio, Onco)" requirement. Both use
already-verified ElevenLabs voice IDs and the existing shared Simli
face_id — no new category, no face-switching, no mechanism change.
Dr. Sarah Chen's entry is untouched.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Full regression suite and manual browser QA

**Files:** none (verification only).

**Interfaces:** consumes the complete Task 1 implementation.

- [ ] **Step 1: Full automated test suite**

Run: `source venv/bin/activate && pytest -v`
Expected: 100% pass. Record the exact final test count (`pytest --collect-only -q | tail -1`) for use in Task 3.

- [ ] **Step 2: Confirm no unintended files changed**

Run: `git diff main -- app/bedrock.py app/tts.py app/main.py app/avatar_provider.py app/avatar_simli.py app/personas/models.py app/personas/__init__.py avatar-src/ static/dist/ static/stt-web-speech.js static/index.html scripts/bedrock_check.py`
Expected: the diff is empty — confirming every Global Constraint held and this task touched only what Task 1 said it would.

- [ ] **Step 3: Start the app for manual QA**

Run: `source venv/bin/activate && uvicorn app.main:app --reload`
Tell the user the app is running at `http://127.0.0.1:8000/` and hand off to the manual checklist below — per this project's standing rule, no real browser exists in this environment, so this part is performed by the user.

- [ ] **Step 4: Manual browser QA checklist (user performs this)**

**Persona selection and voice defaulting, across all three personas:**
- [ ] Open the "Start a Roleplay" form. Confirm the persona dropdown now lists all three: Dr. Sarah Chen — General Practitioner, Dr. Marcus Reyes — Cardiologist, Dr. Priya Nair — Oncologist.
- [ ] Select **Dr. Sarah Chen**, fill in scenario/objective/mood, start the roleplay. Confirm the voice selector defaults to ElevenLabs' "Sarah" voice.
- [ ] Send a message. Confirm the Bedrock reply reflects a general-practitioner tone and the scenario/objective/mood/difficulty configured, exactly as before this change (regression check on the pre-existing persona).
- [ ] Manually override the voice selector to a different voice and send another message — confirm the new voice is used (proving the override still works).
- [ ] Click "New Roleplay." Select **Dr. Marcus Reyes**. Confirm the voice selector defaults to "Charlie."
- [ ] Send a message. Confirm the Bedrock reply reflects a cardiologist's tone (precise, outcomes/mechanism-focused) consistent with the persona's description.
- [ ] Click "New Roleplay." Select **Dr. Priya Nair**. Confirm the voice selector defaults to "River."
- [ ] Send a message. Confirm the Bedrock reply reflects an oncologist's tone (careful, evidence/safety-focused).

**Regression check on everything this milestone must not affect:**
- [ ] Confirm the Simli avatar connects, renders, and lip-syncs identically for all three personas (same shared face — no visual difference expected, and none should appear).
- [ ] Confirm ElevenLabs audio plays and the audio-unlock behavior (first gesture required) works identically regardless of which persona is active.
- [ ] With any one of the three personas active in a roleplay, use Live Voice (mic toggle) for at least two consecutive turns. Confirm the `listening → thinking → speaking → listening` loop works exactly as before, and Sarah's/Marcus's/Priya's own speech is not picked back up as the user's next turn.
- [ ] Load the page fresh and use plain Text Chat **without** starting a roleplay. Confirm this still uses the original default behavior, completely unaffected by the persona catalog now having 3 entries.

- [ ] **Step 5: Report results**

Summarize the automated test count/pass status, the untouched-file diff result, and the outcome of each manual QA item to the user before proceeding to Task 3.

---

## Task 3: Update `PROJECT_CONTEXT.md` (only after manual QA passes)

**Files:**
- Modify: `PROJECT_CONTEXT.md`

**Interfaces:** consumes the verified outcome of Task 2 — this task must not run until Task 2's manual QA has actually been performed and reported, per this plan's Global Constraints.

- [ ] **Step 1: Update the "Persona registry" section's persona-count sentence**

Find the sentence ending "...Dr. Sarah Chen is still the only entry today, structurally no different from any future persona." in the `## Roleplay Sessions` section's persona registry paragraph. Replace it with:

```
Three personas are registered today — Dr. Sarah Chen (General
Practitioner), Dr. Marcus Reyes (Cardiologist), and Dr. Priya Nair
(Oncologist), all under `category="doctor"` — added by the same
one-dict-entry mechanism this paragraph describes, with no change to
`get_persona`/`list_personas`'s signatures or any caller.
```

- [ ] **Step 2: Update the "Features currently working" Persona Library bullet**

Find the bullet starting "- Persona Library: function-based persona registry...". Replace its content to state that three personas now exist and that all three have been manually verified (persona selection, voice defaulting and override, Bedrock reply content, Simli, ElevenLabs, Live Voice, audio-unlock), using the actual current date from this session's own date context for the verification date — do not reuse the `2026-09-18` date already present elsewhere in the file for the Persona Library milestone unless this verification genuinely happens on that same date; use whatever the real date is when this step is executed.

- [ ] **Step 3: Update "Next planned feature"**

Replace the section's content to describe HCP Specialty Personas (Dr. Marcus Reyes, Cardiologist; Dr. Priya Nair, Oncologist) as the now-completed milestone, referencing `docs/superpowers/specs/2026-09-18-hcp-specialty-personas-design.md` for the design rationale, stating it is built and manually verified end-to-end (using the real current date, per Step 2's instruction), and that nothing is queued up after it.

- [ ] **Step 4: Update the test count**

Run `source venv/bin/activate && pytest --collect-only -q | tail -1` and update the "Tests and how to run them" section's test-count sentence to the real number returned — do not guess or reuse `27`.

- [ ] **Step 5: Run the full test suite**

Run: `source venv/bin/activate && pytest -v`
Expected: unaffected — this is a docs-only change; confirm the same pass count as Task 2 Step 1 to catch any accidental code edit.

- [ ] **Step 6: Commit**

```bash
git add PROJECT_CONTEXT.md
git commit -m "$(cat <<'EOF'
docs: document the two new HCP specialty personas in PROJECT_CONTEXT.md

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```
