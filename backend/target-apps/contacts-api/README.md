# Contact Directory API

Internal REST API for colleague contact cards (name, email, department, phone).  
Reads are fully open; writes are guarded by a shared `X-API-Key` header.

---

## Quick Start

### 1. Clone and navigate

```bash
cd target-apps/contacts-api
```

### 2. Create virtual environment

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**Bash / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set your credentials:
- **`DATABASE_URL`** — Every line needs the variable name — paste `DATABASE_URL=postgresql+psycopg://...`, not a bare URL.
  ```
  DATABASE_URL=postgresql+psycopg://user:password@agenticaidbinstance.c1u0cggiolxp.us-east-2.rds.amazonaws.com:5432/sdlc_agentic_ai?sslmode=require
  ```
- **`API_KEY`** — shared secret for write operations (any string for local dev).

### 4. Run the server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)

### 5. Run tests

```bash
pytest -q
```

Tests use SQLite in-memory — no live Postgres required.

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | — | Postgres DSN (`postgresql+psycopg://...?sslmode=require`) |
| `POSTGRES_SCHEMA` | Yes | `contacts_api` | Database schema name |
| `API_KEY` | Yes | — | Shared secret for write routes |
| `APP_ENV` | No | `development` | `development` / `production` / `test` |
| `PORT` | No | `8000` | Server port |

---

## Seed Data (UUIDs)

The database-agent seed script populates the following stable UUIDs:

### Departments

| Name | Code | UUID |
|------|------|------|
| Engineering | ENG | `a1b2c3d4-0001-4000-8000-000000000001` |
| Sales | SALES | `a1b2c3d4-0002-4000-8000-000000000002` |
| Human Resources | HR | `a1b2c3d4-0003-4000-8000-000000000003` |

### Contacts (sample)

| Name | Email | Department | Active | UUID |
|------|-------|------------|--------|------|
| Alice Chen | alice.chen@example.com | ENG | Yes | `b1c2d3e4-0001-4000-8000-000000000001` |
| Bob Martinez | bob.martinez@example.com | ENG | Yes | `b1c2d3e4-0002-4000-8000-000000000002` |
| Carol Johnson | carol.johnson@example.com | SALES | Yes | `b1c2d3e4-0003-4000-8000-000000000003` |
| Grace Lee | grace.lee@example.com | SALES | No | `b1c2d3e4-0007-4000-8000-000000000007` |

---

## API Authentication

- **Read endpoints** (`GET`): No authentication required.
- **Write endpoints** (`POST`, `PATCH`, `DELETE`): Require `X-API-Key` header.

### Swagger UI auth

1. Open [http://localhost:8000/docs](http://localhost:8000/docs)
2. For write routes, include the `X-API-Key` header value when using "Try it out".

---

## Endpoint Reference

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | None | Health check (DB ping) |
| GET | `/api/v1/departments` | None | List all departments (sorted by name) |
| POST | `/api/v1/departments` | X-API-Key | Create department |
| GET | `/api/v1/departments/{id}` | None | Get department + contact_count |
| PATCH | `/api/v1/departments/{id}` | X-API-Key | Update department |
| GET | `/api/v1/contacts` | None | List contacts (paginated, filterable) |
| POST | `/api/v1/contacts` | X-API-Key | Create contact |
| GET | `/api/v1/contacts/{id}` | None | Get contact by ID |
| PATCH | `/api/v1/contacts/{id}` | X-API-Key | Update contact |
| DELETE | `/api/v1/contacts/{id}` | X-API-Key | Soft-delete (set is_active=false) |

### Query parameters for `GET /api/v1/contacts`

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `department_id` | uuid | — | Filter by department |
| `is_active` | bool | — | Filter by active status |
| `q` | string | — | Case-insensitive search on full_name/email |
| `limit` | int | 20 | Page size (max 200) |
| `offset` | int | 0 | Pagination offset |

---

## RDS Smoke Test

After setting up `.env` with real RDS credentials:

```bash
# 1. Health check (verifies DB connectivity)
curl http://localhost:8000/health

# 2. List departments (verifies seed data)
curl http://localhost:8000/api/v1/departments

# 3. Create a contact (verifies API-key auth)
curl -X POST http://localhost:8000/api/v1/contacts \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{"full_name":"Test User","email":"test@example.com","department_id":"a1b2c3d4-0001-4000-8000-000000000001"}'

# 4. List contacts
curl "http://localhost:8000/api/v1/contacts?limit=5"
```

Expected: Step 1 returns `{"status":"ok","checks":{"api":"ok","database":"ok"}}`, Step 2 returns 3 departments, Step 3 returns 201, Step 4 shows paginated results.
