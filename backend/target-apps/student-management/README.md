# Student Management API

Centralised internal REST API for student record management, replacing disconnected spreadsheets with a single authoritative PostgreSQL-backed service.

## Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI (Python 3.12) |
| UI | Streamlit (calls API over HTTP) |
| Auth | API-key (`X-API-Key` header) — two-tier: read + write |
| ORM | SQLAlchemy 2.x |
| DB | PostgreSQL (RDS) — schema `student_management` |
| Driver | psycopg (v3) |

## Quick Start

### Prerequisites

- Python 3.12+
- Access to the RDS Postgres instance (or a local Postgres)

### 1. Clone & create virtual environment

**PowerShell (Windows):**
```powershell
cd target-apps/student-management
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**Bash (macOS/Linux):**
```bash
cd target-apps/student-management
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and fill in your actual values:

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | `postgresql+psycopg://user:pass@host:5432/sdlc_agentic_ai?sslmode=require` |
| `POSTGRES_SCHEMA` | `student_management` |
| `WRITE_API_KEY` | Secret key for write operations (POST/PUT/PATCH) |
| `READ_API_KEY` | Secret key for read operations (GET) — write key also accepted |

> **IMPORTANT:** Every line in `.env` must be `KEY=value` — do NOT paste a bare URL without the `DATABASE_URL=` prefix.

### 3. Terminal 1 — Start the API

**PowerShell:**
```powershell
cd target-apps/student-management
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000 --reload-dir app --reload-dir schemas
```

**Bash:**
```bash
cd target-apps/student-management
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000 --reload-dir app --reload-dir schemas
```

API docs: http://localhost:8000/docs

### 4. Terminal 2 — Start Streamlit UI

**PowerShell:**
```powershell
cd target-apps/student-management
.\.venv\Scripts\Activate.ps1
cd ui
pip install -r requirements.txt
streamlit run streamlit_app.py --server.port 8501
```

**Bash:**
```bash
cd target-apps/student-management
source .venv/bin/activate
cd ui
pip install -r requirements.txt
streamlit run streamlit_app.py --server.port 8501
```

UI: http://localhost:8501 — enter your API key in the sidebar.

## Auth & Endpoint Quick Reference

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/health` | GET | None | Health check + DB ping |
| `/api/v1/students` | GET | Read key | List students (filter: `?course=`, `?status=`) |
| `/api/v1/students/{student_id}` | GET | Read key | Get single student |
| `/api/v1/students` | POST | Write key | Create student |
| `/api/v1/students/{student_id}` | PUT | Write key | Update student |
| `/api/v1/students/{student_id}/deactivate` | PATCH | Write key | Soft-delete (deactivate) |
| `/api/v1/students/seed` | POST | Write key | Insert demo data |

### Swagger Auth

1. Open http://localhost:8000/docs
2. Click **Authorize** or add header manually: `X-API-Key: <your-write-or-read-key>`
3. For write operations, use `WRITE_API_KEY`
4. For read operations, use `READ_API_KEY` (write key also works)

## Seed Data

After the database is provisioned, the following demo records exist (from `011_seed.sql`):

| student_id | full_name | email | course | status |
|-----------|-----------|-------|--------|--------|
| STU-001 | Alice Nguyen | alice@example.com | Computer Science | active |
| STU-002 | Ben Carter | ben@example.com | Data Engineering | active |
| STU-003 | Cleo Marsh | cleo@example.com | Cybersecurity | inactive |
| STU-004 | Diana Patel | diana@example.com | Computer Science | active |
| STU-005 | Evan Brooks | evan@example.com | Data Engineering | active |
| STU-006 | Fiona Lee | fiona@example.com | Cybersecurity | active |
| STU-007 | George Kim | george@example.com | Computer Science | inactive |

You can also call `POST /api/v1/students/seed` (with write key) to insert the first 3 demo records idempotently.

## RDS Smoke Test

After `.env` is configured with real RDS credentials:

```bash
# 1. Health check (no auth)
curl http://localhost:8000/health
# Expected: {"status":"ok","checks":{"api":"ok","database":"ok"}}

# 2. List students (read key)
curl -H "X-API-Key: <READ_API_KEY>" http://localhost:8000/api/v1/students
# Expected: 200 with array of student objects

# 3. Get single student
curl -H "X-API-Key: <READ_API_KEY>" http://localhost:8000/api/v1/students/STU-001
# Expected: 200 with Alice Nguyen's record
```

## Running Tests

```bash
cd target-apps/student-management
pytest tests/ -q
```

Tests use in-memory SQLite — no Postgres or `.env` required.
