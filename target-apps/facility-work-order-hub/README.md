# Facility Work Order Hub

Internal facility management REST API (FastAPI) with a Streamlit front-end for creating, assigning, and tracking maintenance work orders across multi-site portfolios.

## Tech Stack

- **API:** FastAPI + Uvicorn (Python 3.12+)
- **Database:** PostgreSQL (RDS) via SQLAlchemy 2.x + psycopg3
- **Auth:** JWT Bearer (PyJWT, 60-min TTL, bcrypt password hashing)
- **UI:** Streamlit (calls API over HTTP)

## Quick Start

### 1. Clone and navigate

```bash
cd target-apps/facility-work-order-hub
```

### 2. Create virtual environment

**Bash (macOS/Linux):**
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**PowerShell (Windows):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and fill in:
- `DATABASE_URL` — **Every line needs the variable name.** Paste `DATABASE_URL=postgresql+psycopg://user:pass@host:5432/db?sslmode=require`, not a bare URL.
- `JWT_SECRET_KEY` — A random secret string for token signing.

### 4. Run the API (Terminal 1)

```bash
uvicorn app.main:app --reload --port 8000 --reload-dir app --reload-dir schemas
```

Open [http://localhost:8000/docs](http://localhost:8000/docs) for interactive Swagger UI.

### 5. Run the Streamlit UI (Terminal 2)

```bash
cd target-apps/facility-work-order-hub
source .venv/bin/activate  # or .venv\Scripts\Activate.ps1 on Windows
cd ui
pip install -r requirements.txt
streamlit run streamlit_app.py --server.port 8501
```

Open [http://localhost:8501](http://localhost:8501)

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | Postgres DSN: `postgresql+psycopg://user:pass@host:5432/db?sslmode=require` |
| `POSTGRES_SCHEMA` | Yes | `facility_work_order_hub` |
| `JWT_SECRET_KEY` | Yes | Secret for signing JWT tokens |
| `JWT_ALGORITHM` | No | Default: `HS256` |
| `JWT_EXPIRE_MINUTES` | No | Default: `60` |
| `APP_ENV` | No | `development` / `production` / `test` |
| `API_BASE_URL` | No | For Streamlit UI. Default: `http://localhost:8000` |

## Seed Data

The database has been seeded via `db/sql/008_seed.sql` (applied during RDS pipeline).

| Email | Password | Role |
|-------|----------|------|
| admin@example.com | DevPassword123! | facilities_admin |
| alice.req@example.com | DevPassword123! | requester |
| bob.req@example.com | DevPassword123! | requester |
| charlie.tech@example.com | DevPassword123! | technician |
| diana.tech@example.com | DevPassword123! | technician |
| exec@example.com | DevPassword123! | leadership |

Passwords are applied during pipeline DB apply (bcrypt hashes materialized automatically).

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | No | Health check |
| POST | `/api/v1/auth/token` | No | Login, returns JWT |
| POST | `/api/v1/sites` | Admin | Create site |
| PATCH | `/api/v1/sites/{id}` | Admin | Update site |
| POST | `/api/v1/sites/{id}/locations` | Admin | Create location |
| POST | `/api/v1/work-orders` | Requester/Admin | Create work order |
| GET | `/api/v1/work-orders` | All (role-scoped) | List work orders |
| GET | `/api/v1/work-orders/{id}` | All (read-access) | Get work order |
| PATCH | `/api/v1/work-orders/{id}/status` | Admin/Tech | Update status |
| PATCH | `/api/v1/work-orders/{id}/assign` | Admin | Assign technician |
| POST | `/api/v1/work-orders/{id}/comments` | Read-access | Add comment |
| GET | `/api/v1/work-orders/{id}/comments` | Read-access | List comments |
| GET | `/api/v1/dashboard/sla` | Admin/Leadership | SLA dashboard |
| GET | `/api/v1/dashboard/workload` | Admin | Technician workload |

## Authentication (Swagger)

1. POST `/api/v1/auth/token` with `{"email": "admin@example.com", "password": "DevPassword123!"}`
2. Copy the `access_token` from the response
3. Click "Authorize" in Swagger and enter `Bearer <token>`

## Running Tests

```bash
pytest tests/ -q
```

Tests use an in-memory SQLite database (no Postgres required for CI).

## RDS Smoke Test

After setting `DATABASE_URL` in `.env`:

```bash
curl http://localhost:8000/health
```

Expected: `{"status": "ok", "checks": {"api": "ok", "database": "ok"}}`
