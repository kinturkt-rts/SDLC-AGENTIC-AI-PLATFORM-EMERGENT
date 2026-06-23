# Change Request Hub

Role-aware IT change management application with full lifecycle tracking, blackout enforcement, and audit trails.

## Architecture

- **Backend:** Python 3.12 + FastAPI + SQLAlchemy 2.x + PostgreSQL (RDS)
- **Frontend:** Streamlit (HTTP client to API only — never imports `app/`)
- **Auth:** JWT Bearer tokens (HS256) via `POST /api/v1/auth/token`
- **Database:** PostgreSQL ≥ 15 with schema `change_request_hub`

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 15+ (or use the provisioned RDS instance)

### Setup

```bash
# From repo root
cd target-apps/change-request-hub

# Create virtual environment
python -m venv .venv

# Activate (PowerShell on Windows; see comment for Linux/macOS)
.venv\Scripts\Activate.ps1   # Linux/macOS: source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file — EVERY line MUST be KEY=value
cp .env.example .env
# Edit .env: fill in your real DATABASE_URL and JWT_SECRET_KEY
# Example: DATABASE_URL=postgresql+psycopg://user:pass@host:5432/sdlc_agentic_ai?sslmode=require
# WARNING: do NOT paste a bare URL without the DATABASE_URL= prefix
```

### Terminal 1 — API Server

```bash
cd target-apps/change-request-hub
.venv\Scripts\Activate.ps1   # Linux/macOS: source .venv/bin/activate
uvicorn app.main:app --reload --reload-dir app --reload-dir schemas --port 8000
```

API docs: http://localhost:8000/docs

### Terminal 2 — Streamlit UI

```bash
cd target-apps/change-request-hub
.venv\Scripts\Activate.ps1   # Linux/macOS: source .venv/bin/activate
cd ui
streamlit run streamlit_app.py --server.port 8501
```

UI: http://localhost:8501

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL DSN: `postgresql+psycopg://user:pass@host:5432/db?sslmode=require` |
| `POSTGRES_SCHEMA` | Yes | `change_request_hub` |
| `JWT_SECRET_KEY` | Yes | Secret key for signing JWTs — must be strong |
| `JWT_ALGORITHM` | No | Default: `HS256` |
| `JWT_EXPIRE_MINUTES` | No | Default: `480` (8 hours) |
| `APP_ENV` | No | `development` / `production` / `test` |
| `API_BASE_URL` | No (UI) | Default: `http://localhost:8000` — for Streamlit |

## Seed Users & Credentials

All seed users share the password: **`ChangeMe123!`**

| Email | Role | UUID |
|-------|------|------|
| `sam.manager@example.com` | manager | `a1000000-0000-0000-0000-000000000001` |
| `alice.req@example.com` | requester | `a1000000-0000-0000-0000-000000000002` |
| `bob.req@example.com` | requester | `a1000000-0000-0000-0000-000000000003` |
| `charlie.impl@example.com` | implementer | `a1000000-0000-0000-0000-000000000004` |
| `diana.impl@example.com` | implementer | `a1000000-0000-0000-0000-000000000005` |
| `exec.leader@example.com` | leadership | `a1000000-0000-0000-0000-000000000006` |

> **Note:** RDS seed passwords are materialized during pipeline DB apply. Run manually if needed:
> ```bash
> python agents/_shared/materialize_seed_passwords.py --target-app change-request-hub
> ```

## Role & Endpoint Quick Reference

| Role | Key Endpoints | Actions |
|------|---------------|---------|
| **Manager** (`sam.manager@example.com`) | `POST/GET /api/v1/services`, `POST/GET /api/v1/environments`, `POST/GET /api/v1/blackout-windows`, `PATCH .../status` (approve/reject/schedule/close), `PATCH .../assign`, `GET /api/v1/dashboard/summary` | Full catalog CRUD, approve/reject/schedule/close changes, assign implementers, view dashboard |
| **Requester** (`alice.req@example.com`) | `POST /api/v1/change-requests`, `PATCH .../status` (submit), `GET/POST .../comments` (own) | Create changes, submit for approval, comment on own |
| **Implementer** (`charlie.impl@example.com`) | `PATCH .../status` (implementing→completed), `GET/POST .../comments` (assigned) | Start/complete assigned changes, add comments |
| **Leadership** (`exec.leader@example.com`) | `GET /api/v1/dashboard/summary`, `GET /api/v1/change-requests` (read-only) | View dashboard and list all changes |

## Swagger Auth Header

1. Open http://localhost:8000/docs
2. Use "Try it out" on `POST /api/v1/auth/token` with:
   ```json
   {"email": "sam.manager@example.com", "password": "ChangeMe123!"}
   ```
3. Copy the `access_token` from the response
4. Click "Authorize" (top-right lock icon) and enter: `Bearer <your_token>`

## RDS Smoke Test

After setting `.env` with real RDS credentials:

```bash
# Health check (no auth required)
curl http://localhost:8000/health

# List services (requires JWT)
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"email":"sam.manager@example.com","password":"ChangeMe123!"}' | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/services
```

## Running Tests

```bash
cd target-apps/change-request-hub
pytest tests/ -q
```

Tests use SQLite in-memory — no PostgreSQL required for test suite.

## Project Structure

```
app/
├── main.py              # FastAPI application
├── config.py            # Settings from .env
├── database.py          # SQLAlchemy engine + session
├── startup_checks.py    # Fail-fast runtime validation
├── dependencies.py      # Auth + DB dependencies
├── security.py          # JWT + bcrypt utilities
├── models/              # SQLAlchemy ORM models
│   ├── user.py
│   ├── service.py
│   ├── environment.py
│   ├── blackout_window.py
│   ├── change_request.py
│   ├── approval_record.py
│   ├── comment.py
│   └── status_history.py
├── routers/             # FastAPI route handlers
│   ├── health.py
│   ├── auth.py
│   ├── services.py
│   ├── environments.py
│   ├── blackout_windows.py
│   ├── change_requests.py
│   ├── comments.py
│   ├── dashboard.py
│   └── users.py
schemas/                 # Pydantic request/response schemas
├── auth.py
├── service.py
├── environment.py
├── blackout_window.py
├── change_request.py
├── comment.py
├── dashboard.py
└── user.py
tests/                   # Pytest suite
ui/
└── streamlit_app.py     # Streamlit frontend
```
