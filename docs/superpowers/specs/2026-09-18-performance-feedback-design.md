# Performance Feedback / Scoring — Design Spec

Status: approved design, not yet implemented.
Extends the architecture documented in `PROJECT_CONTEXT.md`. Read that file
first for the system this plugs into, and
`docs/superpowers/specs/2026-09-17-roleplay-sessions-design.md` for the
`RoleplaySessionRequest`/conversation model this reuses unmodified.

## Goal

Give the user a qualitative, source-grounded reflection on a completed
Roleplay Session — an overall summary, a breakdown across a small set of
evaluation dimensions, and specific improvement recommendations — generated
by one additional Bedrock call over the conversation already held in the
browser. No new persistence, no numeric scoring system, no certification
logic, no compliance-monitoring infrastructure: this is the smallest slice
of the "Automated Performance Scoring" capability that the original Mini
ECHO source documents actually specify, built the same way every prior
milestone was — as a new, isolated code path that cannot regress anything
already verified.

## Source mapping — what's included, why, and what's explicitly excluded

Four documents in the original Mini ECHO/Proxa ECHO planning material
describe this capability, and they do not agree with each other on exact
dimensions, scale, or format. This section is the actual justification for
every choice below — cited, not asserted.

**Included dimensions (each requires 2+ independent source citations):**

| Dimension | Citation 1 | Citation 2 |
|---|---|---|
| Message accuracy | Strategy doc: *"Message accuracy and completeness"* | Market analysis doc: *"messaging accuracy"* |
| Objection handling | Strategy doc: *"Objection handling effectiveness"* | Market analysis doc: *"objection handling"* |
| Rapport building | Strategy doc: *"Active listening and rapport building"* | Market analysis doc: *"rapport building"* |
| Compliance adherence | Strategy doc: *"Compliance adherence"* (one of 5 scoring dimensions) | Functionality doc, slide 15: *"Compliance Score"* — cited only for the dimension's existence, not for its heavier slide-9-11 monitoring/audit apparatus, which is explicitly excluded below |

**Included as feedback format, not a scored dimension** (both citations
nearly verbatim identical, which is itself the strongest cross-source
agreement found anywhere in this review): *"Specific improvement
recommendations"* — Strategy doc and Market analysis doc, word for word.

**Included as a qualitative overall reflection**, per Strategy doc's
*"Overall score with dimensional breakdown"* and Market analysis doc's
*"Overall performance assessment"* — both sources establish that an
overall, whole-conversation reflection belongs alongside the per-dimension
breakdown. Neither source defines what "score" means numerically (see
below), so this is implemented as a qualitative summary, not a number.

**Explicitly excluded, and why (single-source or coupled to deferred
features — never invented, always a real citation that didn't clear the
bar):**
- Conversation structure and flow (Strategy doc only, no second source)
- Clinical fluency, closing (Market analysis doc only, no second source)
- Professionalism/"Language and Conduct," Talk Ratio, Total Messages
  (Echo Overview walkthrough's "Roleplay Scorecard" *screen mockup* only —
  a UI illustration, not requirement text, and internally inconsistent
  even within that one screen: two gauges use a 0–10 scale, one uses a raw
  count forced into a /10 display, and one uses a raw percentage)
- Pre-Call Goal Alignment, Persona Adaptability, Clinical Accuracy,
  AI-Derived Coaching Tips (Functionality doc slide 15 only — and this
  entire version of "scorecard" is explicitly coupled to a "Pre-Call Plan"
  feature (slide 14) that doesn't exist in Mini ECHO and is out of scope
  for this milestone per direct instruction)
- Any live, in-call compliance flagging (Echo Overview's "Roleplay Full
  Screen" screen shows a real-time "Compliance Violation" banner
  mid-conversation) — this requires streaming analysis tied to the
  compliance-monitoring/MLR/audit-trail apparatus (Functionality doc
  slides 9-11, explicitly labeled *"Major Required Feature"* for the full
  enterprise product) that this milestone does not build. Evaluation here
  happens once, after the conversation, not live.
