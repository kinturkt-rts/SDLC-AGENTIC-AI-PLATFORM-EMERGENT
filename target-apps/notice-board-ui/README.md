# Team Notice Board

## Overview

Persistent company notice board with:
- **FastAPI** backend — REST API + OpenAPI at `/docs`
- **Streamlit** UI — browser-based interface for browsing and management
- **PostgreSQL** (AWS RDS) — notices, categories, audit log

---

## Quick Start (Local Development)

### Prerequisites
- Python 3.12+
- An accessible PostgreSQL database (see DB Setup below) OR use a local Postgres instance

### Step 1 — Clone & set up environment

```bash
# From repo root
cd target-apps/notice-board-ui

# Create virtualenv
python -m venv .venv

# Activate (Windows PowerShell)
.venv\Scripts\Activate.ps1

# Activate (macOS / Linux)
source .venv/bin/activate

# Install backend dependencies
pip install -r requirements.txt
```

### Step 2 — Configure environment

```bash
# Copy the example env file
cp .env.example .env
```

Open `.env` and fill in your values:

```dotenv
# IMPORTANT: every line must start with KEY= — never paste a bare URL
DATABASE_URL=postgresql+psycopg://user:password@your-rds-host.rds.amazonaws.com:5432/your_db?sslmode=require
POSTGRES_SCHEMA=notice_board_ui
ORGANIZER_SECRET=your-strong-secret-here
API_BASE_URL=http://localhost:8000
```

> ⚠️ **Common mistake**: If you already have `DATABASE_URL` set in your shell from a previous
> session, it will override `.env`. Fix with:
> - PowerShell: `Remove-Item Env:DATABASE_URL`
> - Bash: `unset DATABASE_URL`

### Step 3 — Apply database migrations

SQL migrations live in `db/sql/`. Apply them in order to your Postgres instance:

```sql
-- Run these in psql or via the pipeline DB apply script:
-- 001_create_schema_and_categories.sql
-- 002_create_notices.sql
-- 003_create_audit_log.sql
-- 004_seed_data.sql
```

The seed data inserts default categories: **General, HR, IT, Events, Finance** plus sample notices.

---

## Running the Application

### Terminal 1 — FastAPI Backend

```bash
cd target-apps/notice-board-ui
# (activate .venv if not already)
uvicorn app.main:app --reload --port 8000 --reload-dir app --reload-dir schemas
```

API is live at: http://localhost:8000
OpenAPI docs: http://localhost:8000/docs
Health check: http://localhost:8000/health

### Terminal 2 — Streamlit UI

```bash
cd target-apps/notice-board-ui
# (activate .venv if not already)
cd ui
pip install -r requirements.txt
streamlit run streamlit_app.py --server.port 8501
```

UI is live at: http://localhost:8501

---

## API Reference

### Authentication

Write operations (POST/PUT/DELETE) require the `X-Organizer-Secret` header:

```
X-Organizer-Secret: your-strong-secret-here
```

Read operations (GET) are public — no authentication required.

### Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | — | System health + DB ping |
| GET | `/api/v1/notices` | — | List active notices (filtered, paginated) |
| POST | `/api/v1/notices` | ✅ organizer | Create a notice |
| PUT | `/api/v1/notices/{id}` | ✅ organizer | Update a notice |
| DELETE | `/api/v1/notices/{id}/archive` | ✅ organizer | Archive a notice |
| GET | `/api/v1/categories` | — | List all categories |
| POST | `/api/v1/categories` | ✅ organizer | Create a category |

### Query parameters for `GET /api/v1/notices`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `category_id` | int | — | Filter by category |
| `search` | string | — | Case-insensitive search in title and body |
| `page` | int | 1 | Page number (1-based) |
| `limit` | int | 20 | Results per page (max 100) |

### Swagger / OpenAPI

Visit http://localhost:8000/docs for the interactive API explorer.

