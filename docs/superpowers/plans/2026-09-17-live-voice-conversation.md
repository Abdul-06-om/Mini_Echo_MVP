# Live Voice Conversation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Live Voice Conversation mode (mic → browser Speech-to-Text → existing `/chat` → existing `/tts` → existing Simli avatar → auto-listen again) alongside the existing, unchanged Text Chat.

**Architecture:** A new, plain (unbundled) `static/stt-web-speech.js` wraps the browser's native `SpeechRecognition` API behind a small, swappable interface. `static/index.html`'s existing inline script gains a shared `sendToSarah(message)` function (extracted from the current form-submit handler, behavior-identical) that both Text Chat and the new voice controller call, plus a `MutationObserver`-driven turn-taking loop that starts/stops the recognizer based on the avatar's existing `data-state` attribute. No backend file changes.

**Tech Stack:** Plain browser JS (`SpeechRecognition`/`webkitSpeechRecognition`), no new npm packages, no new Python deps.

**Spec:** `docs/superpowers/specs/2026-09-17-live-voice-conversation-design.md`

## Global Constraints

- MVP targets desktop Chrome only (Web Speech API has no Safari/Firefox support) — this is accepted, not a bug to fix.
- No new API key, account, or AWS permission may be introduced anywhere in this plan.
- Do not modify: `app/main.py`, `app/bedrock.py`, `app/tts.py`, `app/avatar_simli.py`, `app/avatar_provider.py`, `avatar-src/doctor-avatar.js`, `static/dist/avatar-bundle.js`. None of these need to change for this feature.
- `static/stt-web-speech.js` must be a plain `<script src>` file — it must **not** be added to `package.json`'s `build` script or otherwise routed through esbuild. The build step stays scoped to `avatar-src/doctor-avatar.js` only.
- No `npm run build` is needed anywhere in this plan (nothing under `avatar-src/` changes).
- Recognition config is fixed for this MVP: `continuous = false`, `interimResults = false` — one utterance per listening turn, no partial-transcript UI.
- The `listening` state is written to `#avatar-panel`'s `data-state` (and `#avatar-state-badge`'s text) by the new page-level voice controller only. `doctor-avatar.js` must not be touched or made aware voice mode exists.
- **No JS test infrastructure exists in this project and none is being added here** (documented project convention — see `PROJECT_CONTEXT.md`, "Tests and how to run them"). In place of `pytest`-style red/green steps, each JS-touching task below verifies with `node --check` (syntax-only — catches typos/malformed code without needing a browser) and, where relevant, a `curl` check that the running server serves the new/changed content correctly. Final human-in-a-real-browser verification is a dedicated step in the last task, per this project's standing rule that WebRTC/audio/UI changes can only be confirmed by the user.
- Run `pytest -v` once at the end (Task 5) to confirm the existing 15 backend tests are unaffected — expected to be a no-op check since no backend file changes, but it's cheap and confirms nothing was accidentally touched.
- `PROJECT_CONTEXT.md` must be updated once the feature works, per this project's CLAUDE.md rule.

---

## Task 1: STT provider module (`static/stt-web-speech.js`)

**Files:**
- Create: `static/stt-web-speech.js`

**Interfaces:**
- Produces: `window.MiniEchoSTT.WebSpeechSTT` — a class with:
  - `static get isSupported()` → `boolean`
  - `constructor({ onFinalResult, onError, onListeningChange })` — all three callbacks optional
    - `onFinalResult(transcript: string)` — called once per completed utterance
    - `onError(reason: string)` — called with the native `SpeechRecognitionErrorEvent.error` string (e.g. `"no-speech"`, `"not-allowed"`, `"network"`, ...)
    - `onListeningChange(isListening: boolean)` — called when recognition actually starts/stops
  - `start()` — begins listening for one utterance; no-ops with a console warning if unsupported or already listening
  - `stop()` — stops listening if active; no-ops safely if not currently listening