- Exportable reports, progress tracking over time (Strategy doc,
  "Feedback Delivery") — both require persisting results across sessions.
  The same Strategy doc's own **"MVP Scope > Included in V1.0"** list goes
  further and names *"Session history and performance tracking"* as part
  of that product's V1.0 itself — so this is not a case of the sources
  being silent; they explicitly call for it. It's excluded here anyway,
  deliberately, because it would reverse Mini ECHO's own separate,
  standing stateless-backend decision — a project-level constraint that
  predates this milestone and is being kept intentionally smaller than
  even the source's own "V1.0," per your explicit instruction. Not built.

## Non-goals (explicitly out of scope for this iteration)

- Any numeric score, percentage, star rating, letter grade, weighting
  formula, or pass/fail threshold. No source document defines one for the
  scoring feature itself (a "Minimum score thresholds" concept exists only
  in the separate, already-deferred Certification feature). Where a source
  says "overall score" with no defined scale, this spec implements a
  qualitative summary instead — an explicit, documented substitution, not
  a silent one.
- Compliance monitoring, MLR review routing, audit trails, adverse-event
  detection, or any regulatory/enterprise compliance subsystem.
  "Compliance adherence" here is one plain-text field in a single
  end-of-conversation evaluation call — nothing live, nothing audited,
  nothing retained.
- Certification, credentialing, badges, or leaderboards.
- Pre-Call Plan Builder or anything that reads one (no such feature
  exists in Mini ECHO).
- Any persistence: no database, no session store, no history across page
  loads, no cross-session comparison. Evaluation reads the same in-memory
  `conversation` array `/chat` already reads, once, on demand, and returns
  a result that exists only in that response.
- An Admin UI, LMS/CRM integration, or manager dashboards.
- Any change to `app/bedrock.py`'s existing functions
  (`build_request_body`, `build_system_prompt`, `get_reply`,
  `extract_reply_text`), `app/tts.py`, `app/avatar_simli.py`,
  `app/avatar_provider.py`, `avatar-src/doctor-avatar.js`,
  `static/dist/avatar-bundle.js`, `static/stt-web-speech.js`, or
  `scripts/bedrock_check.py`.
- Any UI change beyond the one new trigger button and one new results
  panel described below. No redesign of existing markup, CSS, or the
  chat/avatar/roleplay-setup flow.

## Evaluation result schema — precise, final

```json
{
  "dimensions": {
    "message_accuracy": "string — qualitative assessment",
    "objection_handling": "string — qualitative assessment",
    "rapport_building": "string — qualitative assessment",
    "compliance_adherence": "string — qualitative assessment"
  },
  "overall_summary": "string — qualitative whole-conversation reflection",
  "improvement_recommendations": "string — specific, actionable suggestions"
}
```

All six fields are required, plain-text strings. No field is ever numeric,
a percentage, an enum, or a boolean. This is the smallest source-faithful
representation of "overall score with dimensional breakdown" + "specific
improvement recommendations" that doesn't invent a scale, a weighting
formula, or a label taxonomy the sources never specified — even a small
closed set of qualitative labels (e.g. "Strong/Adequate/Needs Improvement")
would be inventing a ranking system, which is exactly what was ruled out.

## Where this runs in the existing Roleplay Session lifecycle

At the end of an active Roleplay Session, on explicit user action — not
automatically, not mid-conversation, not on every reply. The sources
describe two different timings (a live in-call flag and a post-call
comprehensive review); the live version requires the explicitly-deferred
compliance-monitoring machinery, so this milestone implements only the
post-call version, triggered by a new button rather than any automatic
hook into the existing `sendToSarah` turn-taking flow.

## What existing data is reused — nothing new is captured

- The browser's existing `conversation` array — the exact same data
  `/chat` already sends on every call — is the transcript.
- The active `roleplaySession` object (`persona_id`, `scenario`,
  `objective`, `mood`, `difficulty`) is the same session context `/chat`
  already sends; it's passed to the new endpoint unchanged.
- `get_persona(session.persona_id)` — the same lookup `/chat` already
  performs — resolves the persona whose `base_description`/`role_title`
  frame what "compliance adherence" and "rapport" mean for that specialty.

