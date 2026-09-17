# Live Voice Conversation — Design Spec

Status: approved design, not yet implemented.
Supersedes nothing. Extends the architecture documented in `PROJECT_CONTEXT.md`
("Next planned feature" section) — read that file first for the system this
plugs into.

## Goal

Make the roleplay voice-first: the user speaks instead of typing, and the
existing pipeline (Bedrock → ElevenLabs → Simli) handles the rest, exactly as
it does today for typed input. Text Chat stays fully available and unchanged.
MVP scope is desktop Chrome only.

Flow:

```
mic -> Speech-to-Text -> existing /chat (Bedrock) -> existing /tts (ElevenLabs)
    -> existing Simli avatar -> listen again
```

Turn-taking model: `Listening -> Thinking -> Sarah Speaking -> Listening`,
looping automatically until the user turns voice mode off.

## Non-goals (explicitly out of scope for this iteration)

- Safari, Firefox, or mobile support. Web Speech API is Chrome-only; this is
  an accepted MVP trade-off, not an oversight.
- Barge-in / interrupting Sarah while she's speaking. Strict turn-taking only.
- Any change to `app/bedrock.py`, `app/tts.py`, `app/avatar_simli.py`,
  `app/avatar_provider.py`, `avatar-src/doctor-avatar.js`, or the built
  `static/dist/avatar-bundle.js`. This feature is additive at the page level.
- A cloud/streaming STT provider. Explicitly deferred — see "Future STT swap"
  below for why today's design doesn't block it.
- Noise cancellation or acoustic echo cancellation. Turn-taking (not
  listening while Sarah talks) is the only mechanism preventing her voice
  from being captured; see "Preventing self-capture" below.

## STT provider decision

**Chosen: the browser's native `SpeechRecognition` API** (in Chrome, exposed
as `webkitSpeechRecognition`).

Why, over a cloud STT (e.g. a streaming API to a hosted provider):
- **No new API key, account, or AWS permission.** Every other integration in
  this project (Simli, ElevenLabs) required a new account and key; this is
  the one STT option that requires neither, which matters directly for
  keeping this MVP the smallest safe change.
- **No backend involvement at all.** Audio never leaves the browser through
  our infrastructure — recognition happens locally/via the browser vendor's
  own service, invisible to our stack. This means zero new routes, zero new
  provider files under `app/`, and zero new mocked-boundary tests required.
- **No added latency budget or per-minute cost** to reason about, unlike a
  cloud STT call sitting in the critical path before Bedrock.
- Cost of this choice: no Safari/Firefox support. Accepted per the browser
  scope decision above.

### Future STT swap (why this design doesn't block it)

All Web-Speech-API-specific behavior (vendor prefixing, continuous-mode
quirks, interim vs. final results, restart-on-end handling) is isolated
inside one new file, `static/stt-web-speech.js`, behind a small class with a
generic three-method shape:

```js
class WebSpeechSTT {
  static isSupported;               // feature-detection, no instantiation needed
  constructor({ onFinalResult, onError, onListeningChange }) {}
  start() {}
  stop() {}
}
```

Nothing else in the codebase touches the `SpeechRecognition` global directly.
Swapping to a cloud STT provider later means: write a new class matching this
same shape (e.g. `CloudSTT`, likely backed by a new `/stt` route and provider
file under `app/`, mirroring the `avatar_provider.py` pattern), and change one
instantiation line in `static/index.html`. No other file changes. This
mirrors the existing `TTS is isolated from the avatar provider` precedent
documented in `PROJECT_CONTEXT.md`.

## Files added / changed

### New: `static/stt-web-speech.js`

Plain, unbundled JS (no npm package involved — `SpeechRecognition` is a
native browser global). Loaded via a normal `<script src>` tag, **not**
routed through esbuild. This deliberately does not widen the frontend build
step, which stays scoped to `avatar-src/doctor-avatar.js` only, per the
existing project rule (Simli's SDK is the only thing that has ever forced a
build step here).

