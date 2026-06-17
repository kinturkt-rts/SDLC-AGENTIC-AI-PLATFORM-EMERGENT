# Contact Directory API

Internal contact directory REST service — FastAPI + SQLAlchemy 2.x + PostgreSQL (schema `contacts_api`).  
Write routes guarded by `X-API-Key` header; all reads are public.

---

## Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | None | Liveness probe |
| POST | `/departments` | API-key | Create department |
| GET | `/departments` | None | List all departments (sorted by name) |
| GET | `/departments/{id}` | None | Get department + contact_count |
| PATCH | `/departments/{id}` | API-key | Update department name/code |
| POST | `/contacts` | API-key | Create contact |
| GET | `/contacts` | None | List contacts (paginated, filterable, searchable) |
| GET | `/contacts/{id}` | None | Get single contact |
| PATCH | `/contacts/{id}` | API-key | Update contact fields |
| DELETE | `/contacts/{id}` | API-key | Soft-delete (sets is_active=false) |

---

## Local Development

### Prerequisites

- Python 3.12+
- (Optional) PostgreSQL instance for integration testing

### Terminal 1 — API Server

**Bash (macOS/Linux):**
```bash
cd target-apps/contacts-api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env: set DATABASE_URL, POSTGRES_SCHEMA, API_KEY
uvicorn app.main:app --reload --port 8000
```

**Windows (PowerShell):**
```powershell
cd target-apps\contacts-api
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# Edit .env: set DATABASE_URL, POSTGRES_SCHEMA, API_KEY
uvicorn app.main:app --reload --port 8000
```

### Running Tests

Tests use SQLite in-memory — no Postgres required:

```bash
cd target-apps/contacts-api
source .venv/bin/activate
pip install pytest httpx
pytest tests/ -v
```

> ⚠️ Passing tests use SQLite. This does **not** prove the app works against RDS.  
> Always perform the RDS smoke test below before declaring success.

---

## Manual API Test (Swagger)

1. Open http://localhost:8000/docs
2. For write routes, click **Authorize** or add the header manually:
   - Header name: `X-API-Key`
   - Value: the `API_KEY` from your `.env` (default: `dev-api-key-change-me`)

### curl examples

```bash
# Health
curl http://localhost:8000/health

# List departments (public)
curl http://localhost:8000/departments

# Create department (requires API key)
curl -X POST http://localhost:8000/departments \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-api-key-change-me" \
  -d '{"name": "Marketing", "code": "MKT"}'

# List contacts with search
curl "http://localhost:8000/contacts?q=alice&limit=10&offset=0"

# Create contact
curl -X POST http://localhost:8000/contacts \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-api-key-change-me" \
  -d '{"full_name":"Alice Smith","email":"alice@example.com","department_id":"a1b2c3d4-0001-4000-8000-000000000001"}'

# Soft-delete contact
curl -X DELETE http://localhost:8000/contacts/b2c3d4e5-0001-4000-8000-000000000001 \
  -H "X-API-Key: dev-api-key-change-me"
```

### PowerShell example

```powershell
# List departments
Invoke-RestMethod -Uri http://localhost:8000/departments -Method GET

# Create department
$headers = @{ "X-API-Key" = "dev-api-key-change-me"; "Content-Type" = "application/json" }
$body = '{"name": "Marketing", "code": "MKT"}'
Invoke-RestMethod -Uri http://localhost:8000/departments -Method POST -Headers $headers -Body $body
```

---

## RDS Smoke Test

After filling `.env` with real RDS credentials:

> **Note:** URL-encode special characters in passwords (e.g., `#` → `%23`).

1. Start the server: `uvicorn app.main:app --port 8000`
2. Health check:
   ```bash
   curl http://localhost:8000/health
   # Expected: {"status":"ok","service":"contacts-api"}
   ```
3. List departments (seed data should be present):
   ```bash
   curl http://localhost:8000/departments
   # Expected: 3 departments — Engineering (ENG), HR (HR), Sales (SALES)
   ```
4. Fetch a seeded contact by UUID:
   ```bash
   curl http://localhost:8000/contacts/b2c3d4e5-0001-4000-8000-000000000001
   # Expected: Alice Johnson, alice.johnson@example.com
   ```
5. List inactive contacts:
   ```bash
   curl "http://localhost:8000/contacts?is_active=false"
   # Expected: George Taylor (seed inactive contact)
   ```

### Seed UUIDs (from `db/sql/004_seed.sql`)

| Entity | UUID | Identifier |
|--------|------|------------|
| Department: Engineering | `a1b2c3d4-0001-4000-8000-000000000001` | ENG |
| Department: Sales | `a1b2c3d4-0002-4000-8000-000000000002` | SALES |
| Department: HR | `a1b2c3d4-0003-4000-8000-000000000003` | HR |
| Contact: Alice Johnson | `b2c3d4e5-0001-4000-8000-000000000001` | alice.johnson@example.com |
| Contact: George Taylor (inactive) | `b2c3d4e5-0007-4000-8000-000000000007` | george.taylor@example.com |

---

## Deployment (AWS dev — devops-agent)

| Config | Value |
|--------|-------|
| Port | 8000 |
| Health probe | `GET /health` |
| Start command | `uvicorn app.main:app --host 0.0.0.0 --port 8000` |
| Env vars | `DATABASE_URL`, `POSTGRES_SCHEMA`, `API_KEY`, `PORT` |
| Secrets | `DATABASE_URL`, `API_KEY` via AWS Secrets Manager |
