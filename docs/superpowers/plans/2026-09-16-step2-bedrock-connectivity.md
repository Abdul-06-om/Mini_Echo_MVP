# Step 2: Bedrock Connectivity Check Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove the project can call AWS Bedrock and get an AI reply back, via a small standalone script — the foundation every later step (the real `/chat` endpoint, the persona) builds on.

**Architecture:** One standalone script (`scripts/bedrock_check.py`), separate from the FastAPI app, with its request-building and response-parsing logic split into small testable functions. The script sends one hardcoded message to Bedrock via `boto3` and prints the reply. AWS account setup, Bedrock model access, and local credential configuration were already completed and verified manually before this plan (confirmed working: `aws sts get-caller-identity` succeeds, and a manual `invoke-model` call against `us.anthropic.claude-haiku-4-5-20251001-v1:0` in `us-east-1` returned a real reply) — this plan only covers the script.

**Tech Stack:** Python 3, boto3, pytest (same stack as Step 1; no new dependencies)

**Spec:** `/Users/abdulrahman/Desktop/Mini_Echo_MVP/PROJECT.md`

## Global Constraints

- Language: Python 3, dependencies managed via `venv` + `pip` (per spec section 4)
- AI provider: AWS Bedrock via `boto3` (per spec section 4)
- Model to call: **`us.anthropic.claude-haiku-4-5-20251001-v1:0`** — this exact inference-profile ID, in region **`us-east-1`**. (Discovered live this session: the plain model ID `anthropic.claude-haiku-4-5-20251001-v1:0` fails with "on-demand throughput isn't supported" — Bedrock requires the `us.`-prefixed inference-profile ID for this model.)
- Request body shape for `invoke_model`: `{"anthropic_version": "bedrock-2023-05-31", "max_tokens": <int>, "messages": [{"role": "user", "content": <str>}]}` — verified working via a manual AWS CLI call this session.
- Response body shape: JSON with a top-level `"content"` list; the reply text is at `content[0]["text"]` — verified via the same manual call.
- No AWS credentials of any kind in code, ever. `boto3` must pick up credentials automatically from the local AWS credential chain (`~/.aws/credentials`, already configured via `aws configure`) — never read, print, or log credential values.
- Backend must remain stateless (per spec section 1) — not directly applicable to this standalone script, but the script must not write any conversation state to disk.

---

### Task 1: Bedrock Connectivity Script

**Files:**
- Create: `scripts/__init__.py`
- Create: `scripts/bedrock_check.py`
- Create: `tests/test_bedrock_check.py`

**Interfaces:**
- Produces: `scripts.bedrock_check.build_request_body(message: str) -> dict` — builds the Bedrock request JSON body for a given message string.
- Produces: `scripts.bedrock_check.extract_reply_text(response_body: dict) -> str` — pulls the reply text out of a parsed Bedrock response JSON body.
- Produces: `scripts.bedrock_check.MODEL_ID` (str) and `scripts.bedrock_check.REGION` (str) — the constants later steps (the `/chat` endpoint) will reuse for their own Bedrock calls.
- These two functions are unit-tested without any network call. The actual live AWS call only happens in `main()`, which is verified manually (Step 7 below), not by an automated test — an automated test would need real AWS credentials to run and would make a real network call on every test run, which is out of scope for this project's test approach (per spec section 2, "Out of scope").

- [ ] **Step 1: Write the failing tests**

Create `tests/test_bedrock_check.py`:
```python
from scripts.bedrock_check import build_request_body, extract_reply_text


def test_build_request_body_has_correct_shape():
    body = build_request_body("Hello there")

    assert body == {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 50,
        "messages": [{"role": "user", "content": "Hello there"}],
    }


def test_extract_reply_text_returns_the_text_field():
    response_body = {
        "content": [{"type": "text", "text": "Hello world today."}]
    }

    assert extract_reply_text(response_body) == "Hello world today."
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:
```bash
pytest tests/test_bedrock_check.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.bedrock_check'` (or similar), because `scripts/bedrock_check.py` doesn't exist yet.

- [ ] **Step 3: Write the minimal implementation**

Create `scripts/__init__.py` (empty file — marks `scripts/` as a package, matching the existing `app/__init__.py` / `tests/__init__.py` pattern from Step 1).

Create `scripts/bedrock_check.py`:
```python
import json

import boto3

MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
REGION = "us-east-1"
TEST_MESSAGE = "Say hello in exactly 3 words."


def build_request_body(message: str) -> dict:
    return {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 50,
        "messages": [{"role": "user", "content": message}],
    }


def extract_reply_text(response_body: dict) -> str:
    return response_body["content"][0]["text"]


def main() -> None:
    client = boto3.client("bedrock-runtime", region_name=REGION)
    body = build_request_body(TEST_MESSAGE)

    response = client.invoke_model(
        modelId=MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body),
    )

    response_body = json.loads(response["body"].read())
    reply = extract_reply_text(response_body)

    print(f"Sent: {TEST_MESSAGE}")
    print(f"Bedrock replied: {reply}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the tests and verify they pass**

Run:
```bash
pytest tests/test_bedrock_check.py -v
```

Expected: PASS — both `test_build_request_body_has_correct_shape` and `test_extract_reply_text_returns_the_text_field` show PASSED.

- [ ] **Step 5: Run the full test suite**

Run:
```bash
pytest -v
```

Expected: PASS — all tests from this task plus Step 1's `test_health_check_returns_ok` show PASSED (3 total).

- [ ] **Step 6: Manually run the script against real Bedrock**

Run:
```bash
source venv/bin/activate
python -m scripts.bedrock_check
```

Expected: prints two lines, e.g.:
```
Sent: Say hello in exactly 3 words.
Bedrock replied: <some short AI-generated greeting>
```
No stack trace, no credential values printed. If this fails with an AWS error, stop and report it — do not modify AWS credentials or account settings; that is the user's domain.

- [ ] **Step 7: Commit**

```bash
git add scripts tests/test_bedrock_check.py
git commit -m "feat: standalone script proving Bedrock connectivity"
```

Expected: `git log --oneline -1` shows the new commit.
