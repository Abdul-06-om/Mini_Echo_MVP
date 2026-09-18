# HCP Specialty Personas — Design Spec

Status: approved design, not yet implemented.
Extends the architecture documented in `PROJECT_CONTEXT.md`. Read that file
first for the system this plugs into, and
`docs/superpowers/specs/2026-09-17-persona-library-design.md` for the
`Persona` model and function-based registry this milestone adds data to —
this spec introduces no new architecture, only two new registry entries.

## Goal

Add two new doctor personas — a cardiologist and an oncologist — to the
existing Persona Library registry, so a Roleplay Session can be started
against a healthcare professional whose specialty differs from Dr. Sarah
Chen's general practice. This directly satisfies the one Persona Library
capability that was built but never exercised with more than one entry:
`get_persona`/`list_personas` already support any number of personas: this
milestone is purely adding data, using a mechanism that already works and
is already tested.

## Provenance: why exactly these two personas, and nothing else

This milestone followed a source-grounding review of Mini ECHO's original
planning materials (`PROJECT.md` and the pre-MVP "Proxa ECHO" product
documents: a solution overview, a market analysis, a product strategy
document, a platform functionality specification, and an app walkthrough
deck) before any persona was chosen, specifically to avoid inventing
product scope. The review is preserved here because it is the actual
justification for this spec's boundaries, not just process history.

**What is explicitly required, cited verbatim:** the market analysis
document's Tier 1 ("table stakes") feature list states, under "Realistic
AI Avatars": *"Specialty Controls: Configurable by HCP specialty (Cardio,
Onco) and role."* This is the specific requirement this milestone
satisfies — Cardiology and Oncology are the two specialties the
requirement text itself names as examples. No other specialty or role type
is named in this sentence.

**What is only a UI mockup example, not a requirement:** the "Proxa Echo
Overview" walkthrough deck shows a "Select your medical professional"
screen with example cards including "Dr. Gemma Casey, Director of
Orthopaedology" and "Norah Jones, Patient Experience Manager." These are
screenshots of a hypothetical UI, not requirement text. Orthopedics is not
named in the Tier 1 specialty-control requirement, and "Patient Experience
Manager" describes a non-clinician role that would require inventing a new
`category` taxonomy value — Mini ECHO's `category` field (`doctor` today)
is itself an invention of the prior Persona Library milestone, not
something the source documents define at all, so extending it without an
explicit requirement forcing that extension would be scope creep. Both
were considered and explicitly rejected for this milestone on that basis.

