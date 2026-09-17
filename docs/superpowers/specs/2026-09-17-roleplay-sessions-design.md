# Roleplay Sessions — Design Spec

Status: approved design, not yet implemented.
Extends the architecture documented in `PROJECT_CONTEXT.md`. Read that file
first for the system this plugs into, and
`docs/superpowers/specs/2026-09-17-live-voice-conversation-design.md` for
the Live Voice feature this must not disturb.

## Goal

Move Mini ECHO from "one fixed persona (Dr. Sarah Chen, GP)" toward the
full ECHO product's structured roleplay model, without building any of the
downstream features (scoring, compliance, documents, Admin) yet. A user
configures a roleplay — HCP persona, scenario, conversation objective,
persona mood/behavior, difficulty — and that configuration becomes system
context for the *existing* Bedrock conversation. Text Chat and Live Voice
must both continue to use the same roleplay session, since they already
share one conversation pipeline (`sendToSarah`).

Sarah is the first demo persona, not a special case: nothing in this
design may be Sarah-specific at the architecture level.

## Non-goals (explicitly out of scope for this iteration)

- Scoring or evaluating a roleplay against its objective.
- Compliance detection (e.g., flagging off-label claims).
- An Admin UI or API for managing personas/scenarios.
- Document or RAG ingestion (e.g., product literature grounding a persona).
- Any backend persistence of roleplay sessions or transcripts. The backend
  stays stateless, per this project's standing architectural decision — a
  roleplay session lives exactly where the conversation array already
  lives: in the browser, for the duration of one page load.
- Any change to how Text Chat, Live Voice, ElevenLabs TTS, Simli, or the
  avatar's five real states work. This spec is additive to `/chat`'s
  request contract and to the system prompt Bedrock receives — nothing
  about the existing call paths is required to change for old behavior to
  keep working.
- A library of preset scenarios/objectives/moods. For this MVP those three
  fields are free text the user types per session; only `persona` (a
  registry) and `difficulty` (a fixed enum) are structured pickers. A
  preset library is exactly the kind of thing Admin would manage later.

## Decision: session config is client-held, sent per request

The roleplay session (persona + scenario + objective + mood + difficulty)
is held in browser state exactly like the existing `conversation` array —
not persisted server-side, not given a session ID today. It is sent
alongside `messages` on every `/chat` call, and the backend builds the
system prompt fresh from it on each request.

This was chosen over two alternatives:

- **Embedding the config as a synthetic message** in the `messages` array
  (no `/chat` schema change at all) was rejected: it mixes a structured,
  machine-inspectable configuration with free-form conversation turns,
  making it harder for a future scoring/compliance pass to read `objective`
  or `difficulty` as data rather than parse it back out of prose. It also
  doesn't match how the current `SYSTEM_PROMPT` already carries persona
  instructions — the natural evolution is to make that computation dynamic,
  not to relocate persona data into chat history.
- **A server-side session store** (`POST /sessions` returning a session ID,
  looked up on later `/chat` calls) was rejected for *this* milestone: it
  directly reverses "backend stays stateless... no database, no
  server-side session store, ever" (`PROJECT_CONTEXT.md`, Architectural
  Decisions) — a bigger change than this milestone asks for, and exactly
  the kind of persistence that should arrive together with the feature that
  actually needs it (reviewing past sessions, which belongs to a future
  scoring/Admin milestone, not this one). Giving the session a clean typed
  shape now, as described below, is what makes that later move a change of
  *where* the object lives, not *what* it is.

The critical property this decision buys: **`session` is optional on
`/chat`.** Omit it, and the backend falls back to today's exact hardcoded
Sarah/GP prompt, byte-identical to current behavior. Live Voice and Text
Chat's existing call path through `sendToSarah` is not required to change
for old behavior to keep working — only a browser that has actually
started a roleplay sends a `session`.

## Data model

Two deliberately separate concepts, so a future persona library (Admin)
can evolve independently of how a session is shaped:

**Persona** — a reusable character definition, not a session-specific
value:
```python
@dataclass(frozen=True)
class Persona:
    id: str                 # e.g. "dr_sarah_chen" — stable key, used in requests
    name: str                # "Dr. Sarah Chen"
    role_title: str          # "General Practitioner"
    base_description: str    # persona voice/manner, independent of any one scenario
    safety_framing: str      # domain-appropriate disclaimer text (medical, sales, etc.)
```
`safety_framing` lives on the persona, not globally, because a future
non-medical HCP persona (e.g., a hospital pharmacist in a formulary
negotiation) needs different disclaimer language than a GP consultation —
hardcoding one global disclaimer would be exactly the kind of
Sarah-specific architecture this spec must avoid.

**Roleplay session** — one instantiation, held client-side:
```python
class RoleplaySessionRequest(BaseModel):  # pydantic, in app/main.py
    persona_id: str
    scenario: str
    objective: str
    mood: str
    difficulty: Literal["easy", "medium", "hard"]
```