No new frontend state, no new fields on `roleplaySession`, no new backend
storage.

## Architecture

### New file: `app/evaluation.py`

A new, small module — kept separate from `app/bedrock.py` on purpose, the
same way `app/tts.py` is separate from `app/bedrock.py`, so the existing
chat code path is never touched by this feature:

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
        # Models sometimes add a preamble before the fence (e.g. "Here's
        # the evaluation:\n```json\n{...}\n```), which the prefix-based
        # stripping above doesn't catch. Retry once against the substring
        # between the first "{" and the last "}" before giving up — this
        # only widens what's *recoverable*; genuinely malformed output
        # still raises ValueError exactly as before.
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

`_client` is a second, independent `boto3.client` instance constructed the
same way `app/bedrock.py`'s already is — not a shared/imported instance —
keeping the two modules fully independent, matching this project's
existing pattern of each AI-calling module owning its own client
(`app/bedrock.py` and `app/tts.py` each already do this; `app/tts.py`'s
client setup is even simpler, a bare `requests`-style call per request).
`MODEL_ID`/`REGION` are imported as constants, not duplicated as literal
strings, since they name the one real AWS model/region this project uses.

### Changed: `app/main.py`

One new request model and one new route, following the exact structure of
every existing route:

```python
class EvaluateRequest(BaseModel):
    messages: list[ChatMessage]
    session: RoleplaySessionRequest


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

`session` is **required** here (unlike `/chat`'s optional `session`) —
evaluation only makes sense for an active Roleplay Session, per the
approved scope; omitting it is a 422 from FastAPI's own request
validation, the same mechanism already used everywhere in this app. An
unknown `persona_id` is a 400, mirroring `/chat`'s existing identical
check verbatim. A Bedrock failure *or* a malformed/unparseable response —
both handled by the same `except Exception` — become the same generic
503, matching every other route's error-handling convention exactly.
`get_evaluation`'s `ValueError` from `extract_evaluation` and any real
`boto3`/network exception are indistinguishable to the client, on purpose,
consistent with how this project already treats every upstream failure.

`app/bedrock.py` gains **zero** changes — `MODEL_ID`/`REGION` are only
read, not modified, and `/chat`'s route, `get_reply`, `build_request_body`,
and `build_system_prompt` are untouched.

### Changed: `static/index.html`

The only frontend change in this milestone. Two new elements and one new
block of JS in the existing inline `<script>`:

**Markup additions** (inside the existing avatar panel, alongside the
existing `#new-roleplay-btn`):
```html
<button type="button" id="get-feedback-btn" hidden disabled>Get Feedback</button>
<div id="feedback-panel" style="display: none;">
  <h3>Performance Feedback</h3>
  <div id="feedback-content"></div>
  <button type="button" id="feedback-close-btn">Close</button>
</div>
```

