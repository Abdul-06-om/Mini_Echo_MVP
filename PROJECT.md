# Mini ECHO — MVP Plan

## What This Is

A small learning project: a simplified version of ECHO, an AI roleplay
platform where a user converses with an AI acting as a healthcare
professional. Built primarily to learn AI engineering and software
development fundamentals — not to be a production medical product.

This document is the agreed plan for the **MVP only**. A larger/fuller
version of the project may follow once this MVP works end-to-end.

## 1. MVP Definition

A local web app. The user opens a page in their browser, sees a chat
box with a disclaimer ("this is an AI roleplay, not real medical
advice"), types a message, and receives a reply from an AI playing one
fixed healthcare persona (e.g. a general practitioner). The
conversation continues naturally within that browser session.

**Key simplicity decision:** no database, no login, no server-side
sessions. The **browser** holds the conversation history (a JavaScript
list of messages) and sends the *entire* conversation so far to the
backend on every message. The backend remembers nothing between
requests — it is stateless. This mirrors how real chat APIs (OpenAI,
Anthropic) work, and it means we skip building session/database
machinery entirely for the MVP.

## 2. Scope

**In scope:**
- One fixed AI persona (a system prompt describing a "helpful general
  practitioner")
- Text chat in a browser
- AWS Bedrock as the AI provider
- Conversation remembered only during the browser session (lost on
  page refresh)
- Runs on the developer's own machine only (not deployed publicly)
- Basic error handling (AI call fails → friendly message, not a crash)
- A visible disclaimer that this is not real medical advice

**Out of scope for this MVP** (candidates for the later, bigger
project):
- User accounts / login
- Saved history (database)
- Multiple personas / persona switching
- Streaming replies (word-by-word typing effect)
- Voice/audio input or output
- Deployment to the internet / multiple simultaneous users
- Automated test suite (verification is manual, per feature, for this
  learning MVP)

## 3. User Workflow

1. User starts the backend server on their machine.
2. User opens the page in a browser.
3. Page shows the disclaimer and an empty chat box.
4. User types a message and hits send.
5. Browser sends the full conversation-so-far to the backend.
6. Backend adds the persona's system prompt, calls AWS Bedrock.
7. Backend returns the AI's reply.
8. Browser displays the reply and appends it to the conversation list.
9. Repeat from step 4.

## 4. Tech Stack

| Piece | What it is | Why we need it |
|---|---|---|
| Python 3 | Programming language | Already known by the developer — no new language while learning AI concepts. |
| FastAPI | Backend web framework | Defines the `/chat` endpoint: receives the conversation, returns the AI's reply. Built-in request validation catches bugs early. |
| Uvicorn | ASGI server | The program that actually listens on a network port and runs the FastAPI app. FastAPI describes behavior; Uvicorn serves it. |
| boto3 | AWS's official Python SDK | How the backend calls Amazon Bedrock to get AI replies. |
| HTML + CSS + plain JavaScript | Frontend, in the browser | Displays the chat box, captures input, calls the backend with `fetch()`. No React/Node/build tools, to keep concepts visible and simple. |
| venv + pip | Python's virtual environment + package installer | Keeps this project's dependencies isolated and tracked (`requirements.txt`). |

Deliberately excluded: database, frontend framework, authentication
library — not needed for the in-scope MVP.

## 5. Architecture

```
Browser (HTML + JS)  --HTTP POST /chat (JSON)-->  FastAPI backend (Python, local machine)
       ^                                                    |
       |                                                    v
       ----------------  JSON reply  <--------------  boto3 --> Amazon Bedrock (Claude model)
```

1. Browser sends the whole conversation (as JSON) to `POST /chat`.
2. Backend prepends the persona's system prompt to that conversation.
3. Backend calls Bedrock via `boto3`, using AWS credentials.
4. Bedrock returns the AI's reply text.
5. Backend sends the reply back to the browser as JSON.
6. Browser displays it and appends it to its local conversation list.

**Error handling:** if step 3 fails (bad credentials, network issue,
rate limit), the backend catches the error and returns a clean JSON
error instead of crashing; the browser shows a friendly message
instead of breaking.

## 6. Feature Breakdown (Build Order)

Each step is small, independently verifiable, and builds on the
previous one. We do not move to the next step until the current one is
verified working.

1. **Project setup** — Python virtual environment, install
   FastAPI/Uvicorn/boto3, basic folder structure.
   *Verify: a "hello world" test route responds.*
2. **Bedrock connectivity check** — AWS account and Bedrock model
   access enabled, credentials configured, a standalone script sends
   one hardcoded message and prints the reply.
   *Verify: terminal prints an AI response.*
3. **`/chat` endpoint, no persona yet** — backend accepts a message,
   forwards it to Bedrock, returns the reply as JSON.
   *Verify: a test request (browser/curl) returns an AI reply.*
4. **Add the persona** — system prompt makes replies sound like the
   healthcare-professional persona.
   *Verify: replies match the intended tone/role.*
5. **Basic chat frontend** — static HTML page with input + send
   button, calls `/chat` via `fetch`, displays replies.
   *Verify: user can chat in the browser.*
6. **Conversation memory within a session** — frontend sends full
   history each time so the AI remembers earlier context.
   *Verify: AI correctly references something said earlier in the
   same session.*
7. **Disclaimer + graceful errors** — static disclaimer banner, and a
   friendly message shown if the Bedrock call fails.
   *Verify: simulate a failure, confirm the UI does not crash.*

## Status

Plan agreed. AWS account / Bedrock access not yet set up — this will
be part of step 2. No code written yet.