To test protected endpoints via Swagger:
1. Open `/docs`
2. Click **Authorize** (lock icon, top right)
3. There is no built-in Swagger auth widget for header-based secrets —
   instead use the **"Try it out"** on each endpoint and add the header manually.

Or use curl:

```bash
# List active notices
curl http://localhost:8000/api/v1/notices

# Create a notice
curl -X POST http://localhost:8000/api/v1/notices \
  -H "Content-Type: application/json" \
  -H "X-Organizer-Secret: your-strong-secret-here" \
  -d '{"title":"Hello World","body":"First notice!","author_display_name":"Morgan"}'

# Archive a notice
curl -X DELETE http://localhost:8000/api/v1/notices/1/archive \
  -H "X-Organizer-Secret: your-strong-secret-here"
```

---

## Seed Data

After applying `004_seed_data.sql`, the following categories and notices are available:

**Categories:** General (1), HR (2), IT (3), Events (4), Finance (5)

**Sample Notices:** 8 sample notices with mix of active and archived entries.

No passwords or user accounts — the organizer secret is set via `ORGANIZER_SECRET` env var.

---

## Running Tests

```bash
cd target-apps/notice-board-ui
# (activate .venv if not already)
pytest tests/ -v
```

Tests use SQLite in-memory — no Postgres connection needed for tests.

```bash
# With coverage
pytest tests/ --cov=app --cov=schemas --cov-report=term-missing
```

### RDS Smoke Test (after deploying with real .env)

```bash
curl -s http://localhost:8000/health | python -m json.tool
# Expected: {"status": "ok", "checks": {"api": "ok", "database": "ok"}}
```

---

## Project Structure

```
target-apps/notice-board-ui/
├── app/
│   ├── main.py              # FastAPI app factory + router registration
│   ├── config.py            # pydantic-settings config (reads .env)
│   ├── database.py          # SQLAlchemy engine + session factory
│   ├── dependencies.py      # Auth dependency (organizer secret)
│   ├── startup_checks.py    # Fail-fast env validation
│   ├── models/
│   │   ├── category.py      # Category ORM model
│   │   ├── notice.py        # Notice ORM model
│   │   └── audit_log.py     # AuditLog ORM model
│   ├── routers/
│   │   ├── health.py        # GET /health
│   │   ├── notices.py       # /api/v1/notices routes
│   │   └── categories.py    # /api/v1/categories routes
│   └── services/
│       └── audit.py         # Audit log helper
├── schemas/
│   ├── notice.py            # Notice request/response schemas
│   └── category.py          # Category request/response schemas
├── ui/
│   ├── streamlit_app.py     # Streamlit browser UI
│   └── requirements.txt     # Streamlit UI dependencies
├── tests/
│   ├── conftest.py          # SQLite test engine + fixtures
│   ├── test_health.py       # Health endpoint tests
│   ├── test_notices.py      # Notice CRUD tests
│   └── test_categories.py   # Category CRUD tests
├── db/
│   └── sql/                 # Migration + seed SQL files
├── .env.example             # Environment variable template
├── pytest.ini               # pytest configuration
└── requirements.txt         # Backend Python dependencies
```

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | ✅ | — | PostgreSQL DSN: `postgresql+psycopg://user:pass@host/db?sslmode=require` |
| `POSTGRES_SCHEMA` | ✅ | `notice_board_ui` | Postgres schema name |
| `ORGANIZER_SECRET` | ✅ | — | Shared secret for write operations |
| `APP_ENV` | — | `development` | `development` / `production` / `test` |
| `LOG_LEVEL` | — | `INFO` | Logging level |
| `API_BASE_URL` | — | `http://localhost:8000` | Used by Streamlit UI to call the API |
| `CORS_ORIGINS` | — | `["*"]` | Allowed CORS origins (JSON array) |

---

## Open Questions

1. Organizer secret rotation process — DevOps/Security team
2. Should archived notices be exportable? — Product team
3. Database performance targets as notice volume grows — Engineering team