- [ ] **Step 1: Create the file**

```js
(function () {
  "use strict";

  const LOG_PREFIX = "[WebSpeechSTT]";
  const SpeechRecognitionImpl = window.SpeechRecognition || window.webkitSpeechRecognition;

  class WebSpeechSTT {
    static get isSupported() {
      return !!SpeechRecognitionImpl;
    }

    constructor({ onFinalResult, onError, onListeningChange } = {}) {
      this.onFinalResult = onFinalResult;
      this.onError = onError;
      this.onListeningChange = onListeningChange;
      this._recognition = null;
    }

    start() {
      if (!WebSpeechSTT.isSupported) {
        console.warn(LOG_PREFIX, "start() called but SpeechRecognition is not supported in this browser");
        return;
      }
      if (this._recognition) {
        console.warn(LOG_PREFIX, "start() called while already listening — ignoring");
        return;
      }

      const recognition = new SpeechRecognitionImpl();
      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.lang = "en-US";

      recognition.onstart = () => {
        console.log(LOG_PREFIX, "started listening");
        if (this.onListeningChange) this.onListeningChange(true);
      };

      recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript.trim();
        console.log(LOG_PREFIX, "final transcript:", transcript);
        if (transcript && this.onFinalResult) {
          this.onFinalResult(transcript);
        }
      };

      recognition.onerror = (event) => {
        console.warn(LOG_PREFIX, "error:", event.error);
        if (this.onError) this.onError(event.error);
      };

      recognition.onend = () => {
        console.log(LOG_PREFIX, "stopped listening");
        this._recognition = null;
        if (this.onListeningChange) this.onListeningChange(false);
      };

      this._recognition = recognition;
      recognition.start();
    }

    stop() {
      if (this._recognition) {
        this._recognition.stop();
      }
    }
  }

  window.MiniEchoSTT = { WebSpeechSTT };
})();
```

- [ ] **Step 2: Syntax-check the file**

