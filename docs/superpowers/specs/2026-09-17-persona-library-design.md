# Persona Library — Design Spec

Status: approved design, not yet implemented.
Extends the architecture documented in `PROJECT_CONTEXT.md`. Read that file
first for the system this plugs into, and
`docs/superpowers/specs/2026-09-17-roleplay-sessions-design.md` for the
Persona/RoleplaySessionRequest concepts this milestone builds on directly —
this is not a competing persona system, it is that same `Persona` concept
turned into a real registry with the fields a library of personas actually
needs.

## Goal

Move Mini ECHO's persona concept from "one entry in a dict, added for
Roleplay Sessions" to a scalable Persona Library: a registry that can hold
many personas (doctors, patients, nurses, pharmacists, and other
healthcare-related roles), each with its own voice and (eventually) its own
Simli face, accessed through a stable function-based API that does not need
to change shape when personas later move to persistent storage or get an
Admin UI.

Dr. Sarah Chen must continue to work exactly as she does today, in every
mode (Text Chat, Live Voice, inside or outside a Roleplay Session). Nothing
in this design is Sarah-specific at the architecture level — she is simply
the first fully-populated entry in the library.

## Non-goals (explicitly out of scope for this iteration)

- `default_mood` or `tags`/multi-category fields on `Persona`. The model
  stays minimal: only fields with a concrete consumer in this milestone are
  added. These can be added later when a real feature (Admin, filtering,
  scenario matching, persona-specific mood defaults) actually needs them —
  adding them now would be exactly the kind of speculative field this
  project's guidelines warn against.
- Simli reconnect-on-persona-change and multi-face support. Every persona's
  `face_id` points at the same existing, verified Simli "Doctor" face for
  now. `POST /avatar/session` is extended to accept a `face_id` at the
  API/data-contract level, but the frontend does not yet send a
  persona-specific one, and the Simli connection lifecycle (when `connect()`
  fires, how long a session lives) does not change at all.
- Applying persona selection outside Roleplay Sessions. Plain Text Chat and
  Live Voice with no active roleplay keep using `DEFAULT_SYSTEM_PROMPT` and
  the default Simli face, byte-identical to today — persona selection stays
  scoped to the existing Roleplay setup form.
- Any UI redesign. The persona `<select>` in the Roleplay setup form and the
  voice `<select>` already exist; this milestone changes what data feeds
  them and one default-setting behavior, not their layout or markup
  structure.
- An Admin UI or API for managing personas, and any database. The registry
  stays in-memory, in Python, exactly as `PERSONAS` is today — just accessed
  through functions instead of a raw dict, which is what makes the later
  move to a database not require touching any caller.
- Any change to how Bedrock's `build_system_prompt`/`build_request_body`,
  ElevenLabs' `synthesize_speech`/`list_voices`, Simli's WebRTC/audio-unlock
  flow, or Live Voice's turn-taking loop work. This spec only changes where
  persona data comes from and adds one new optional field to one existing
  endpoint's request body.

## Current state (what exists before this milestone)

- `app/personas.py`: a `Persona` dataclass (`id`, `name`, `role_title`,
  `base_description`, `safety_framing`) and a `PERSONAS: dict[str, Persona]`
  with one entry, `dr_sarah_chen`. Callers (`app/main.py`) read it directly
  as `PERSONAS.get(...)` / `PERSONAS.values()`.
- `POST /avatar/session` takes no request body at all.
  `SimliAvatarProvider.create_session()` always POSTs the same hardcoded
  module-level `FACE_ID`. The frontend's `avatar.connect()` call fires once,
  automatically, at page load — before the user has seen or filled in the
  Roleplay setup form, i.e. before any persona is known.
- `GET /voices` / the `#voice-select` dropdown is a global, user-chosen
  ElevenLabs voice, persisted in `localStorage`, completely independent of
  which persona (if any) is active. `app/tts.py`'s `DEFAULT_VOICE_ID` is
  ElevenLabs' "Sarah" voice, chosen only because the name matched.
- `bedrock.py`'s `DEFAULT_SYSTEM_PROMPT` is the fallback used whenever
  `persona is None or session is None` — i.e. whenever no Roleplay Session
  is active. This is today's only persona-agnostic path and must stay
  reachable unchanged.