`difficulty` is a closed 3-value enum (not free text) because it needs to
map to a specific, testable prompt-behavior instruction (see "System
prompt composition" below) — an open string can't be reasoned about the
same way by a future scoring pass either.

## How context reaches the existing Bedrock conversation

`app/bedrock.py`'s hardcoded `SYSTEM_PROMPT` module constant becomes a
function:

```python
def build_system_prompt(persona: Persona | None, session: dict | None) -> str:
    if persona is None or session is None:
        return DEFAULT_SYSTEM_PROMPT  # today's exact hardcoded Sarah/GP text, byte-identical
    return (
        f"{persona.base_description}\n\n"
        f"Scenario: {session['scenario']}\n"
        f"Conversation objective: {session['objective']}\n"
        f"Persona mood/behavior for this conversation: {session['mood']}\n"
        f"Difficulty: {DIFFICULTY_INSTRUCTIONS[session['difficulty']]}\n\n"
        f"{persona.safety_framing}"
    )
```

`DEFAULT_SYSTEM_PROMPT` is today's existing `SYSTEM_PROMPT` string, moved
verbatim, unchanged — this is what guarantees zero behavior change for any
caller that doesn't supply a persona/session. `DIFFICULTY_INSTRUCTIONS` is a
small fixed dict (`easy`/`medium`/`hard` → one sentence each shaping how
receptive or resistant the persona should be) — a prompt-engineering detail
tunable later without changing the data model.

`get_reply(messages, persona=None, session=None)` passes both through to
`build_request_body`, which calls `build_system_prompt` instead of
referencing the module constant directly. `build_request_body` and
`build_system_prompt` are both pure functions, tested the same
network-free way `build_request_body`/`extract_reply_text` already are.

`app/main.py`'s `/chat` route: `ChatRequest` gains an optional
`session: RoleplaySessionRequest | None = None` field. When present, the
route looks up `PERSONAS.get(request.session.persona_id)` (from the new
`app/personas.py` registry) and passes both persona and session dict to
`get_reply`. An unknown `persona_id` is a 400 (client error — the frontend
population from `/personas` should make this unreachable in practice, but
the route validates rather than trusting it silently).

A new `GET /personas` route returns `[{"id", "name", "role_title"}, ...]`
for every registered persona — same shape and same mocked-boundary testing
pattern as the existing `GET /voices` route.

## Files added / changed

### New: `app/personas.py`

The `Persona` dataclass and a `PERSONAS: dict[str, Persona]` registry.
Sarah is the only entry for this milestone, defined with exactly the
persona-voice text currently embedded in `SYSTEM_PROMPT`, split into
`base_description` (the warm-GP framing) and `safety_framing` (the
roleplay/emergency disclaimer). Structurally, Sarah is in no way different
from any future persona — adding one later is adding one dict entry, not
touching the mechanism.

### Changed: `app/bedrock.py`

- `SYSTEM_PROMPT` renamed `DEFAULT_SYSTEM_PROMPT`, value unchanged.
- New `DIFFICULTY_INSTRUCTIONS` dict and `build_system_prompt(persona, session)`
  function, both pure and unit-testable.
- `build_request_body(messages, persona=None, session=None)` calls
  `build_system_prompt` instead of referencing a constant.
- `get_reply(messages, persona=None, session=None)` forwards both through.

### Changed: `app/main.py`

- New `RoleplaySessionRequest` pydantic model (shape above).
- `ChatRequest` gains `session: RoleplaySessionRequest | None = None`.
- `/chat` route resolves `persona_id` → `Persona` via `PERSONAS`, 400s on
  an unknown id, and calls `get_reply(messages, persona=persona,
  session=request.session.model_dump())` — converting the pydantic model
  to a plain dict before it crosses into `app/bedrock.py`, matching how
  `request.messages` (a list of `ChatMessage` models) is already converted
  to plain dicts before `get_reply` sees them today. `app/bedrock.py` stays
  pydantic-free, same as it is now. Wrapped in the same
  `try/except Exception -> 503` pattern already used for every other
  route — a Bedrock failure still never leaks upstream exception text,
  unchanged from today.
- New `GET /personas` route, same shape/pattern as `GET /voices`.

### Changed: `static/index.html`

- New setup UI: a panel with persona `<select>` (populated from
  `GET /personas`, mirroring how `#voice-select` is already populated from
  `GET /voices`), scenario/objective/mood text inputs, and a difficulty
  `<select>` (Easy/Medium/Hard). Pre-filled with today's defaults (Sarah,
  empty scenario/objective, neutral mood, medium difficulty) so clicking
  "Start Roleplay" with no changes reproduces current behavior exactly.
- A `roleplaySession` JS object (or `null` before a roleplay starts) held
  in the same page-level scope as `conversation`, `voices`, etc.
