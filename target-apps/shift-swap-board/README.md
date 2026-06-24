# Shift Swap Board

Internal tool for posting, claiming, and approving shift swaps with atomic roster updates and an append-only audit log.

## Tech Stack

- **Backend:** Python 3.12 + FastAPI + SQLAlchemy 2.x
- **Database:** PostgreSQL (RDS) with schema `shift_swap_board`
- **Auth:** JWT (HS256) via PyJWT + bcrypt
- **UI:** Streamlit (port 8501)

## Quick Start

### Prerequisites

- Python 3.12+
- PostgreSQL (RDS or local Docker)

### Setup

```bash
cd target-apps/shift-swap-board

# Create virtual environment
python -m venv .venv

# Activate (Windows PowerShell)
.venv\Scripts\Activate.ps1

# Activate (Linux/Mac)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Environment Configuration

```bash
cp .env.example .env
```

**Important:** Every line in `.env` must be `KEY=value` format. Do NOT paste a bare URL without `DATABASE_URL=`.

Required variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | Postgres DSN | `postgresql+psycopg://user:pass@host:5432/db?sslmode=require` |
| `POSTGRES_SCHEMA` | Schema name | `shift_swap_board` |
| `JWT_SECRET_KEY` | Secret for HS256 JWT signing | (random string, min 32 chars) |
| `JWT_EXPIRY_HOURS` | Token lifetime in hours | `8` |
| `API_BASE_URL` | API URL for Streamlit | `http://localhost:8000` |

### Terminal 1 — Start API

```bash
cd target-apps/shift-swap-board
# Activate venv if not already active
uvicorn app.main:app --reload --port 8000 --reload-dir app --reload-dir schemas
```

Open Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)

### Terminal 2 — Start Streamlit UI

```bash
cd target-apps/shift-swap-board
# Activate venv if not already active
cd ui
streamlit run streamlit_app.py --server.port 8501
```

Open UI: [http://localhost:8501](http://localhost:8501)

## Seed Data / Demo Logins

After DB migration, the seed creates:

| Username | Password | Role |
|----------|----------|------|
| `admin` | `Password1!` | admin |
| `lead_a` | `Password1!` | floor_lead |
| `lead_b` | `Password1!` | floor_lead |
| `staff_01` | `Password1!` | staff |
| `staff_02` | `Password1!` | staff |
| `staff_03` | `Password1!` | staff |

> **Note:** RDS passwords are applied during pipeline DB apply (bcrypt hashes materialized automatically by `materialize_seed_passwords.py`).

## Swagger Auth

1. `POST /auth/login` with `{"username": "admin", "password": "Password1!"}`
2. Copy the `access_token` from the response
3. Click "Authorize" in Swagger and enter: `Bearer <token>`

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/login` | Public | Get JWT token |
| GET | `/health` | Public | Health check |
| GET | `/roster` | All roles | List shifts |
| GET | `/roster/mine` | All roles | My shifts |
| GET | `/swaps` | All roles | List swaps |
| POST | `/swaps` | Staff | Create swap offer |
| POST | `/swaps/{id}/claim` | Staff | Claim a swap |
| POST | `/swaps/{id}/approve` | Floor Lead | Approve swap |
| POST | `/swaps/{id}/deny` | Floor Lead | Deny swap |
| POST | `/swaps/{id}/cancel` | Offerer | Cancel swap |
| GET | `/swaps/{id}/audit` | Admin/Lead | Swap audit |
| GET | `/audit` | Admin | Global audit |
| GET | `/floor-leads` | Admin | List assignments |
| POST | `/floor-leads` | Admin | Assign lead |

## Running Tests

```bash
cd target-apps/shift-swap-board
pytest tests/ -q
```

Tests use in-memory SQLite and do NOT require a running Postgres instance.

## RDS Smoke Test

With `.env` configured for RDS:

```bash
curl http://localhost:8000/health
# Expected: {"status":"ok","checks":{"api":"ok","database":"ok"}}
```

## Project Structure

```
app/
  main.py              # FastAPI app entry point
  config.py            # Settings from env
  database.py          # SQLAlchemy engine/session
  startup_checks.py    # Fail-fast validation
  dependencies.py      # Auth + DB deps
  security.py          # JWT + bcrypt
  models/              # ORM models
  routers/             # API route handlers
schemas/               # Pydantic request/response models
tests/                 # pytest suite
ui/
  streamlit_app.py     # Streamlit frontend
  requirements.txt     # UI-specific deps
db/sql/                # DDL migrations (read-only)
```