Run: `node --check static/stt-web-speech.js`
Expected: no output, exit code 0. (This only checks JS syntax — `window`/`SpeechRecognition` are undefined under plain Node, but `--check` parses without executing, so that's fine.)

- [ ] **Step 3: Confirm it's served correctly**

```bash
source venv/bin/activate
uvicorn app.main:app &
sleep 1
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/static/stt-web-speech.js
kill %1
```

Expected: `200` printed, then the background server is stopped.

- [ ] **Step 4: Commit**

```bash
git add static/stt-web-speech.js
git commit -m "$(cat <<'EOF'
feat: add browser Speech-to-Text provider module

Wraps the native SpeechRecognition/webkitSpeechRecognition API behind a
small class (isSupported, start/stop, onFinalResult/onError/onListeningChange)
so the live-voice feature can be wired to it without any file elsewhere
depending on the native API's quirks. Not yet used by the page.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Voice UI — mic toggle button and "listening" state CSS

**Files:**
- Modify: `static/index.html` (CSS `<style>` block and markup only — no `<script>` changes in this task)

**Interfaces:**
- Consumes: nothing new (pure markup/CSS)
- Produces: a `<button id="voice-toggle-btn">` element and a `data-state="listening"` CSS mapping for `#avatar-panel`, for Task 4's JS to attach behavior to. The button has no click handler yet after this task — that's expected and harmless (inert until Task 4).

- [ ] **Step 1: Add the "listening" badge CSS**

In the `<style>` block, find this existing block (it's immediately followed by the `@keyframes dot-pulse` rule):

```css
  #avatar-panel[data-state="error"] #avatar-state-badge::before { background: var(--danger); }
  #avatar-panel[data-state="error"] #avatar-state-badge::after { content: "Connection issue"; }
```

Add immediately after it (before the blank line and `@keyframes dot-pulse`):

```css
  #avatar-panel[data-state="listening"] #avatar-state-badge::before {
    background: var(--accent);
    animation: dot-pulse 1s ease-in-out infinite;
  }
  #avatar-panel[data-state="listening"] #avatar-state-badge::after { content: "Listening…"; }
```

- [ ] **Step 2: Add the mic toggle button CSS**

Find this existing block:

```css
  form#chat-form button svg {
    width: 17px;
    height: 17px;
  }
```

Add immediately after it (before the `@media (max-width: 860px)` block):

```css
  #voice-toggle-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 40px;
    height: 40px;
    flex-shrink: 0;
    border: 1px solid var(--panel-border);
    border-radius: 50%;
    background: transparent;
    color: var(--text-dim);
    cursor: pointer;
    transition: background 0.15s ease, color 0.15s ease, border-color 0.15s ease;
  }
  #voice-toggle-btn:hover:not(:disabled) {
    border-color: var(--accent-dim);
    color: var(--text);
  }
  #voice-toggle-btn:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }
  #voice-toggle-btn[data-active="true"] {
    background: var(--accent);
    border-color: var(--accent);
    color: #08211d;
  }
  #voice-toggle-btn:disabled {
    opacity: 0.4;
    cursor: default;
  }
  #voice-toggle-btn svg {
    width: 17px;
    height: 17px;
  }
```

- [ ] **Step 3: Add the button markup**

Find:

```html
      <form id="chat-form">
        <input id="message-input" type="text" placeholder="Type a message..." autocomplete="off" required>
```

Replace with:

```html
      <form id="chat-form">
        <button type="button" id="voice-toggle-btn" aria-label="Toggle live voice conversation" data-active="false">
          <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 15a3 3 0 0 0 3-3V6a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3Z" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/><path d="M19 11a7 7 0 0 1-14 0M12 18v3" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </button>
        <input id="message-input" type="text" placeholder="Type a message..." autocomplete="off" required>
```

- [ ] **Step 4: Verify the `<script>` blocks are untouched**

```bash
git diff static/index.html
```

Expected: every changed line is inside the `<style>` block or the button markup added in Step 3 — nothing inside either `<script>` block changed. (Following this project's standing rule to diff, not eyeball, when a change should be script-free.)

- [ ] **Step 5: Confirm the page serves the new markup**

```bash
source venv/bin/activate
uvicorn app.main:app &
sleep 1
curl -s http://127.0.0.1:8000/ | grep -c 'id="voice-toggle-btn"'
kill %1
```

Expected: `1`.

- [ ] **Step 6: Commit**

```bash
git add static/index.html
git commit -m "$(cat <<'EOF'
feat: add mic toggle button and listening-state styling

CSS and markup only, additive — the button has no behavior yet. Follows
the existing state-badge pattern used by connecting/idle/thinking/speaking/error.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Extract `sendToSarah(message)` from the form-submit handler

**Files:**
- Modify: `static/index.html` (inline `<script>` block only)

**Interfaces:**
- Consumes: existing page-level `conversation` array, `isSending` flag, `avatar`, `addMessage()`, `voiceSelect`, `input`, `button` — all already defined earlier in the same script.
- Produces: `async function sendToSarah(message)` in the inline script's top-level scope — the single place that pushes to `conversation`, calls `/chat`, and triggers `avatar.speak()`. Task 4's voice controller will call this directly.

This is a **behavior-preserving refactor**: the exact same statements run in the exact same order for a text-chat submission before and after this change. The only difference is that clearing `input.value` now happens in the submit handler (a UI concern) rather than inside the extracted pipeline function.

- [ ] **Step 1: Replace the submit handler**

Find:

```js
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (isSending) return;

      const message = input.value.trim();
      if (!message) return;

      isSending = true;
      input.disabled = true;
      button.disabled = true;

      try {
        conversation.push({ role: 'user', content: message });
        addMessage(message, 'user');
        input.value = '';
        avatar.think();

        const response = await fetch('/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ messages: conversation }),
        });

        if (!response.ok) {
          throw new Error('Request failed with status ' + response.status);
        }

        const data = await response.json();
        conversation.push({ role: 'assistant', content: data.reply });
        addMessage(data.reply, 'ai');
        avatar.speak(data.reply, voiceSelect.value);
      } catch (error) {
        conversation.pop();
        addMessage('Something went wrong. Please try again.', 'error');
      } finally {
        isSending = false;
        input.disabled = false;
        button.disabled = false;
        input.focus();
      }
    });