- `sendToSarah(message)` (already the single shared pipeline both Text
  Chat and Live Voice call) includes `session: roleplaySession` in its
  `/chat` POST body when non-null — this is the one line where Live
  Voice's and Text Chat's already-shared code path picks up roleplay
  context; neither mode needs its own separate wiring.
- "Start Roleplay" collapses the setup panel, updates the avatar panel's
  `.persona-name`/`.persona-role` text to the selected persona (currently
  hardcoded markup), and enables the composer.
- "New Roleplay" resets both `roleplaySession` (to `null`) and
  `conversation` (to `[]`) together and re-shows the setup panel — a
  persona swap mid-transcript wouldn't be a coherent conversation, so a new
  roleplay is deliberately a fresh conversation, not a context-only swap.

### Unchanged

`app/avatar_simli.py`, `app/avatar_provider.py`, `app/tts.py`,
`avatar-src/doctor-avatar.js`, `static/dist/avatar-bundle.js`,
`static/stt-web-speech.js`, `scripts/bedrock_check.py`. No `npm run build`
needed — nothing under `avatar-src/` changes. No new environment variable,
API key, or account.

## Error handling

- **Unknown `persona_id` in a `/chat` request:** 400 with a generic message
  (mirrors the pattern of not leaking internals, same spirit as the
  existing 503s, but a 400 since this is a client-supplied bad value, not
  an upstream failure).
- **`session` omitted entirely:** falls back to `DEFAULT_SYSTEM_PROMPT`,
  today's exact behavior — not an error at all, the compatibility path.
- **`GET /personas` failure:** there is no real failure mode here (it's a
  static in-process dict, not a network call) — the route can't
  meaningfully 503 the way `/voices`/`/tts`/`/avatar/session` do, so it
  does not need the same try/except wrapper those routes use for genuine
  upstream calls.
- **Frontend: persona list fails to load:** same defensive pattern already
  used for `populateVoices()` (empty list, logged, non-fatal) — the setup
  panel's persona `<select>` would simply have no options; not a new
  pattern to design, an existing one to reuse.

## Testing

Same conventions as the rest of the project:
- `build_system_prompt` and the updated `build_request_body` get pure,
  network-free unit tests in `tests/test_bedrock.py` — one case with
  `persona=None, session=None` asserting the output equals
  `DEFAULT_SYSTEM_PROMPT` byte-for-byte (the compatibility guarantee, made
  literally testable), and one case per difficulty level with a persona
  supplied, asserting the composed prompt contains the persona's
  description, the scenario/objective/mood text, and the right difficulty
  instruction.
- `tests/test_main.py` gets a case for `/chat` with a `session` field
  (mocked `get_reply`, asserting it was called with the resolved
  `Persona` and session dict), a case for `/chat` with an unknown
  `persona_id` (expect 400), and a case for `GET /personas` (asserting the
  shape and that Sarah is present) — following the existing
  mocked-at-the-function-boundary pattern throughout `test_main.py`.
- No JS test infrastructure exists or is being added, per established
  project convention. The setup panel, persona-driven `.persona-name`/
  `.persona-role` update, and the "New Roleplay" reset are UI/JS changes
  verifiable only by the user in a real browser — the implementation plan
  will include a manual QA script, same as Live Voice's.

## How this supports scoring, compliance, documents, and Admin later

- **Scoring**: a roleplay's `objective` and `difficulty` are already
  structured fields on `session`, not buried in prose. A future scoring
  pass is a new function/endpoint taking the same `messages` + `session`
  shape `/chat` already receives — no rework of how sessions flow through
  the app, just a new consumer of data that already exists in the right
  shape.
- **Compliance detection**: same reasoning — a persona's `safety_framing`
  and a session's `scenario` are already explicit fields a compliance pass
  can read directly, rather than needing to be extracted from a hardcoded
  prompt string the way `SYSTEM_PROMPT` works today.
- **Documents/RAG**: grounding a persona or scenario in reference material
  becomes an additional parameter to `build_system_prompt` (e.g., a
  retrieved-context string appended before the persona's `base_description`)
  — additive to a function that's already dynamic, not a rewrite of a
  hardcoded constant.
- **Admin**: `PERSONAS` is a hardcoded Python dict today. Admin managing
  personas (and, later, scenario/objective presets) means swapping this
  one module's data source for a database-backed store — the `Persona`
  shape, the `GET /personas` contract, and how `/chat` consumes
  `persona_id` all stay the same. This mirrors the exact swap this
  codebase already proved works: the Polly→ElevenLabs TTS swap
  (`PROJECT_CONTEXT.md`, Architectural Decisions) touched only
  `app/tts.py`.
- **Session persistence** (needed eventually by scoring/Admin/compliance
  to review past roleplays): today's `session` is client-held and
  ephemeral, same as `conversation`. Because `RoleplaySessionRequest` is
  already a fully-typed shape, persisting `{session, messages}` later is a
  new endpoint (e.g. `POST /sessions` called when a roleplay ends) writing
  an object that already has the right shape — not a redesign of this
  feature.
