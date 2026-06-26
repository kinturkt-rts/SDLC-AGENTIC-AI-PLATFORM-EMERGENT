# IT Asset Lifecycle

Full asset lifecycle management (procurement → assignment → maintenance → retirement) for IT Ops and Finance personas. PostgreSQL backend, FastAPI REST API, Streamlit role-gated UI.

## Quick Start

### Prerequisites

- Python 3.12+
- PostgreSQL (RDS or local) with the `it_asset_lifecycle` schema migrated
- Access to the RDS instance (or a local Postgres for development)

### 1. Clone & setup virtual environment

```bash
cd target-apps/it-asset-lifecycle

# Windows PowerShell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

**Edit `.env`** — every line must be `KEY=value` format:

| Variable | Purpose | Example |
|----------|---------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+psycopg://user:pass@host:5432/sdlc_agentic_ai?sslmode=require` |
| `POSTGRES_SCHEMA` | Schema name | `it_asset_lifecycle` |
| `JWT_SECRET` | HMAC secret for JWT signing | Any strong random string |
| `JWT_TTL_HOURS` | Token expiry (default 8) | `8` |
| `ASSET_ENCRYPTION_KEY` | Fernet key for license encryption | Generate with command below |
| `AWS_REGION` | AWS region | `us-east-2` |

> ⚠️ **Every line needs the variable name** — paste `DATABASE_URL=postgresql+psycopg://...`, not a bare URL.

Generate Fernet key:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 3. Run database migrations

Apply the DDL scripts in order against your Postgres instance:

```bash
psql -h <host> -U <user> -d sdlc_agentic_ai -f db/sql/001_create_users.sql
psql -h <host> -U <user> -d sdlc_agentic_ai -f db/sql/002_create_employees.sql
psql -h <host> -U <user> -d sdlc_agentic_ai -f db/sql/003_create_assets.sql
psql -h <host> -U <user> -d sdlc_agentic_ai -f db/sql/004_create_assignments.sql
psql -h <host> -U <user> -d sdlc_agentic_ai -f db/sql/005_create_assignment_history.sql
psql -h <host> -U <user> -d sdlc_agentic_ai -f db/sql/006_create_indexes.sql
psql -h <host> -U <user> -d sdlc_agentic_ai -f db/sql/011_seed.sql
```

### 4. Start the API (Terminal 1)

```bash
cd target-apps/it-asset-lifecycle
# Ensure .venv is activated
uvicorn app.main:app --reload --port 8000
```

Open Swagger UI: **http://localhost:8000/docs**

### 5. Start Streamlit UI (Terminal 2)

```bash
cd target-apps/it-asset-lifecycle
# Ensure .venv is activated (or use a separate venv with ui/requirements.txt)
pip install -r ui/requirements.txt
streamlit run ui/streamlit_app.py --server.port 8501
```

Open: **http://localhost:8501**

## Seed Users (Dev Credentials)

All seed users share the password: `AssetPass123!`

| Username | Role | Permissions |
|----------|------|-------------|
| `kevin_admin` | `it_admin` | Full access — all endpoints |
| `sarah_staff` | `it_staff` | Assign/return, read assets, alerts |
| `mike_staff` | `it_staff` | Assign/return, read assets, alerts |
| `dana_finance` | `finance_readonly` | Read-only + valuation report |

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/login` | None | Login, get JWT |
| GET | `/health` | None | Health check + DB ping |
| GET | `/assets` | All roles | List assets (filters: type, status, warranty_expiring_within_days) |
| POST | `/assets` | it_admin | Create asset |
| PATCH | `/assets/{id}` | it_admin | Update asset |
| POST | `/assets/{id}/assign` | it_admin, it_staff | Assign asset to employee |
| POST | `/assets/{id}/return` | it_admin, it_staff | Return assigned asset |
| POST | `/assets/{id}/retire` | it_admin | Retire asset |
| PATCH | `/employees/{id}/deactivate` | it_admin | Deactivate employee |
| GET | `/alerts/offboarding` | it_admin, it_staff | Inactive employees with active assets |
| GET | `/alerts/warranty` | All roles | Assets with expiring warranty |
| GET | `/alerts/license-overages` | it_admin, it_staff | License seat violations |
| GET | `/reports/valuation-by-department` | it_admin, finance_readonly | Department cost summary |

## Swagger Authentication

1. Call `POST /auth/login` with username/password
2. Copy the `access_token` from the response
3. Click "Authorize" button in Swagger UI
4. Enter: `Bearer <your-token>`

## Running Tests

```bash
cd target-apps/it-asset-lifecycle
pip install pytest httpx
python -m pytest tests/ -v
```

Tests use an in-memory SQLite database — no Postgres required.

## RDS Smoke Test

After configuring `.env` with real RDS credentials:

```bash
curl http://localhost:8000/health
# Expected: {"status":"ok","checks":{"api":"ok","database":"ok"}}

curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"kevin_admin","password":"AssetPass123!"}'
# Expected: {"access_token":"...","role":"it_admin"}
```

## Architecture

```
target-apps/it-asset-lifecycle/
├── app/
│   ├── main.py              # FastAPI app factory
│   ├── config.py            # Pydantic settings
│   ├── database.py          # SQLAlchemy engine + session
│   ├── startup_checks.py    # Fail-fast env validation
│   ├── security.py          # JWT + bcrypt
│   ├── dependencies.py      # Auth guards + DB dep
│   ├── models/              # SQLAlchemy ORM models
│   ├── routers/             # API route handlers
│   └── services/            # Encryption service
├── schemas/                 # Pydantic request/response models
├── tests/                   # Pytest suite (SQLite)
├── ui/
│   └── streamlit_app.py     # Streamlit frontend
├── db/sql/                  # DDL + seed scripts
├── requirements.txt
├── .env.example
└── README.md
```
