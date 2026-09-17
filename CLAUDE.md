# CLAUDE.md — Mini ECHO

Read `PROJECT_CONTEXT.md` first, in full, before making any change in this repo. It
documents the current architecture, what's working, what must not break, and the
next planned feature. This file only holds durable rules; `PROJECT_CONTEXT.md` holds
the actual state and must be kept in sync with it.

## Rules for this project specifically

- **Update `PROJECT_CONTEXT.md`** whenever a change alters architecture, adds/removes
  a working feature, fixes a real bug worth remembering, or changes environment
  variables — the same standard used to write it originally. Keep it accurate, not
  just present.
- **No real browser is available in this environment.** Any change touching WebRTC,
  audio playback, or visual rendering can only be verified by the user in their own
  browser. Say plainly what you verified (tests, curl, diffs) versus what only they
  can confirm — never claim a UI/avatar/audio change "works" without that caveat.
- **For visual/UI-only requests, prefer touching only CSS and static markup.**
  Diff the `<script>` blocks in `static/index.html` against the prior commit to
  *prove* they're untouched, rather than eyeballing it.
- **After editing `avatar-src/doctor-avatar.js`, always run `npm run build`** before
  telling the user the change is live — the browser loads the committed
  `static/dist/avatar-bundle.js`, not the source file.
- **Never put a third-party API key in frontend code or an API response.** Keys stay
  in `.env` (gitignored) and are read server-side only. See `PROJECT_CONTEXT.md` for
  the exact variable names.
- **Run `pytest -v` after any backend change.** All existing tests must keep passing;
  add a test for new route/function behavior following the existing mocked-boundary
  pattern in `tests/test_main.py`.
- **Do not "fix" `scripts/bedrock_check.py`'s divergence from `app/bedrock.py`.** It's
  intentionally frozen — see `PROJECT_CONTEXT.md`.
- **Do not widen the frontend build step** beyond `avatar-src/doctor-avatar.js`
  without a real forcing reason (the same kind that made Simli's SDK require esbuild
  in the first place). The rest of `static/index.html` stays plain, build-free
  HTML/CSS/JS on purpose.