```

Replace with:

```js
    async function sendToSarah(message) {
      if (isSending) return;
      if (!message) return;

      isSending = true;
      input.disabled = true;
      button.disabled = true;

      try {
        conversation.push({ role: 'user', content: message });
        addMessage(message, 'user');
        avatar.think();

        const response = await fetch('/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ messages: conversation }),
        });

        if (!response.ok) {
          throw new Error('Request failed with status ' + response.status);
        }

        const data = await response.json();
        conversation.push({ role: 'assistant', content: data.reply });
        addMessage(data.reply, 'ai');
        avatar.speak(data.reply, voiceSelect.value);
      } catch (error) {
        conversation.pop();
        addMessage('Something went wrong. Please try again.', 'error');
      } finally {
        isSending = false;
        input.disabled = false;
        button.disabled = false;
        input.focus();
      }
    }

    form.addEventListener('submit', (event) => {
      event.preventDefault();
      const message = input.value.trim();
      if (!message) return;
      input.value = '';
      sendToSarah(message);
    });
```

- [ ] **Step 2: Syntax-check the inline script**

The inline script is embedded in HTML, so extract it to a temp file first:

```bash
awk '/^  <script>$/{flag=1; next} /^  <\/script>$/{flag=0} flag' static/index.html > /tmp/mini-echo-inline-check.js
node --check /tmp/mini-echo-inline-check.js
rm /tmp/mini-echo-inline-check.js
```

Expected: no output from `node --check`, exit code 0.

- [ ] **Step 3: Confirm Text Chat still behaves identically**

```bash
git diff static/index.html
```

Expected: the diff shows only the extraction shown in Step 1 (function boundary moved, `input.value = ''` moved to the submit handler) — no other statement added, removed, or reordered within the pipeline itself. Read through it once to confirm `conversation.push`, `addMessage`, `avatar.think()`, the `/chat` fetch, `avatar.speak()`, and the `catch`/`finally` blocks are byte-identical to before.

Real Text Chat behavior (typing and sending a message, seeing Sarah's reply and hearing her speak) can only be confirmed by the user in a real browser — flag this plainly rather than claiming it "works" from the diff alone. It will be covered again in Task 5's end-to-end manual check.

- [ ] **Step 4: Commit**

```bash
git add static/index.html
git commit -m "$(cat <<'EOF'
refactor: extract sendToSarah() from the chat form submit handler

Behavior-preserving: the pipeline (push message, addMessage, avatar.think(),
POST /chat, avatar.speak(), error rollback) is now a standalone function so
the upcoming voice controller can call the exact same code path Text Chat
already uses, instead of duplicating it.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Voice-mode controller — wire mic button, STT, and turn-taking

**Files:**
- Modify: `static/index.html` (add one `<script src>` tag, and add to the inline `<script>` block)

**Interfaces:**
- Consumes:
  - `window.MiniEchoSTT.WebSpeechSTT` from Task 1
  - `sendToSarah(message)` from Task 3
  - existing `avatarPanel`, `avatarStateBadge` DOM refs and the `data-state` attribute contract already set by `doctor-avatar.js`
- Produces: no new externally-consumed interface — this task is the final wiring, consumed only by the user's browser.

- [ ] **Step 1: Load the STT module**

Find:

```html
  <script src="/static/dist/avatar-bundle.js"></script>
```

Replace with:

