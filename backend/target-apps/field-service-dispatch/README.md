# Field Service Dispatch

FastAPI REST service + Streamlit UI for dispatching HVAC field technicians. Replaces whiteboard-based coordination with a structured digital workflow, role-based access (Dispatcher, Technician, Owner), and full audit history.

## Features

- **Dispatch Board** — Visual today's board with unassigned queue, per-technician columns, and SLA breach highlighting
- **Work Order Lifecycle** — Create, assign, start, complete, cancel with state-machine enforcement
- **Role-Based Access** — JWT auth with Dispatcher (full CRUD), Technician (own jobs only), Owner (read-only)
- **Audit Trail** — Immutable status-change history for every work order
- **SLA Breach Detection** — Urgent orders past scheduled date flagged automatically
- **Streamlit UI** — Multi-view interface for all three roles

## Quick Start

### Prerequisites

- Python 3.12+
- PostgreSQL (RDS) or SQLite for local dev/testing

### 1. Clone and navigate

```bash
cd target-apps/field-service-dispatch
```

### 2. Create virtual environment

**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**macOS / Linux:**
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and fill in:
- `DATABASE_URL` — Your PostgreSQL connection string (must start with `DATABASE_URL=`)
- `JWT_SECRET_KEY` — A random secret string (≥32 chars)

> ⚠️ **Every line in `.env` must be `KEY=value`** — never paste a bare URL without the variable name prefix.

### 4. Terminal 1 — Start the API

```bash
cd target-apps/field-service-dispatch
.venv\Scripts\Activate.ps1  # or source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

Open Swagger UI: **http://localhost:8000/docs**

### 5. Terminal 2 — Start the Streamlit UI

```bash
cd target-apps/field-service-dispatch
.venv\Scripts\Activate.ps1  # or source .venv/bin/activate
cd ui
pip install -r requirements.txt
streamlit run streamlit_app.py --server.port 8501
```

Open: **http://localhost:8501**

## Authentication

The API uses JWT Bearer tokens. All endpoints except `POST /auth/token` and `GET /health` require the `Authorization: Bearer <token>` header.

### Swagger UI Auth

1. Open http://localhost:8000/docs
2. Click "Authorize"
3. Use OAuth2 form: enter username/password
4. All subsequent requests will include the token

### Seed Users

> ⚠ **RDS login will fail until seed passwords are materialized.**
> Full pipeline (recommended): `python scripts/apply_sql_to_rds.py --target-app field-service-dispatch`
> Manual (if SQL already applied to RDS): `python agents/_shared/materialize_seed_passwords.py --target-app field-service-dispatch`

| Username | Password | Role |
|----------|----------|------|
| `dana` | `Dispatch123!` | dispatcher |
| `sam` | `Dispatch123!` | dispatcher |
| `owner_pat` | `Dispatch123!` | owner |
| `tech_marcus` | `Dispatch123!` | technician |
| `tech_keisha` | `Dispatch123!` | technician |
| `tech_carlos` | `Dispatch123!` | technician |
| `tech_tanya` | `Dispatch123!` | technician |
| `tech_derek` | `Dispatch123!` | technician |
| `tech_lisa` | `Dispatch123!` | technician |
| `tech_james` | `Dispatch123!` | technician |

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | Public | Health check with DB ping |
| POST | `/auth/token` | Public | Login (form: username, password) |
| POST | `/customers` | Dispatcher | Create customer |
| GET | `/customers/{id}` | Dispatcher, Owner | Get customer |
| PATCH | `/customers/{id}` | Dispatcher | Update customer |
| POST | `/work-orders` | Dispatcher | Create work order |
| GET | `/work-orders/{id}` | All roles | Get work order |
| PATCH | `/work-orders/{id}` | Dispatcher, Technician | Update work order (assign/status/complete/addendum) |
| GET | `/work-orders/{id}/history` | All roles | Audit history |
| GET | `/technicians` | All roles | List technicians |
| GET | `/board` | All roles | Today's dispatch board |
| GET | `/workload` | Dispatcher, Owner | Workload summary |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | _(required)_ | PostgreSQL DSN: `postgresql+psycopg://...?sslmode=require` |
| `POSTGRES_SCHEMA` | `field_service_dispatch` | DB schema name |
| `JWT_SECRET_KEY` | _(required)_ | Secret for signing JWT tokens |
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm |
| `JWT_EXPIRE_MINUTES` | `480` | Token expiry (8 hours) |
| `SLA_BREACH_HOUR` | `17` | Hour (UTC) after which urgent orders are flagged as SLA-breached |
| `APP_ENV` | `development` | `development` shows detailed errors; `production` hides them |
| `AWS_REGION` | `us-east-2` | AWS region for future integrations |

## Running Tests

```bash
cd target-apps/field-service-dispatch
pip install pytest httpx
pytest tests/ -q
```

Tests use in-memory SQLite — no external database required.

## RDS Smoke Test

After configuring `.env` with your real RDS credentials:

```bash
curl http://localhost:8000/health
# Expected: {"status":"ok","checks":{"api":"ok","database":"ok"}}
```

## Project Structure

```
target-apps/field-service-dispatch/
├── app/
│   ├── main.py              # FastAPI application factory
│   ├── config.py            # Settings from environment
│   ├── database.py          # SQLAlchemy engine + session
│   ├── startup_checks.py    # Fail-fast config validation
│   ├── security.py          # JWT + bcrypt utilities
│   ├── dependencies.py      # Auth dependencies (get_current_user, role guards)
│   ├── models/              # SQLAlchemy ORM models
│   │   ├── pg_types.py      # UUID column helper
│   │   ├── user.py
│   │   ├── technician.py
│   │   ├── customer.py
│   │   ├── work_order.py
│   │   └── status_history.py
│   └── routers/             # API route handlers
│       ├── health.py
│       ├── auth.py
│       ├── customers.py
│       ├── technicians.py
│       ├── work_orders.py
│       └── board.py
├── schemas/                  # Pydantic request/response schemas
│   ├── auth.py
│   ├── customer.py
│   ├── technician.py
│   ├── work_order.py
│   ├── history.py
│   └── board.py
├── ui/
│   ├── streamlit_app.py     # Streamlit UI (calls API over HTTP)
│   └── requirements.txt
├── tests/
│   ├── conftest.py          # Test fixtures (SQLite, auth helpers)
│   ├── test_health.py
│   ├── test_auth.py
│   ├── test_customers.py
│   ├── test_technicians.py
│   ├── test_work_orders.py
│   └── test_board.py
├── db/sql/                   # DDL migrations (read-only, applied by pipeline)
├── requirements.txt
├── .env.example
├── .gitignore
├── pytest.ini
└── README.md
```