**Behavior:**
- `#get-feedback-btn` is shown/hidden by the exact same condition as
  `#new-roleplay-btn` (both toggle together at roleplay start/"New
  Roleplay" reset) — no new visibility state to design, reusing the
  existing one.
- Additionally **disabled** whenever `conversation.length === 0` (nothing
  to evaluate yet) and whenever `isSending` is true (mirrors the existing
  guard `sendToSarah` already uses to prevent overlapping requests) — a
  small `updateFeedbackButtonState()` helper called wherever `conversation`
  already changes and wherever `isSending` already changes, not new
  independent state.
- On click: disable the button, set its text to "Evaluating…", `POST
  /evaluate` with `{ messages: conversation, session: roleplaySession }`
  (the exact same two values `sendToSarah` already has in scope — no new
  data assembly).
  - On success: render the four dimension strings, `overall_summary`, and
    `improvement_recommendations` as plain text into `#feedback-content`,
    then show `#feedback-panel` via `style.display = 'block'` (the same
    inline-style-toggle convention already load-bearing for `#chat`/
    `#chat-form`, not the `hidden` attribute).
  - On failure (non-200 response): render a single error line into
    `#feedback-content` (e.g. "Something went wrong generating feedback.
    Please try again.") and show the panel the same way — **no other
    state is touched**: `conversation`, `roleplaySession`, `avatar`, and
    every existing DOM element are left exactly as they were, so the user
    can keep chatting, use Live Voice, or click "New Roleplay" immediately
    afterward with zero side effects from the failed attempt.
  - `finally`: restore the button's text and re-run
    `updateFeedbackButtonState()` so it becomes clickable again
    immediately (retry is always available).
- `#feedback-close-btn` just hides `#feedback-panel` again
  (`style.display = 'none'`) — no state change beyond visibility.
- The existing `newRoleplayBtn` click handler gains one additional line:
  hide `#feedback-panel` (`style.display = 'none'`) alongside its
  existing resets. Without this, feedback from the just-abandoned
  conversation would remain visible on screen after starting a new
  roleplay — a stale, potentially misleading display, not merely a
  cosmetic gap. This is the only change to `newRoleplayBtn`'s existing
  handler; its reset of `roleplaySession`/`conversation`/the chat log is
  untouched.
- This code never touches `sendToSarah`, `avatar.think()`/`avatar.speak()`,
  the Live Voice controller, or any existing event listener. It reads
  `conversation`/`roleplaySession`/`isSending` and writes only to its own
  two new elements.

No change to `avatar-src/doctor-avatar.js` — the avatar's state machine
has no concept of "evaluating" and doesn't need one; evaluation is a
read-only side panel, not a new conversational turn.

## Backward compatibility

- `/chat`, `/personas`, `/voices`, `/tts`, `/avatar/session` are
  byte-for-byte unmodified — `POST /evaluate` is a wholly new, additive
  route.
- `app/bedrock.py` is not modified — every existing test in
  `tests/test_bedrock.py` keeps passing unmodified.
- The existing "New Roleplay" button's core behavior (reset session and
  conversation) is unchanged; its click handler gains exactly one
  additional line (hiding `#feedback-panel`, described above) so it
  doesn't leave stale feedback on screen — everything else about it, and
  every other existing element's markup/ID/class/listener, is untouched.
  `#get-feedback-btn` and `#feedback-panel` themselves are purely
  additive elements.
- A malformed or failed evaluation call cannot corrupt `conversation` or
  `roleplaySession` — the failure path explicitly touches neither.

## Error handling

- Missing `session` on `/evaluate`: 422 from FastAPI's own validation
  (required field), no custom handling needed.
- Unknown `persona_id`: 400, identical pattern to `/chat`.
- Any Bedrock network/auth failure, or a response that fails
  `extract_evaluation`'s validation (not JSON, not an object, missing or
  wrong-typed field): both produce the same generic 503, logged
  server-side via `logger.exception`, exactly like every other route —
  the client never learns which kind of failure occurred, matching this
  project's established "never leak upstream exception text" rule.
- Frontend failure handling is described precisely above: an inline
  error message in `#feedback-panel`, full recovery of button state, and
  zero mutation of any pre-existing state.

## Testing

Same conventions as the rest of the project (`pytest -v`, mocked at the
function boundary, no JS test infrastructure):

- **New file `tests/test_evaluation.py`** (mirrors `tests/test_bedrock.py`'s
  structure), network-free pure-function tests:
  - `build_evaluation_prompt`/`build_evaluation_request_body` produce the
    expected shape (system prompt contains the persona name, scenario,
    objective; `messages` passed through unchanged).
  - `extract_evaluation` on a valid, well-formed JSON response returns the
    expected dict.
  - `extract_evaluation` on JSON wrapped in a ` ```json ... ``` ` markdown
    fence still parses correctly (the one defensive allowance the
    extractor makes, since models commonly add this even when told not
    to).
  - `extract_evaluation` on JSON preceded by a short preamble before the
    fence (e.g. `"Here's the evaluation:\n```json\n{...}\n```"`) still
    parses correctly via the first-`{`-to-last-`}` fallback.
  - `extract_evaluation` raises `ValueError` for: non-JSON text; a JSON
    value that isn't an object; a missing `dimensions` key; a missing
    individual dimension field; a non-string value for any required
    field.
