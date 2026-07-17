# Field Service Dispatch

Role-aware dispatch application for a 15-technician HVAC shop. Replaces whiteboard/text-thread workflow with a structured API + Streamlit UI.

## Features

- **Customer Management** — CRUD with soft-delete
- **Technician Roster** — skills, active/inactive status
- **Work Order Lifecycle** — new → assigned → in_progress → completed/cancelled
- **Assignment Engine** — one active tech per order, reassignment support
- **SLA Breach Detection** — urgent orders flagged after 17:00 UTC cutoff
- **Audit Log** — append-only status-change history
- **Role-Based Access** — dispatcher (full), technician (own jobs), owner (read-only)
- **Streamlit UI** — dispatcher board, technician "My Jobs Today", owner dashboard

## Demo Accounts

| Username | Password | Role | Notes |
|----------|----------|------|-------|
| `dana_dispatch` | `FieldService2024!` | dispatcher | Full CRUD access |
| `carlos_tech` | `FieldService2024!` | technician | Linked to Carlos Mendez tech record |
| `frank_owner` | `FieldService2024!` | owner | Read-only board access |

## Role & Endpoint Quick Reference

| Role | Endpoints | Permissions |
|------|-----------|-------------|
| dispatcher | All `/api/v1/*` | Full CRUD on customers, technicians, work orders, assignments; addendum on completed; board + audit log |
| technician | `GET /api/v1/work-orders`, `PATCH /api/v1/work-orders/{id}/status` | View own assigned orders; advance status (assigned→in_progress→completed) |
| owner | `GET /api/v1/board`, `GET /api/v1/work-orders/{id}/audit-log`, `GET /api/v1/customers`, `GET /api/v1/technicians` | Read-only on all resources; 403 on any mutation |

## Setup

### Prerequisites

- Python 3.12+
- Access to RDS Postgres (or local Postgres)

### Terminal 1 — API Server

**Windows (PowerShell):**
```powershell
cd target-apps/field-service-dispatch
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# Edit .env: set DATABASE_URL and API_KEY
uvicorn app.main:app --reload --port 8000 --reload-dir app --reload-dir schemas
```

**Bash (Linux/macOS):**
```bash
cd target-apps/field-service-dispatch
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env: set DATABASE_URL and API_KEY
uvicorn app.main:app --reload --port 8000 --reload-dir app --reload-dir schemas
```

> **Important:** Every `.env` line needs the variable name — paste `DATABASE_URL=postgresql+psycopg://...`, not a bare URL.

### Terminal 2 — Streamlit UI

**Windows (PowerShell):**
```powershell
cd target-apps/field-service-dispatch
.venv\Scripts\Activate.ps1
cd ui
pip install -r requirements.txt
streamlit run streamlit_app.py --server.port 8501
```

**Bash (Linux/macOS):**
```bash
cd target-apps/field-service-dispatch
source .venv/bin/activate
cd ui
pip install -r requirements.txt
streamlit run streamlit_app.py --server.port 8501
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | Postgres DSN: `postgresql+psycopg://user:pass@host:5432/db?sslmode=require` |
| `POSTGRES_SCHEMA` | Yes | Schema name: `field_service_dispatch` |
| `API_KEY` | Yes | Shared secret for Streamlit/testing (set after first login via `/api/v1/auth/token`) |
| `APP_ENV` | No | `development` (default) / `production` / `test` |
| `SLA_CUTOFF_HOUR` | No | Hour (0-23) when SLA breach triggers (default: 17) |
| `AWS_REGION` | No | AWS region (default: us-east-2) |

## API Authentication

1. Call `POST /api/v1/auth/token` with `{"username": "...", "password": "..."}` to get an `access_token`
2. Use the token as `X-API-Key: <token>` header on all subsequent requests
3. In Swagger UI (`http://localhost:8000/docs`): click "Authorize" and add header `X-API-Key: <your-token>`

## Seed Data UUIDs

| Entity | ID (prefix) | Name |
|--------|-------------|------|
| Technician | `a0000001-...-01` | Carlos Mendez |
| Technician | `a0000001-...-02` | Janice Park |
| Customer | `b0000001-...-01` | Lakewood Medical Center |
| User | `c0000001-...-01` | dana_dispatch |
| Work Order | `d0000001-...-01` | Annual HVAC maintenance |

## RDS Smoke Test

1. Verify health:
```bash
curl http://localhost:8000/health
# Expected: {"status":"ok","checks":{"api":"ok","database":"ok"}}
```

2. Login and get token:
```bash
curl -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"username":"dana_dispatch","password":"FieldService2024!"}'
```

3. List customers (use token from step 2):
```bash
curl http://localhost:8000/api/v1/customers \
  -H "X-API-Key: <token-from-step-2>"
```

4. Get dispatch board:
```bash
curl "http://localhost:8000/api/v1/board?date=$(date +%Y-%m-%d)" \
  -H "X-API-Key: <token>"
```

## Running Tests

```bash
cd target-apps/field-service-dispatch
pip install -r requirements.txt
pytest tests/ -q
```

Tests use an in-memory SQLite database and do not require RDS connectivity.