Responsibilities:
- Feature-detect `window.SpeechRecognition || window.webkitSpeechRecognition`
  and expose the result as `WebSpeechSTT.isSupported`.
- Wrap a `SpeechRecognition` instance configured for a single utterance per
  `start()` call (`continuous = false`, `interimResults = false` — the
  simplest correct setting for turn-taking; no partial-transcript UI in this
  MVP).
- Translate the API's `result` / `error` / `end` events into the three
  callbacks (`onFinalResult(transcript)`, `onError(error)`,
  `onListeningChange(isListening)`), so the rest of the app never touches
  the native event names or the vendor-prefixed global.
- Swallow/report the "no speech detected" case via `onError` with a
  recognizable reason string, so the page can restart listening instead of
  treating it as fatal (this is a normal, frequent event with this API, not
  an exceptional one).

### Changed: `static/index.html` (only file with functional changes)

1. One new script tag: `<script src="/static/stt-web-speech.js"></script>`,
   placed before the existing inline `<script>` block (same load-order
   pattern as the avatar bundle tag today).
2. New UI: a mic toggle button near the chat composer, to turn Live Voice
   mode on/off. If `WebSpeechSTT.isSupported` is false (non-Chrome), the
   button is rendered `disabled` with a `title`/inline note explaining why,
   rather than hidden — so the feature is visibly "not available in this
   browser" rather than silently absent. Text Chat is unaffected either way.
3. New CSS-only visual state: `data-state="listening"` on `#avatar-panel`
   (badge text + a mic-pulse animation, following the same
   `content` -from-`data-state` mapping pattern the other five states
   already use). Purely additive CSS, same file, same convention.
4. **Refactor** (behavior-preserving): extract the body of the existing
   `form.addEventListener('submit', ...)` handler — push user message,
   `addMessage`, `avatar.think()`, `POST /chat`, push assistant reply,
   `addMessage`, `avatar.speak()`, error rollback — into one function,
   `sendToSarah(message)`. The submit handler becomes a thin wrapper that
   reads `input.value` and calls `sendToSarah`. This is the only change to
   existing, working code, and it's a pure extraction: the exact same
   statements, same order, same `conversation` array, same error handling.
   Text Chat's behavior is unchanged; this is what let's Live Voice reuse it
   verbatim instead of duplicating it.
5. New voice-mode controller (all new code, added alongside the existing
   inline script logic):
   - Holds one `WebSpeechSTT` instance.
   - A `MutationObserver` on `avatarPanel`'s `data-state` attribute (this
     attribute is already written by `DoctorAvatar._setState` today — the
     observer is a read-only consumer, **no change to `doctor-avatar.js`
     needed**).
   - While Live Voice mode is on: when the observed state becomes `idle`,
     set `avatarPanel.dataset.state = 'listening'` and call
     `stt.start()`. `DoctorAvatar` never sets `dataset.state` on its own
     except from `think()`, `speak()`, `connect()`'s internal transitions,
     or an SDK event, so it won't clobber the `listening` value while the
     controller owns it.
   - `onFinalResult(transcript)`: call `stt.stop()` (defensive; recognition
     is single-utterance already) then `sendToSarah(transcript)`. Calling
     `sendToSarah` invokes `avatar.think()` immediately, which overwrites
     `dataset.state` to `thinking` — the natural `listening -> thinking`
     transition, no extra code needed.
   - `onError`: if the reason is "no speech" and voice mode is still on,
     just call `stt.start()` again (stay in `listening`); for any other
     error, drop back to idle and surface a small inline error state, same
     spirit as the existing `/chat` failure handling.
   - Turning voice mode off calls `stt.stop()` and clears the controller's
     `idle`-state hook so no further auto-restarts happen; it does not touch
     `avatar.state` itself.

### Unchanged

`app/main.py`, `app/bedrock.py`, `app/tts.py`, `app/avatar_simli.py`,
`app/avatar_provider.py`, `avatar-src/doctor-avatar.js`,
`static/dist/avatar-bundle.js`, `tests/*`. No rebuild (`npm run build`)
required for this feature. No new environment variables.