**What was rejected as clearly out of scope even though it appears in the
source material:** nurse and pharmacist personas appear in the market
analysis document, but specifically under Tier 2 ("Differentiating
Features") as *"Multi-Stakeholder Scenarios: Practice with multiple HCPs
simultaneously (physician + nurse + pharmacist)"* — a materially different
and harder feature (one AI managing several simultaneous roleplay
participants in one scene) than adding a single new selectable persona.
Patient personas ("Digital Twin Patient... Patient journey conversations")
appear exactly once, explicitly labeled *"(future expansion)"*. Neither is
this milestone.

**Conclusion:** exactly two new personas, both citing the same Tier 1
requirement sentence, both using the existing `doctor` category — the
smallest change that satisfies an explicit, cited requirement without
introducing anything the source documents don't call for.

## Non-goals (explicitly out of scope for this iteration)

- Any persona beyond the two named above. No nurse, pharmacist, patient,
  or non-clinician/administrative persona of any kind.
- Any new `category` value. All personas in this milestone use the
  existing `category="doctor"` value Dr. Sarah Chen already uses.
- Simultaneous multi-stakeholder scenes (one AI representing multiple
  roleplay participants at once). Every Roleplay Session still has exactly
  one active persona, exactly as today.
- Simli face-switching or reconnect logic. Every persona — the existing
  one and both new ones — uses the same single existing verified Simli
  `face_id`. `avatar.connect()`'s behavior, timing, and the WebRTC
  connection lifecycle are completely untouched; this milestone adds zero
  lines to `avatar-src/doctor-avatar.js`, `app/avatar_simli.py`, or
  `app/avatar_provider.py`.
- Scoring, evaluation, compliance detection, certification, an Admin UI,
  an AI Tutor, LMS/CRM/Veeva integration, or any other feature from the
  full Proxa ECHO roadmap not already built in Mini ECHO. All confirmed
  either not started or explicitly future-expansion in the source
  documents' own language, per the provenance review above.
- Any UI redesign, markup change, or CSS change. The persona `<select>` in
  the Roleplay setup form already renders whatever `GET /personas` returns
  — three personas instead of one requires zero frontend code change, the
  same way this was already proven true when `voice_id`/`face_id` were
  added in the Persona Library milestone.
- A closed-set list of mood presets (the functionality document describes
  fixed mood options like "Combative/Argumentative," "Short on Time,"
  etc.). Mini ECHO's `mood` field stays free text, exactly as today — this
  is a real, separate gap from the source material, not something this
  milestone touches.
- Any change to `app/bedrock.py`, `app/tts.py`, `app/main.py`'s route
  signatures, `avatar-src/doctor-avatar.js`, `static/dist/avatar-bundle.js`,
  `static/stt-web-speech.js`, `static/index.html`, or `scripts/bedrock_check.py`.

## Data model — unchanged

No change to `app/personas/models.py`. The existing `Persona` fields
(`id, name, role_title, category, base_description, safety_framing,
voice_id, face_id`) are sufficient for both new personas exactly as they
are.

## The two new registry entries

Added to `app/personas/registry.py`'s existing `_PERSONAS` dict, alongside
Dr. Sarah Chen's untouched entry:

```python
"dr_marcus_reyes": Persona(
    id="dr_marcus_reyes",
    name="Dr. Marcus Reyes",
    role_title="Cardiologist",
    category="doctor",
    base_description=(
        "You are Dr. Marcus Reyes, an experienced cardiologist taking "
        "part in a training roleplay conversation. Speak precisely and "
        "efficiently, focus on clinical outcomes and mechanism of "
        "action, and respond the way a real cardiologist evaluating a "
        "new treatment would in a consultation."
    ),
    safety_framing=(
        "This is a roleplay for practice and learning purposes only, "
        "not real medical care: do not provide actual cardiology "
        "diagnoses or treatment advice, and if the user describes a "
        "real medical emergency, tell them to contact real emergency "
        "services immediately."
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
        "You are Dr. Priya Nair, an experienced oncologist taking part "
        "in a training roleplay conversation. Speak carefully and "
        "thoughtfully, focus on safety data and treatment evidence, "
        "and respond the way a real oncologist evaluating a new "
        "therapy would in a consultation."
    ),
    safety_framing=(
        "This is a roleplay for practice and learning purposes only, "
        "not real medical care: do not provide actual oncology "
        "diagnoses or treatment advice, and if the user describes a "
        "real medical emergency, tell them to contact real emergency "
        "services immediately."
    ),
    voice_id="SAz9YHcvj6GT2YYXdXww",
    face_id="f0ba4efe-7946-45de-9955-c04a04c367b9",
),
```

`voice_id` values (`IKne3meq5aSn9XLyUdCD` = "Charlie," `SAz9YHcvj6GT2YYXdXww`
= "River") were confirmed against the live ElevenLabs account by calling
`app.tts.list_voices()` during design — both are real, currently-available
premade voices distinct from Sarah's, not invented. `face_id` is copied
verbatim from the existing constant (`avatar_simli.FACE_ID`) — identical to
how Sarah's entry already references it, per this milestone's explicit
no-reconnect constraint.

## How this flows through the existing system — nothing new to design

Every mechanism this needs already exists and is already tested, because
it was built and proven generically in the Persona Library milestone:

- `GET /personas` already returns `list_personas()` mapped to
  `{id, name, role_title, category, voice_id, face_id}` for every entry —
  adding two entries changes the response length, not its shape or the
  route code.
- The Roleplay setup form's `populatePersonas()` and the submit handler's
  voice-defaulting logic already iterate over whatever `/personas` returns
  and already look up `selectedPersona.voice_id` generically — zero
  frontend code change.
- `/chat` already resolves `get_persona(session.persona_id)` and passes
  the result to `build_system_prompt(persona, session)`, which already
  composes `persona.base_description` + scenario/objective/mood/difficulty
  + `persona.safety_framing` for *any* persona — zero backend logic
  change.
- `/avatar/session` already accepts an optional `face_id` that every
  persona can supply; both new personas supply the same existing default,
  so the outbound Simli request is byte-identical to today's regardless of
  which of the three personas is active.

## Files added / changed

### Changed: `app/personas/registry.py`

Two new dict entries, as shown above. No change to `models.py`,
`__init__.py`, `get_persona`, or `list_personas`.

### Changed: `tests/test_personas.py`

New assertions mirroring the existing Sarah-entry test pattern:
`get_persona("dr_marcus_reyes")` and `get_persona("dr_priya_nair")` return
non-`None` `Persona` instances with the expected `role_title`, `category`,
`voice_id`, and distinguishing substrings in `base_description` /
`safety_framing`. `list_personas()`'s existing "includes Sarah" test is
extended to also assert both new personas are present, and that
`list_personas()` now returns exactly 3 entries.

### Changed: `tests/test_main.py`

`test_personas_returns_registered_personas`'s exact-equality assertion on
`GET /personas`'s response is extended from a 1-element list to a 3-element
list, adding the two new personas' expected JSON shape. No other test in
this file changes, since no other route's behavior changes.

### Unchanged

`app/main.py`, `app/bedrock.py`, `app/tts.py`, `app/avatar_simli.py`,
`app/avatar_provider.py`, `app/personas/models.py`, `app/personas/__init__.py`,
`static/index.html`, `avatar-src/doctor-avatar.js`,
`static/dist/avatar-bundle.js`, `static/stt-web-speech.js`,
`scripts/bedrock_check.py`. No `npm run build` needed. No new environment
variable, API key, or account.

## Backward compatibility

- Dr. Sarah Chen's registry entry is not modified in any way — same `id`,
  `name`, `role_title`, `category`, `base_description`, `safety_framing`,
  `voice_id`, `face_id` as today. Every existing test asserting her exact
  content keeps passing unmodified.
- A `/chat` request with no `session` never touches the registry at all —
  identical code path to today, unaffected by how many personas exist.
- `GET /personas`'s response shape (the six fields per persona) is
  unchanged; only the array's length grows from 1 to 3.
- `POST /avatar/session`'s behavior is unchanged for all three personas —
  none of them send a non-default `face_id`.

## Error handling

Unchanged from the existing patterns: unknown `persona_id` still 400s;
`GET /personas` still has no real failure mode (static in-process
registry) and stays without a try/except, matching today.

## Testing

Same conventions as the rest of the project (`pytest -v`, mocked at the
function boundary, no JS test infrastructure):

- `tests/test_personas.py`: extended per above.
- `tests/test_main.py`: extended per above.
- No change needed to `tests/test_bedrock.py` — `bedrock.py` is untouched,
  and its existing tests use a synthetic `TEST_PERSONA` fixture already
  independent of the real registry's contents.
- Manual browser QA (no JS test infra, per established project
  convention): the user starts a Roleplay Session with each of the three
  personas in turn and confirms the voice defaults correctly (and is still
  overridable), the Bedrock reply reflects that persona's specialty and
  safety framing, and Simli video, ElevenLabs audio, and Live Voice all
  continue to work exactly as before — i.e., that adding personas 2 and 3
  didn't regress persona 1's already-verified behavior.

## Consistency check against the original source documents, `PROJECT_CONTEXT.md`, and the current codebase

**Against the source documents:** both new personas' specialties
(Cardiology, Oncology) are the literal examples named in the market
analysis document's Tier 1 "Specialty Controls" requirement — the only
citation this spec relies on. No persona, category, or feature outside
that citation and the existing, already-built Persona Library mechanism
is introduced. Nurse, pharmacist, patient, and non-clinician personas
were explicitly considered during design and rejected with cited reasons
(see Provenance section above), matching the user's explicit exclusion
list.

**Against `PROJECT_CONTEXT.md`:** the "Persona registry" section already
documents the registry as accessed only through `get_persona`/
`list_personas`, "Dr. Sarah Chen is still the only entry today,
structurally no different from any future persona" — this spec is exactly
the case that sentence anticipated: a structurally identical entry added
by data, not by mechanism change. No other section of `PROJECT_CONTEXT.md`
describes any behavior this spec would contradict. `PROJECT_CONTEXT.md`
itself will need a small update once this is implemented and verified
(the persona count in "Features currently working" and the "Next planned
feature" section) — that update happens as part of implementing this
spec, per this project's standing rule, not before.

**Against the current codebase:** verified during design (not assumed)
that `category` is read in exactly two places in the entire codebase —
written once in `registry.py`, read once in `main.py` to build the
`/personas` JSON response — and asserted in one test. Nothing branches on
its value anywhere, confirming that even though this spec doesn't
introduce a new category value, doing so *would* have been technically
safe; the decision not to was about not inventing unrequired product
taxonomy, not about avoiding a technical risk. Both proposed `voice_id`
values were confirmed live against the ElevenLabs account this project
actually uses, not invented or assumed from documentation. The shared
`face_id` was copied verbatim from `avatar_simli.FACE_ID`, the same
constant Sarah's entry already references.

No contradiction, unsupported assumption, or scope creep was found in
this spec against any of the three sources checked.