```html
  <script src="/static/dist/avatar-bundle.js"></script>
  <script src="/static/stt-web-speech.js"></script>
```

- [ ] **Step 2: Add the defensive stop-recognition guard to `sendToSarah`**

This closes a gap the spec calls out only for the voice-triggered path (stop recognition before running the pipeline) but that must also apply when a *text* submission happens while voice mode's recognizer is still active (e.g. the user types while the mic is listening) — otherwise the mic could still be capturing audio when `avatar.speak()` starts playing Sarah's reply. `stt.stop()` is always a safe no-op when nothing is listening, so making it unconditional at the top of the shared pipeline is the correct place for this guarantee to live, exactly once.

Find (inside `sendToSarah`, from Task 3):

```js
      isSending = true;
      input.disabled = true;
      button.disabled = true;

      try {
        conversation.push({ role: 'user', content: message });
```

Replace with:

```js
      isSending = true;
      input.disabled = true;
      button.disabled = true;
      if (stt) stt.stop();

      try {
        conversation.push({ role: 'user', content: message });
```

- [ ] **Step 3: Add the voice controller**

Find the end of the inline script (the closing of the `form.addEventListener('submit', ...)` block added in Task 3):

```js
    form.addEventListener('submit', (event) => {
      event.preventDefault();
      const message = input.value.trim();
      if (!message) return;
      input.value = '';
      sendToSarah(message);
    });
```

Add immediately after it, before the closing `</script>` tag:

```js

    const voiceToggleBtn = document.getElementById('voice-toggle-btn');
    let voiceModeActive = false;

    const stt = MiniEchoSTT.WebSpeechSTT.isSupported
      ? new MiniEchoSTT.WebSpeechSTT({
          onFinalResult: (transcript) => {
            stt.stop();
            sendToSarah(transcript);
          },
          onError: (error) => {
            if (error === 'no-speech' && voiceModeActive) {
              console.log('[page] no speech detected, listening again');
              stt.start();
              return;
            }
            console.warn('[page] voice mode stopped due to STT error:', error);
            voiceModeActive = false;
            voiceToggleBtn.dataset.active = 'false';
            if (avatarPanel.dataset.state === 'listening') {
              avatarPanel.dataset.state = 'idle';
              avatarStateBadge.textContent = 'idle';
            }
            addMessage(
              error === 'not-allowed'
                ? 'Voice mode stopped: microphone permission denied.'
                : 'Voice mode stopped: speech recognition error.',
              'error',
            );
          },
        })
      : null;

    if (!stt) {
      voiceToggleBtn.disabled = true;
      voiceToggleBtn.title = 'Live voice mode requires a browser with SpeechRecognition support (e.g. desktop Chrome)';
    } else {
      voiceToggleBtn.addEventListener('click', () => {
        voiceModeActive = !voiceModeActive;
        voiceToggleBtn.dataset.active = String(voiceModeActive);

        if (voiceModeActive) {
          if (avatarPanel.dataset.state === 'idle') {
            avatarPanel.dataset.state = 'listening';
            avatarStateBadge.textContent = 'listening';
            stt.start();
          }
        } else {
          stt.stop();
          if (avatarPanel.dataset.state === 'listening') {
            avatarPanel.dataset.state = 'idle';
            avatarStateBadge.textContent = 'idle';
          }
        }
      });

      const voiceStateObserver = new MutationObserver(() => {
        if (!voiceModeActive) return;
        if (avatarPanel.dataset.state === 'idle') {
          avatarPanel.dataset.state = 'listening';
          avatarStateBadge.textContent = 'listening';
          stt.start();
        }
      });
      voiceStateObserver.observe(avatarPanel, { attributes: true, attributeFilter: ['data-state'] });
    }
```

- [ ] **Step 4: Syntax-check the inline script**

