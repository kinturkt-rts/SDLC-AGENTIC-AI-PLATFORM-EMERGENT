# Expense Tracker — Internal API

FastAPI + PostgreSQL REST API for logging, approving, and reporting on employee business expenses.

## Features

- **Employees**: Submit, edit, and soft-delete expenses with automatic multi-currency → USD conversion
- **Managers**: View monthly team aggregation reports (approved expenses only)
- **Admins**: Manage teams, assign employees, approve/reject expenses
- **Audit Log**: Every status transition is recorded with actor and timestamp
- **Health**: `GET /health` with real DB ping (503 on failure)

## Quick Start

### 1. Clone & setup virtual environment

**PowerShell (Windows):**
```powershell
cd target-apps/expense-tracker
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**Bash (macOS/Linux):**
```bash
cd target-apps/expense-tracker
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` with your RDS credentials. **Every line must be `KEY=value` format** — never paste a bare URL without `DATABASE_URL=`.

Example:
```
DATABASE_URL=postgresql+psycopg://postgres:yourpassword@agenticaidbinstance.c1u0cggiolxp.us-east-2.rds.amazonaws.com:5432/sdlc_agentic_ai?sslmode=require
```

### 3. Run the API (Terminal 1)

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Access Swagger UI at: http://localhost:8000/docs

### 4. Run tests

```bash
pytest tests/ -q
```

## Authentication

This API uses **two auth mechanisms** (no JWT):

| Actor | Header | Format |
|-------|--------|--------|
| Employee | `Authorization` | `Bearer <token>` |
| Manager | `X-Api-Key` | `<api-key>` |
| Admin | `X-Api-Key` | `<api-key>` |

Tokens and API keys are SHA-256 hashed and stored in `employees.token_hash` and `api_keys.key_hash` respectively.

### Swagger Auth

- For employee routes: Click "Authorize" and enter bearer token
- For manager/admin routes: Add `X-Api-Key` header in individual requests or use curl

## Demo Accounts (Seed Data)

| Role | Name | ID | Team |
|------|------|----|------|
| Employee | Alice Johnson | employees.id=1 | Engineering |
| Employee | Bob Smith | employees.id=2 | Engineering |
| Employee | Carol Davis | employees.id=3 | Finance |
| Manager | Manager - Engineering | api_keys.id=1 | Engineering |
| Admin | Admin - Global | api_keys.id=2 | All teams |

> **Note**: Seed plaintext passwords: `DevToken123!` (employee tokens), `DevApiKey456!` (API keys).

## Role & Endpoint Quick Reference

| Endpoint | Allowed Role(s) | Notes |
|----------|-----------------|-------|
| `POST /api/v1/expenses` | employee | Submit expense |
| `PATCH /api/v1/expenses/{id}` | employee (owner) | Edit submitted only |
| `DELETE /api/v1/expenses/{id}` | employee (owner) | Soft-delete submitted only |
| `GET /api/v1/expenses` | employee | Own expenses, filterable |
| `GET /api/v1/expenses/{id}` | employee (owner), admin | Single expense |
| `GET /api/v1/expenses/{id}/audit-log` | employee (owner), admin, manager | Audit trail |
| `POST /api/v1/expenses/{id}/approve` | admin | submitted → approved |
| `POST /api/v1/expenses/{id}/reject` | admin | submitted → rejected |
| `POST /api/v1/teams` | admin | Create team |
| `GET /api/v1/teams` | admin | List all teams |
| `PUT /api/v1/employees/{id}/team` | admin | Assign employee to team |
| `GET /api/v1/teams/{team_id}/report?year=&month=` | manager (scoped), admin | Monthly aggregation |
| `GET /health` | public | Health check with DB ping |
| `GET /api/v1/health` | public | Health check (versioned) |

## RDS Smoke Test

After configuring `.env` with valid RDS credentials:

```bash
# 1. Health check
curl http://localhost:8000/health
# Expected: {"status":"ok","checks":{"api":"ok","database":"ok"}}

# 2. List teams (requires admin API key)
curl -H "X-Api-Key: <your-admin-key>" http://localhost:8000/api/v1/teams
```

## Project Structure

```
app/
├── __init__.py
├── config.py           # Settings from .env
├── database.py         # SQLAlchemy engine + session
├── startup_checks.py   # Runtime validation
├── dependencies.py     # Auth + DI
├── main.py             # FastAPI app entry point
├── models/             # SQLAlchemy ORM models
│   ├── team.py
│   ├── employee.py
│   ├── api_key.py
│   ├── fx_rate_snapshot.py
│   ├── expense.py
│   └── audit_log.py
└── routers/
    ├── health.py       # GET /health
    ├── health_v1.py    # GET /api/v1/health
    ├── expenses.py     # Expense CRUD + approve/reject + audit-log
    ├── teams.py        # Team management + report
    └── employees.py    # Employee team assignment
schemas/                # Pydantic request/response models
tests/                  # pytest integration tests
db/sql/                 # DDL migrations + seed (read-only)
```
