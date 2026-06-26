# Desk Booking API

Hot desk booking system for hybrid office teams. Employees reserve desks by date and time slot (full/am/pm) with conflict prevention enforced by PostgreSQL UNIQUE constraints and application-level logic.

## Local Development

### Prerequisites

- Python 3.12+
- PostgreSQL database (RDS or local)
- Virtual environment (recommended)

### Terminal 1 (API)

From the repository root:

```bash
cd target-apps/desk-booking

# Create virtual environment
# Windows:
python -m venv .venv
.venv\Scripts\activate

# Linux/macOS:
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
# Windows:
copy .env.example .env
# Linux/macOS:
cp .env.example .env

# Edit .env with your actual database credentials
# IMPORTANT: Always include the variable name — do not paste a bare URL.
# Example: DATABASE_URL=postgresql+psycopg://user:pass@host:5432/desk_booking?sslmode=require
# URL-encode special characters in passwords (# becomes %23, @ becomes %40)
# Set ADMIN_KEY to a secure random string for admin operations.

# Apply migrations (run SQL files in order against your Postgres database):
#   psql -h <host> -U <user> -d <db> -f db/sql/001_zones.sql
#   psql -h <host> -U <user> -d <db> -f db/sql/002_desks.sql
#   ... through 006_seed.sql

# Start the API server
uvicorn app.main:app --reload --port 8000 --reload-exclude '.venv'
```

API available at: http://localhost:8000  
Swagger UI: http://localhost:8000/docs

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| DATABASE_URL | Yes | - | PostgreSQL DSN: `postgresql+psycopg://user:pass@host:5432/db?sslmode=require` |
| POSTGRES_SCHEMA | No | desk_booking | Schema name for all tables |
| ADMIN_KEY | Yes (non-test) | - | Secret key for admin endpoints (X-Admin-Key header) |
| APP_ENV | No | development | Environment: development / production / test |
| AWS_REGION | No | us-east-2 | AWS region for platform services |

### Manual API Testing (Swagger)

1. Open http://localhost:8000/docs
2. **Public endpoints** (no auth needed): `GET /zones`, `GET /desks`, `GET /availability`, `GET /health`
3. **Employee endpoints**: Click "Authorize", set `X-User-Token` to a seed token (e.g., `token_alice_stable_001`)
4. **Admin endpoints**: Click "Authorize", set `X-Admin-Key` to your ADMIN_KEY from `.env`

#### curl example (create booking)

```bash
curl -X POST http://localhost:8000/bookings/ \
  -H "Content-Type: application/json" \
  -H "X-User-Token: token_alice_stable_001" \
  -d '{"desk_id":"22222222-2222-2222-2222-222222222001","booking_date":"2024-03-15","slot":"am"}'
```

#### PowerShell example

```powershell
$headers = @{"X-User-Token" = "token_alice_stable_001"; "Content-Type" = "application/json"}
$body = '{"desk_id":"22222222-2222-2222-2222-222222222001","booking_date":"2024-03-15","slot":"am"}'
Invoke-RestMethod -Uri "http://localhost:8000/bookings/" -Method POST -Headers $headers -Body $body
```

### Role & Endpoint Quick Reference

| Endpoint | Auth Required | Example Credential | Expected Result | Wrong Auth |
|----------|---------------|-------------------|-----------------|------------|
| GET /health | None | - | 200 status ok | - |
| GET /zones | None | - | 200 list of zones | - |
| GET /desks | None | - | 200 list of desks | - |
| GET /availability?date=YYYY-MM-DD | None | - | 200 per-desk availability | - |
| POST /bookings | X-User-Token | `token_alice_stable_001` | 201 booking created | 401 (no token) |
| GET /bookings/mine | X-User-Token | `token_bob_stable_002` | 200 user's bookings | 401 (no token) |
| DELETE /bookings/{id} | X-User-Token (owner) or X-Admin-Key | token or ADMIN_KEY | 204 | 403 (not owner) |
| POST /desks | X-Admin-Key | ADMIN_KEY from .env | 201 desk created | 401 (missing key) |
| PATCH /desks/{id} | X-Admin-Key | ADMIN_KEY from .env | 200 desk updated | 401 (missing key) |
| POST /blackouts | X-Admin-Key | ADMIN_KEY from .env | 201 blackout created | 401 (missing key) |
| GET /blackouts | X-Admin-Key | ADMIN_KEY from .env | 200 list of blackouts | 401 (missing key) |
| DELETE /blackouts/{id} | X-Admin-Key | ADMIN_KEY from .env | 204 | 401 (missing key) |

### Seed Users

From `db/sql/006_seed.sql`:

| Email | Token | UUID |
|-------|-------|------|
| alice.chen@company.com | `token_alice_stable_001` | `33333333-3333-3333-3333-333333333001` |
| bob.smith@company.com | `token_bob_stable_002` | `33333333-3333-3333-3333-333333333002` |
| carol.jones@company.com | `token_carol_stable_003` | `33333333-3333-3333-3333-333333333003` |
| david.wilson@company.com | `token_david_stable_004` | `33333333-3333-3333-3333-333333333004` |
| eva.martinez@company.com | `token_eva_stable_005` | `33333333-3333-3333-3333-333333333005` |

### Seed UUIDs

- **Zones**: north=`11111111-1111-1111-1111-111111111001`, south=`…002`, lab=`…003`
- **Desks**: N-01=`22222222-2222-2222-2222-222222222001` through LAB-02=`…008`
- **Users**: Alice=`33333333-3333-3333-3333-333333333001` through Grace=`…007`

### RDS Smoke Test

After configuring `.env` with real RDS credentials:

```bash
# 1. Health check
curl http://localhost:8000/health

# 2. List zones (public)
curl http://localhost:8000/zones/

# 3. Check availability (public)
curl "http://localhost:8000/availability/?date=2024-03-15"

# 4. List desks (public)
curl "http://localhost:8000/desks/?zone=north"

# 5. Create booking (employee)
curl -X POST http://localhost:8000/bookings/ \
  -H "Content-Type: application/json" \
  -H "X-User-Token: token_alice_stable_001" \
  -d '{"desk_id":"22222222-2222-2222-2222-222222222001","booking_date":"2024-03-15","slot":"am"}'

# 6. List my bookings (employee)
curl -H "X-User-Token: token_alice_stable_001" http://localhost:8000/bookings/mine

# 7. Create blackout (admin)
curl -X POST http://localhost:8000/blackouts/ \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: YOUR_ADMIN_KEY" \
  -d '{"desk_id":"22222222-2222-2222-2222-222222222001","starts_on":"2024-04-01","ends_on":"2024-04-03","reason":"Maintenance"}'
```

### Testing

```bash
cd target-apps/desk-booking
pytest -q
```

**Note**: Tests use SQLite in-memory database. Passing tests does NOT guarantee PostgreSQL RDS compatibility — always run the RDS smoke test above after configuring `.env`.

### Deployment (AWS dev — devops-agent)

| Concern | Value |
|---------|-------|
| Port | 8000 |
| Health | GET /health |
| Start command | `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}` |
| Env source | AWS Secrets Manager |
| Database | PostgreSQL RDS, schema `desk_booking` |
| Region | us-east-2 |