- **`tests/test_main.py`** additions:
  - `POST /evaluate` success: mocked `get_evaluation`, asserts the route
    returns its dict verbatim as the response JSON, and asserts
    `get_evaluation` was called with the resolved `Persona`, the session
    dict, and the converted messages list.
  - `POST /evaluate` with unknown `persona_id`: 400, same pattern as the
    existing `/chat` test.
  - `POST /evaluate` when `get_evaluation` raises (simulating either a
    real Bedrock failure or a malformed response): 503, generic message,
    and an assertion that the raised exception's message text is absent
    from the response body — the same leak-check pattern already applied
    to every other route.
  - `POST /evaluate` with `session` omitted entirely: 422.
- Full existing suite (`app/bedrock.py`, `app/personas`, `app/main.py`'s
  other routes) must keep passing unmodified — proving this addition
  changed nothing about any previously verified behavior.
- No JS test infrastructure exists or is being added, per established
  project convention. The frontend button/panel behavior is verified only
  by manual QA below.

## Manual QA acceptance criteria

- Start a Roleplay Session with any persona, exchange at least one
  message, click "Get Feedback." A results panel appears containing all
  four dimension assessments, an overall summary, and improvement
  recommendations — as plain qualitative text, with **no number,
  percentage, gauge, star rating, or pass/fail judgment anywhere in the
  panel**.
- Immediately after starting a roleplay, before sending any message,
  confirm "Get Feedback" is disabled.
- After closing the feedback panel, confirm Text Chat still works
  normally in the same session.
- Confirm Live Voice still works across multiple consecutive turns, both
  before and after using "Get Feedback" at least once in the same
  session.
- Confirm the Simli avatar, ElevenLabs audio, and audio-unlock all
  continue to work exactly as before — unaffected by this feature
  existing.
- Confirm "New Roleplay" still fully resets the session and conversation,
  regardless of whether "Get Feedback" was used beforehand, and that any
  previously-shown feedback panel is no longer visible after starting the
  new roleplay.
- If a failure can be induced (e.g., a transient network issue), confirm
  the panel shows an error message and that the conversation and roleplay
  session remain fully usable immediately afterward — nothing is lost or
  corrupted by a failed evaluation attempt.
- Repeat the "Get Feedback" flow with each of the three registered
  personas (Dr. Sarah Chen, Dr. Marcus Reyes, Dr. Priya Nair) to confirm
  the feature works generically, not only for one persona.

## Consistency check against the source documents, `PROJECT_CONTEXT.md`, and the current codebase

**Against the source documents:** every included dimension and the
"overall summary + recommendations" format traces to at least two
independent citations, quoted above; every excluded item is excluded for
a stated, evidence-based reason (single-source, coupled to an unbuilt
prerequisite, or requiring infrastructure already explicitly deferred).
No numeric scale, weighting, or threshold is invented anywhere — the
sources' own silence on this point is treated as binding, not as license
to fill the gap.

**Against `PROJECT_CONTEXT.md`:** "Backend stays stateless" (Important
architectural decisions) holds — `/evaluate` reads exactly the same
client-held data `/chat` already reads and stores nothing. The
provider-isolation pattern ("TTS is isolated from the avatar provider...
validated in practice") is extended, not violated — `app/evaluation.py`
is a new, isolated module the same way `app/tts.py` is. The "Things that
MUST NOT be broken" list's DOM contract, five avatar states, and
inline-style-toggle convention are all explicitly preserved by the
frontend design above, which reuses that exact toggle pattern rather than
introducing a new one. `PROJECT_CONTEXT.md` itself will need updating once
this is implemented and verified — that happens as part of implementing
this spec, not before, per this project's standing rule.

**Against the current codebase:** `app/bedrock.py`'s `MODEL_ID`/`REGION`
are the only things this spec reads from that module — verified by
reading the file directly; no other symbol is touched or duplicated.
`RoleplaySessionRequest` and `ChatMessage` (both already defined in
`app/main.py`) are reused as-is for `EvaluateRequest`, not redefined.
`get_persona`'s existing signature and the existing unknown-`persona_id`
→ 400 pattern are reused verbatim, not reimplemented.

No contradiction, unsupported assumption, or scope creep was found.
