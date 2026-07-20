# Expense Tracker

Internal REST API for employee expense submission, admin approval/rejection, and manager team-spend reporting with at-submit-time FX conversion.

## Tech Stack

- Python 3.12 + FastAPI + Pydantic v2
- SQLAlchemy 2.x (sync) + psycopg 3
- PostgreSQL (RDS) with schema `expense_tracker`
- Streamlit UI (optional interactive client)
- Authentication: API key via `X-API-Key` header (bcrypt-hashed in DB)

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

Edit `.env` and set your real `DATABASE_URL`. Every line **must** be `KEY=value` — never paste a bare URL without the `DATABASE_URL=` prefix.

Example:
```
DATABASE_URL=postgresql+psycopg://postgres:mypassword@agenticaidbinstance.c1u0cggiolxp.us-east-2.rds.amazonaws.com:5432/sdlc_agentic_ai?sslmode=require
```

### 3. Run the API (Terminal 1)

```bash
uvicorn app.main:app --reload --port 8000 --reload-dir app --reload-dir schemas
```

Open Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)

### 4. Run the Streamlit UI (Terminal 2)

**PowerShell (Windows):**
```powershell
cd target-apps/expense-tracker
.\.venv\Scripts\Activate.ps1
cd ui
pip install -r requirements.txt
streamlit run streamlit_app.py --server.port 8501
```

**Bash:**
```bash
cd target-apps/expense-tracker
source .venv/bin/activate
cd ui
pip install -r requirements.txt
streamlit run streamlit_app.py --server.port 8501
```

### 5. Run tests

```bash
pytest tests/ -q
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `APP_ENV` | `development`, `production`, `test` | `development` |
| `DATABASE_URL` | PostgreSQL DSN (psycopg driver) | _(required)_ |
| `POSTGRES_SCHEMA` | Schema name | `expense_tracker` |
| `API_KEY` | API key for admin access | _(required)_ |
| `AWS_REGION` | AWS region | `us-east-2` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `CORS_ORIGINS` | Allowed CORS origins | `["*"]` |

## Demo Accounts

| Email | Role | Password / Token |
|-------|------|-----------------|
| admin@example.com | admin | ExpenseTest123! |
| admin2@example.com | admin | ExpenseTest123! |
| manager@example.com | manager | ExpenseTest123! |
| alice@example.com | employee | ExpenseTest123! |
| bob@example.com | employee | ExpenseTest123! |
| carol@example.com | employee | ExpenseTest123! |
| dave@example.com | employee | ExpenseTest123! |

The `X-API-Key` header accepts the plaintext token/key. The API matches it against bcrypt hashes in the `users.token_hash` and `api_keys.key_hash` columns.

For live UI / Swagger auth, use the seeded demo secret: `ExpenseTest123!`
(same value as the seed password comment in `db/sql/008_seed.sql`).

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | None | Health check with DB ping |
| POST | `/api/v1/expenses` | Employee | Submit expense |
| GET | `/api/v1/expenses` | Employee/Admin | List expenses |
| GET | `/api/v1/expenses/{id}` | Owner/Admin | Get expense |
| PATCH | `/api/v1/expenses/{id}` | Owner | Edit submitted expense |
| DELETE | `/api/v1/expenses/{id}` | Owner | Soft-delete submitted expense |
| POST | `/api/v1/expenses/{id}/approve` | Admin | Approve expense |
| POST | `/api/v1/expenses/{id}/reject` | Admin | Reject expense |
| GET | `/api/v1/expenses/{id}/audit` | Admin | Audit trail |
| POST | `/api/v1/teams` | Admin | Create team |
| GET | `/api/v1/teams` | Admin/Manager | List teams |
| PATCH | `/api/v1/teams/{id}/members` | Admin | Assign/remove member |
| GET | `/api/v1/teams/{id}/expenses/summary` | Manager/Admin | Monthly summary |
| POST | `/api/v1/fx-snapshots` | Admin | Create/update FX rate |

## Swagger Auth

1. Open http://localhost:8000/docs
2. Click "Authorize" button
3. Enter your API key in the `X-API-Key` field
4. Execute endpoints

## Architecture Notes

- All monetary values use `Decimal` (never `float`) mapped to `NUMERIC(19,4)` in Postgres
- FX conversion happens at submit/edit time; `amount_usd` is frozen on the row
- Soft-delete only — `deleted_at` timestamp; no hard deletes
- Append-only audit log for all expense state changes
- Composite index on `(team_id, expense_date, status, deleted_at)` for aggregation performance
