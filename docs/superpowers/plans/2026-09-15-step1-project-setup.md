# Step 1: Project Setup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the Mini ECHO backend project skeleton — a FastAPI app, managed by a Python virtual environment, with one working `/health` endpoint proven by an automated test.

**Architecture:** A single FastAPI application (`app/main.py`) served by Uvicorn. This task adds no AI logic and no frontend — it only proves the backend project itself boots and responds, which every later step (Bedrock call, `/chat` endpoint, persona, frontend) builds on top of.

**Tech Stack:** Python 3, FastAPI, Uvicorn, pytest, httpx (test client dependency for FastAPI's `TestClient`)

**Spec:** `/Users/abdulrahman/Desktop/Mini_Echo_MVP/PROJECT.md`

## Global Constraints

- Language: Python 3, dependencies managed via `venv` + `pip` (per spec section 4)
- Web framework: FastAPI, served by Uvicorn (per spec section 4)
- Backend must remain stateless — no server-side session storage, no database (per spec section 1 and "in scope"/"out of scope")
- AI provider will be AWS Bedrock via `boto3` starting in Step 2 — not used in this task, but `boto3` is installed now so the environment doesn't need touching again next step
- Frontend (later steps) will be plain HTML/CSS/JS only — no frontend frameworks or build tools (per spec section 4)
- Project runs locally only, single user (per spec "in scope")

---

### Task 1: FastAPI Project Skeleton with Health Check

**Files:**
- Create: `requirements.txt`
- Create: `app/__init__.py`
- Create: `app/main.py`
- Create: `tests/__init__.py`
- Create: `tests/test_main.py`
- Create: `.gitignore`

**Interfaces:**
- Produces: `app.main:app` — a FastAPI application instance, importable as `from app.main import app`. Later steps (Task for the `/chat` endpoint) will add routes to this same `app` object in `app/main.py`.
- Produces: `GET /health` route returning JSON `{"status": "ok"}` with HTTP 200 — a convention later steps can reuse to check the server is alive.

- [ ] **Step 1: Create the project folder structure and a virtual environment**

Run:
```bash
cd /Users/abdulrahman/Desktop/Mini_Echo_MVP
mkdir -p app tests
python3 -m venv venv
source venv/bin/activate
```

Expected: prompt now shows `(venv)`, and `app/` and `tests/` directories exist.

- [ ] **Step 2: Write `requirements.txt` and install dependencies**

Create `requirements.txt`:
```
fastapi>=0.115
uvicorn[standard]>=0.32
boto3>=1.35
pytest>=8.3
httpx>=0.27
```

Run:
```bash
pip install -r requirements.txt
```

Expected: install completes with no errors.

- [ ] **Step 3: Write the failing test**

Create `tests/__init__.py` (empty file — marks `tests/` as a package so pytest can import from it consistently).

Create `tests/test_main.py`:
```python
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check_returns_ok():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 4: Run the test and verify it fails**

Run:
```bash
pytest tests/test_main.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.main'` (or similar), because `app/main.py` doesn't exist yet.

- [ ] **Step 5: Write the minimal FastAPI app**

Create `app/__init__.py` (empty file — marks `app/` as a package).

Create `app/main.py`:
```python
from fastapi import FastAPI

app = FastAPI()


@app.get("/health")
def health_check():
    return {"status": "ok"}
```

- [ ] **Step 6: Run the test and verify it passes**

Run:
```bash
pytest tests/test_main.py -v
```

Expected: PASS — `test_health_check_returns_ok PASSED`.

- [ ] **Step 7: Manually run the server and check it in a browser**

Run:
```bash
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/health` in a browser.

Expected: page shows `{"status":"ok"}`. Stop the server afterward with `Ctrl+C`.

- [ ] **Step 8: Add `.gitignore`**

Create `.gitignore`:
```
venv/
__pycache__/
*.pyc
.pytest_cache/
.env
```

- [ ] **Step 9: Commit**

```bash
cd /Users/abdulrahman/Desktop/Mini_Echo_MVP
git add app tests requirements.txt .gitignore PROJECT.md docs
git commit -m "feat: project skeleton with health check endpoint"
```

Expected: `git log --oneline -1` shows the new commit.