## Preventing Sarah's voice from being captured by the mic

The mechanism is scheduling, not audio processing: the mic is started only
when the observed avatar state is `idle` (Sarah is not producing audio), and
is stopped the instant a final transcript arrives — before `sendToSarah` (and
therefore before `avatar.think()`/`avatar.speak()`) ever runs. It is never
started again until the state cycles back through `thinking -> speaking ->
idle`. So there is no window where the recognizer is active while Sarah's
`<audio>` element is playing.

This is a turn-taking guarantee, not acoustic echo cancellation — it doesn't
protect against, say, a phone sitting next to open external speakers
picking up bleed from a *different* device. For a single desktop/laptop
session (mic + speakers or headphones on the one machine), turn-taking is
sufficient because the recognizer is simply off while Sarah talks. The spec
doesn't add `getUserMedia` audio-constraint handling (e.g.
`echoCancellation: true`) because `SpeechRecognition` doesn't expose control
over its own mic acquisition — that constraint knob doesn't exist for this
API. If self-capture is ever observed in practice, the fix is a real
microphone/speaker setup issue (e.g. headphones), not something addressable
in this code.

## Shared conversation history between Text Chat and Live Voice

No backend change of any kind. Today's architecture is already
"stateless backend, browser holds the array" (`PROJECT_CONTEXT.md`,
Architecture Decisions). Both input modes become two different producers of
the same input — a typed string, or a recognized-speech string — that both
flow through the same `sendToSarah(message)` function, mutate the same
top-level `conversation` array, append to the same `#chat` DOM log, and hit
the same `/chat` endpoint with the full history each time. There is exactly
one conversation, regardless of which mode produced each turn, so switching
modes mid-conversation needs no reconciliation step.

## New state

Adds a 6th real state, `listening`, to the five that exist today
(`connecting, idle, thinking, speaking, error`). `PROJECT_CONTEXT.md`
already flagged voice mode as "the feature that would finally justify adding
one" — this is that justification. Unlike the other five, `listening` is
set by the page's voice-mode controller (via the `MutationObserver` hook
described above), not by `DoctorAvatar` — `doctor-avatar.js` remains
completely unaware that voice mode exists.

## Error handling

- **Browser doesn't support `SpeechRecognition`:** mic toggle is disabled
  with an explanatory note at page load (feature-detected once, no retry
  logic needed). Text Chat is entirely unaffected.
- **Mic permission denied:** `WebSpeechSTT` surfaces this via `onError`;
  voice mode turns itself off and shows the same style of inline error
  bubble Text Chat already uses for failed `/chat` calls, rather than a
  silent failure.
- **"No speech detected" (routine, not exceptional):** silently restart
  listening, as described above — this fires often with real usage
  (pauses, false starts) and should not interrupt the loop or show an error.
- **`/chat` or `/tts` failure during a voice turn:** falls through to the
  exact same existing error path inside `sendToSarah` (rollback the
  optimistic user turn, show the error bubble) that Text Chat already has
  and already tests conceptually cover in spirit — no new backend error
  path exists to test, since no backend code changed.

## Testing

Consistent with the project's existing, deliberate convention (documented in
`PROJECT_CONTEXT.md`): no JS test infrastructure exists and none is being
added for this feature — same as `doctor-avatar.js` and the inline script
today. `pytest -v` continues to cover 100% of what changed on the backend,
which is nothing, so no new backend tests are needed either.

Verification is manual, in a real browser, by the user (this environment has
no browser access — per `CLAUDE.md`'s standing rule). The implementation
plan will include an explicit manual test script: toggle voice mode on,
speak a message, confirm transcript accuracy, confirm the
listening → thinking → speaking → listening cycle via the state badge,
confirm the mic does not pick up Sarah's own speech, confirm Text Chat still
works interleaved with Live Voice turns in the same conversation, confirm
graceful degradation in a non-Chrome browser (or via manually stubbing
`isSupported`).