```bash
awk '/^  <script>$/{flag=1; next} /^  <\/script>$/{flag=0} flag' static/index.html > /tmp/mini-echo-inline-check.js
node --check /tmp/mini-echo-inline-check.js
rm /tmp/mini-echo-inline-check.js
```

Expected: no output, exit code 0.

- [ ] **Step 5: Confirm the served page includes both new script tags**

```bash
source venv/bin/activate
uvicorn app.main:app &
sleep 1
curl -s http://127.0.0.1:8000/ | grep -c 'stt-web-speech.js'
kill %1
```

Expected: `1`.

- [ ] **Step 6: Commit**

```bash
git add static/index.html
git commit -m "$(cat <<'EOF'
feat: wire live voice conversation turn-taking

Mic toggle button starts/stops browser speech recognition; a MutationObserver
on the avatar's existing data-state attribute restarts listening every time
the avatar returns to idle after speaking, forming the
listening -> thinking -> speaking -> listening loop. sendToSarah() now stops
any active recognition before running, so the mic can never be capturing
while Sarah's reply is generated or spoken, regardless of whether the turn
was typed or spoken.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Regression check, manual QA script, and PROJECT_CONTEXT.md update

**Files:**
- Modify: `PROJECT_CONTEXT.md`

**Interfaces:**
- Consumes: nothing new — this task verifies and documents Tasks 1–4.

- [ ] **Step 1: Run the existing backend test suite**

```bash
source venv/bin/activate
pytest -v
```

Expected: all 15 tests pass (no backend file changed in this plan, so this should be a clean no-op confirmation, not a fix-something step — if anything fails, stop and investigate before continuing, since it would mean something outside this plan's intended scope was touched).

- [ ] **Step 2: Hand off the manual browser verification script**

This step cannot be executed in this environment — no real browser is available here (per `CLAUDE.md`). Present this exact checklist to the user to run themselves in Chrome:

1. Run `uvicorn app.main:app --reload`, open `http://127.0.0.1:8000/`.
2. Confirm the page loads exactly as before: avatar connects, poster→video swap happens, Text Chat still sends/receives/speaks normally (this is the regression check for Task 3's refactor).
3. Click the new mic button. Confirm: it visually activates (filled accent background), the browser's native "use microphone?" permission prompt appears (first time only), and the avatar badge changes to "Listening…".
4. Speak a short message. Confirm: the badge moves to "Thinking…" once you stop talking, your transcribed message appears in the chat log as a user bubble, Sarah's reply appears and is spoken with lip-sync (badge → "Speaking…"), and the badge automatically returns to "Listening…" afterward without touching anything.
5. Say nothing for a few seconds after the mic activates at least once — confirm the app quietly keeps listening (no error shown) rather than stopping, exercising the "no-speech" recovery path.
6. While the avatar is speaking, confirm (by watching the badge and, if possible, OS mic-activity indicator) that the mic is not active — this is the turn-taking self-capture guard.
7. Click the mic button again to turn voice mode off mid-loop. Confirm the badge returns to "Online" and the mic stops.
8. With voice mode off, type and send a text message — confirm Text Chat still works standalone.
9. Turn voice mode on, then immediately type and send a text message before speaking — confirm it goes through normally and the badge does not get stuck on "Listening…" (this exercises Task 4 Step 2's defensive `stt.stop()` guard).
10. Try in a non-Chrome browser (or via DevTools device/user-agent override) if convenient — confirm the mic button appears disabled with an explanatory tooltip, and Text Chat is unaffected.

Report back which of these pass/fail; do not consider this feature "done" until the user confirms step 4 (the core loop) works in their own browser.

- [ ] **Step 3: Update `PROJECT_CONTEXT.md`**

Insert a new `## Live Voice Conversation integration` section after the existing "Simli live avatar integration" section (adjust placement only if the file's structure has shifted since this plan was written — the goal is grouping it with the other feature-integration sections, not an exact line number). Use this text as the actual content (adjust only if Task 5 Step 2's manual QA surfaced a real behavioral difference from what's described):

```markdown
## Live Voice Conversation integration

Alongside typed Text Chat, the page now supports a voice-first mode: the
user speaks, the browser transcribes it, and the transcript is sent through
the *same* `/chat` → Bedrock → `/tts` → Simli pipeline Text Chat already
uses — no new backend route exists or was needed.

**STT provider** (`static/stt-web-speech.js`, `window.MiniEchoSTT.WebSpeechSTT`):
wraps the browser's native `SpeechRecognition`/`webkitSpeechRecognition` API
(`continuous: false`, `interimResults: false` — one utterance per listening
turn). Desktop Chrome only; Safari and Firefox lack this API, so the mic
toggle button renders `disabled` with an explanatory tooltip there and Text
Chat is unaffected. Deliberately not run through esbuild — it's a native
browser global, no npm package involved, so the build step stays scoped to
`avatar-src/doctor-avatar.js` as before. Requires no new API key, account, or
AWS permission. Kept behind a 3-callback interface
(`onFinalResult`/`onError`/`onListeningChange`) plus `start()`/`stop()`
specifically so a future cloud STT provider can be swapped in by writing one
new file with the same shape and changing one instantiation line in
`static/index.html` — mirroring the existing `avatar_provider.py` /
`app/tts.py` isolation pattern.

**New `listening` state**: a 6th avatar state alongside the original five
(`connecting, idle, thinking, speaking, error`). Unlike those five, it is
set directly on `#avatar-panel`'s `data-state` (and mirrored onto
`#avatar-state-badge`'s text) by the page's voice controller in
`static/index.html`, not by `DoctorAvatar` — `avatar-src/doctor-avatar.js`
was not modified and has no awareness voice mode exists.

**Turn-taking loop**: clicking the mic button (`#voice-toggle-btn`) starts
listening only while the avatar is `idle`. A `MutationObserver` on
`#avatar-panel`'s `data-state` attribute restarts listening every time the
avatar returns to `idle` after speaking (the existing `"silent"` SDK event,
observed indirectly), forming
`listening -> thinking -> speaking -> listening` automatically until the
button is toggled off. A "no-speech" recognition error just restarts
listening rather than stopping voice mode; other errors (e.g. mic permission
denied) stop voice mode and show an inline error bubble, the same visual
pattern Text Chat already uses for failed `/chat` calls.

**Preventing Sarah's voice from being captured by the mic**: purely a
scheduling guarantee, not audio processing. The recognizer is only ever
started while state is `idle`, and `sendToSarah()` — the single function
both Text Chat and voice mode call — unconditionally stops any active
recognition as its first action, before `avatar.think()`/`avatar.speak()`
run. This covers both the voice-triggered turn and the edge case of a typed
message being sent while the mic happens to be listening.

**Shared conversation history**: no backend or data-model change. Text Chat
and Live Voice both call `sendToSarah(message)`, which pushes into the same
top-level `conversation` array and appends to the same `#chat` log
regardless of which mode produced the message — the two modes were never
separate conversations to reconcile.

See `docs/superpowers/specs/2026-09-17-live-voice-conversation-design.md`
for the full design rationale and rejected alternatives.
```

Also make these two small edits elsewhere in the file:
- In "Architecture and key files", add a line for the new file under `static/`: `` static/stt-web-speech.js  Browser Web Speech API wrapper for Live Voice mode (plain script, not bundled) ``.
- In "Known issues / open items", remove or rewrite the bullet about there being no "listening" state (it's now implemented) and add a bullet noting Live Voice mode is desktop-Chrome-only (Safari/Firefox lack `SpeechRecognition`).

- [ ] **Step 4: Commit**

```bash
git add PROJECT_CONTEXT.md
git commit -m "$(cat <<'EOF'
docs: document Live Voice Conversation feature in PROJECT_CONTEXT.md

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```