**Identified architectural risk (not fixed this milestone):** because
`avatar.connect()` fires at page load, before persona selection, Simli's
face cannot follow the selected persona without either delaying that call
or adding reconnect logic — neither exists today, and both would touch the
exact WebRTC/audio-unlock flow this project's guidelines protect. Flagged
here for whoever picks up the future multi-face milestone.

**Identified naming debt (not fixed this milestone):** the frontend class
`DoctorAvatar` and the function `sendToSarah()` are named after the first
persona but contain no persona-specific logic — cosmetic, not a functional
blocker, left alone per this project's surgical-changes rule.

## Data model

```python
@dataclass(frozen=True)
class Persona:
    id: str                 # stable snake_case key, e.g. "dr_sarah_chen"
    name: str                # display name, e.g. "Dr. Sarah Chen"
    role_title: str          # e.g. "General Practitioner"
    category: str            # e.g. "doctor", "patient", "nurse", "pharmacist"
    base_description: str    # behavioral/personality instructions (Bedrock system-prompt text) — same content/purpose as today's field, unchanged
    safety_framing: str      # domain-appropriate disclaimer text — unchanged from today
    voice_id: str            # ElevenLabs voice ID — new, has a concrete consumer this milestone (roleplay-start default)
    face_id: str             # Simli face ID — new, modeled and passed through the API; every persona currently shares the one verified face
```

No `description`/bio field is added separately from `base_description`:
nothing in the current UI displays a persona bio anywhere, so splitting
"background" from "behavioral instructions" now would be a field with no
reader. Add it later, the moment something (an Admin Dashboard, a persona
picker with bios) actually reads it.

## Registry: function-based access, not a raw dict

New package `app/personas/` replaces the single file `app/personas.py`:

- **`app/personas/models.py`** — the `Persona` dataclass above.
- **`app/personas/registry.py`** — the same in-memory dict-literal pattern
  as today's `PERSONAS`, but private to this module, plus exactly two
  public functions:
  ```python
  def get_persona(persona_id: str) -> Persona | None: ...
  def list_personas() -> list[Persona]: ...
  ```

Every caller (`app/main.py`) uses only these two functions — never the
underlying dict. This is the one seam that matters for future persistence:
when personas move to a database, only `registry.py`'s internals change to
issue a query instead of a dict lookup; `get_persona`/`list_personas` keep
their exact signatures, so nothing calling them needs to change. It is the
cheapest thing that is still genuinely migration-ready — no ORM, no
repository interfaces, no config files, just two named functions instead of
a dict callers reached into directly.

Dr. Sarah Chen's entry moves into `registry.py` with identical
`base_description`/`safety_framing` content to today, plus:
- `category="doctor"`
- `voice_id="EXAVITQu4vr4xnSDxMaL"` (today's `tts.DEFAULT_VOICE_ID` value)
- `face_id="f0ba4efe-7946-45de-9955-c04a04c367b9"` (today's
  `avatar_simli.FACE_ID` value)

## How persona data flows: UI → Roleplay Session → Bedrock → ElevenLabs → Simli

1. **Persona list load** (page load, same trigger as today):
   `populatePersonas()` calls `GET /personas`, which now returns
   `[{id, name, role_title, category, voice_id, face_id}, ...]` — additive
   fields; the existing rendering
   (`persona.name + ' — ' + persona.role_title`) is unchanged.
2. **Roleplay start** (`roleplay-setup` submit, unchanged trigger):
   - `roleplaySession = {persona_id, scenario, objective, mood, difficulty}`
     — **unchanged**, identical shape to today.
   - **New:** if the selected persona's `voice_id` is present in the
     already-fetched `voices` list, set `voiceSelect.value` to it and
     persist to `localStorage` the same way manual selection already does.
     This is the persona-default-with-override behavior: after this line
     runs, the existing `voiceSelect` change handler and every later
     `/tts` call are untouched — they already just read whatever
     `voiceSelect.value` currently is, so the user can still pick a
     different voice afterward and it's respected.
3. **Chat turn** (unchanged): `sendToSarah()` → `POST /chat` with `session`
   → `main.py` resolves `get_persona(session.persona_id)` → passes the
   `Persona` and session dict to `bedrock.get_reply` → `build_system_prompt`
   composes the prompt exactly as it does today. No changes to
   `build_system_prompt`, `build_request_body`, or `get_reply`.
4. **Speech**: `avatar.speak(replyText, voiceSelect.value)` → `POST /tts`
   with that `voice_id`. `voice_id` was already a per-call parameter to
   `/tts`, so the persona's voice reaching ElevenLabs required zero backend
   changes — only the frontend default-setting in step 2.
5. **Simli face**: `POST /avatar/session` gains an optional `face_id` field
   on its request body, defaulting to today's constant
   (`avatar_simli.FACE_ID`) when omitted. The frontend's `avatar.connect()`
   call still fires once at page load, before any persona is selected, and
   still sends no `face_id` — so this call is byte-for-byte identical to
   today's request. The plumbing exists end-to-end and is tested, but no
   caller yet exercises a non-default `face_id`; that is the
   explicitly-deferred multi-face milestone described above.

## Files added / changed

### New: `app/personas/models.py`, `app/personas/registry.py`

As described above. `app/personas.py` (the old single file) is deleted.

### Changed: `app/main.py`

- `from app.personas import PERSONAS` → `from app.personas import get_persona, list_personas`.
- `/chat` route: `PERSONAS.get(request.session.persona_id)` →
  `get_persona(request.session.persona_id)`. Same `None` check, same 400-on-
  unknown-id behavior, unchanged.
- `/personas` route: `PERSONAS.values()` → `list_personas()`; response gains
  `category`, `voice_id`, `face_id` alongside the existing `id`/`name`/
  `role_title` (additive fields).
- `/avatar/session` route: gains a request body model with an optional
  `face_id: str | None = None`, passed through to
  `avatar_provider.create_session(face_id)`.

### Changed: `app/avatar_provider.py`

`AvatarProvider.create_session()` protocol gains an optional `face_id: str
| None = None` parameter.

### Changed: `app/avatar_simli.py`

`SimliAvatarProvider.create_session(face_id: str | None = None)`: POSTs
`face_id or FACE_ID` (today's constant stays the default) as `faceId`.
Every other field of the Simli request body (`handleSilence`,
`maxSessionLength`, `maxIdleTime`, header) is unchanged.

### Changed: `static/index.html` (inline script only)

One addition inside the existing `roleplay-setup` submit handler: set
`voiceSelect.value` to the selected persona's `voice_id` (when present
among fetched voices) and persist it, as described in step 2 above. No
markup change, no other script-block change.

### Changed: `tests/test_personas.py`

Import path updated to the new package. Existing assertions on Sarah's
`id`/`name`/`role_title`/`base_description`/`safety_framing` content stay
word-for-word; new assertions added for `category`, `voice_id`, `face_id`
being present and correct on the Sarah entry.

### Changed: `tests/test_main.py`

New/extended cases: `/personas` response includes `category`/`voice_id`/
`face_id`; `/avatar/session` with no `face_id` calls
`create_session()`/the provider with the default (proving today's page-load
call path is unaffected); `/avatar/session` with a `face_id` passes it
through. Existing cases (unknown `persona_id` → 400, session omitted →
`DEFAULT_SYSTEM_PROMPT` fallback, no upstream exception text leaked) are
unchanged and must keep passing.

### Unchanged

`app/bedrock.py` (no changes at all — `build_system_prompt`,
`build_request_body`, `get_reply`, `DEFAULT_SYSTEM_PROMPT`,
`DIFFICULTY_INSTRUCTIONS` are all untouched), `app/tts.py`,
`avatar-src/doctor-avatar.js` (source untouched, so **no `npm run build`
required**), `static/dist/avatar-bundle.js`, `static/stt-web-speech.js`,
`scripts/bedrock_check.py`, all CSS and markup in `static/index.html`. No
new environment variable, API key, or account.

## Backward compatibility

- A `/chat` request with no `session` field never calls `get_persona` or
  touches the registry at all — identical code path to today, which is why
  plain Text Chat and Live Voice outside any roleplay are unaffected by
  this milestone regardless of how many personas the library grows to.
- A `/avatar/session` request with no `face_id` produces the exact same
  outbound Simli request body as today (`FACE_ID` constant, unchanged).
- `GET /personas`'s new fields (`category`, `voice_id`, `face_id`) are
  additive; the current frontend code only reads `id`/`name`/`role_title`
  and continues to do so unaffected.
- Dr. Sarah Chen's `base_description`/`safety_framing`/prompt-composition
  behavior is moved, not rewritten — the two existing persona tests'
  assertions on that content stay word-for-word.
- `bedrock.py` is not modified at all in this milestone, which is itself
  the strongest backward-compatibility guarantee for the Bedrock call path.

## Error handling

Unchanged from the existing patterns documented in the Roleplay Sessions
spec: unknown `persona_id` → 400 (client error, not upstream failure);
`/avatar/session` upstream failures still wrapped in the existing
`try/except Exception -> 503` with no leaked exception text; `GET
/personas` still has no real failure mode (static in-process registry, not
a network call) and stays without a try/except, matching today.

## Testing

Same conventions as the rest of the project (`pytest -v`, mocked at the
function boundary, no JS test infrastructure):

- `tests/test_personas.py`: updated import, extended field assertions (see
  above).
- `tests/test_main.py`: extended `/personas` and `/avatar/session` cases
  (see above); every existing test must keep passing unmodified in
  assertion content.
- No changes needed to `tests/test_bedrock.py` — `bedrock.py` is untouched.
- The one frontend behavior change (voice dropdown defaulting to the
  persona's `voice_id` on roleplay start, still overridable) has no JS test
  infra and is verifiable only by the user in a real browser — the
  implementation plan should include a manual QA step for it, following the
  same pattern as Live Voice's and Roleplay Sessions' manual verification.

## How this supports an Admin Dashboard and persistent database later

- Because `main.py` only ever calls `get_persona`/`list_personas()`, moving
  the registry to a database means rewriting the inside of
  `app/personas/registry.py` (a SQL query instead of a dict lookup) — no
  caller changes. This mirrors the exact swap this codebase already proved
  works: the Polly→ElevenLabs TTS swap touched only `app/tts.py`
  (`PROJECT_CONTEXT.md`, Architectural Decisions).
- An Admin Dashboard for managing personas becomes new routes
  (`POST`/`PUT`/`DELETE /admin/personas`) calling the same registry
  module; the `Persona` dataclass is already the right shape to persist as
  a database row.
- Fields deliberately not added this milestone (`default_mood`, `tags`,
  scoring/compliance metadata) can be added to `Persona` incrementally, one
  at a time, exactly when a real feature needs them — the dataclass and the
  two-function registry API don't need to change shape to accommodate that
  growth, only grow a field.
- The deferred Simli multi-face milestone (reconnect-on-persona-change) can
  build directly on the `face_id` field and the `POST /avatar/session`
  contract already in place after this milestone — it only needs to add the
  frontend logic to call `connect()` with a real per-persona `face_id` and
  handle reconnection safely, not redesign the data model or the endpoint.

## Consistency check against `PROJECT_CONTEXT.md` and the verified baseline

- Matches "Backend stays stateless": the registry is in-memory Python data,
  no new persistence, no session store change.
- Matches "Provider abstraction for the avatar": `avatar_provider.py`'s
  `Protocol` is extended (one optional parameter), not replaced;
  `avatar_simli.py` remains the only Simli-specific file.
- Matches "TTS is isolated from the avatar provider": `app/tts.py` is not
  touched at all; the persona-voice default is set in the frontend, which
  already owns `voiceSelect.value` and already calls `/tts` with whatever
  value it holds.
- Matches "All third-party API keys stay server-side": no change to key
  handling; `face_id` and `voice_id` are non-secret identifiers already
  handled the same way `FACE_ID`/`DEFAULT_VOICE_ID` are today.
- Matches "The frontend build step is scoped as narrowly as possible":
  `avatar-src/doctor-avatar.js` is not touched, so no `npm run build` is
  required for this milestone.
- Matches the "Things that MUST NOT be broken" list in full: the DOM
  contract, the five `DoctorAvatar` states, the `position: absolute` +
  inline-style-display fixes, the audio-unlock listener, `"livekit"`
  transport mode, the stateless backend, `scripts/bedrock_check.py`'s
  frozen divergence, and API keys never reaching the frontend are all
  either explicitly unchanged or not touched by any file in this spec's
  change list.
- Once implemented and verified, `PROJECT_CONTEXT.md` will need its
  "Roleplay Sessions" section (persona registry description) and
  "Environment variables"/architecture sections updated to describe the
  `app/personas/` package and the new `/avatar/session` field, per this
  project's standing rule to keep that file in sync with real
  architecture — that update happens as part of implementing this spec,
  not before.
