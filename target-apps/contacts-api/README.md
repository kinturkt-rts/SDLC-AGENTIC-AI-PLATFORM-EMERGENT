# Contact Directory API

Internal REST API for colleague contact information with department organization. Pattern B Postgres CRUD with API key authentication.

## Features

- **Departments**: Create and manage organizational departments
- **Contacts**: Full CRUD operations for contact records with department relationships
- **Search**: Case-insensitive search across contact names and emails
- **Authentication**: API key protection for write operations
- **Soft Delete**: Maintains audit trail by setting `is_active=false`

## API Endpoints

| Method | Path | Description | Auth Required |
|--------|------|-------------|---------------|
| GET | `/health` | Health check with database ping | No |
| GET | `/contacts` | List contacts with search & pagination | No |
| GET | `/contacts/{id}` | Get specific contact | No |
| POST | `/contacts` | Create new contact | API Key |
| PATCH | `/contacts/{id}` | Update existing contact | API Key |
| DELETE | `/contacts/{id}` | Soft delete contact | API Key |
| GET | `/departments` | List all departments | No |
| POST | `/departments` | Create new department | API Key |
| PATCH | `/departments/{id}` | Update existing department | API Key |

## Local Development

### Prerequisites
- Python 3.12+
- PostgreSQL 15+ (for production) or SQLite (for testing)
- Git

### Setup (Windows & bash)

**Terminal 1: API Server**

```bash
# From repo root
cd target-apps/contacts-api

# Create virtual environment
python -m venv .venv

# Activate venv (Windows)
.venv\Scripts\activate
# Activate venv (bash/Linux/Mac)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
# Windows:
copy .env.example .env
# bash/Linux/Mac:
cp .env.example .env

# Edit .env file - set real values:
# DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/contacts_db?sslmode=require
# POSTGRES_SCHEMA=contacts_api
# API_KEY=your-secure-api-key-here

# Start API server
uvicorn app.main:app --reload --port 8000 --reload-exclude '.venv'
```

**Important**: Every line in `.env` needs the variable name — paste `DATABASE_URL=postgresql+psycopg://...`, not a bare URL.

### Database Setup

The API expects the `contacts_api` schema to exist with tables created by the database-agent SQL files in `db/sql/`.

For password characters like `#` in the DATABASE_URL, use URL encoding: `#` becomes `%23`.

### Environment Variables

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `APP_ENV` | No | Application environment | `development` |
| `DATABASE_URL` | Yes | PostgreSQL connection string | `postgresql+psycopg://user:pass@host:5432/db?sslmode=require` |
| `POSTGRES_SCHEMA` | Yes | Database schema name | `contacts_api` |
| `API_KEY` | Yes | Shared API key for write operations | `your-secure-key` |
| `PORT` | No | Server port | `8000` |

### Running Tests

```bash
# From target-apps/contacts-api with venv activated
python -m pytest tests/ -v
```

**Note**: Tests use SQLite in memory. Passing tests don't guarantee RDS compatibility — always test against real Postgres.

## Manual API Testing

### Swagger UI
1. Start the API server
2. Open http://localhost:8000/docs
3. For protected endpoints, click "Authorize" and enter your API key in the `X-API-Key` field

### curl Examples

**Health check:**
```bash
curl http://localhost:8000/health
```

**List departments:**
```bash
curl http://localhost:8000/departments
```

**Create department (requires API key):**
```bash
curl -X POST http://localhost:8000/departments \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secure-key" \
  -d '{"name": "Engineering", "code": "ENG"}'
```

**List contacts:**
```bash
curl http://localhost:8000/contacts
```

**Search contacts:**
```bash
curl "http://localhost:8000/contacts?q=john&limit=10"
```

**Create contact (requires API key):**
```bash
curl -X POST http://localhost:8000/contacts \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secure-key" \
  -d '{
    "department_id": "dept-uuid-here",
    "full_name": "John Doe", 
    "email": "john.doe@company.com",
    "phone": "555-1234",
    "title": "Software Engineer"
  }'
```

### PowerShell Example

```powershell
$headers = @{
    "X-API-Key" = "your-secure-key"
    "Content-Type" = "application/json"
}

$body = @{
    name = "Engineering"
    code = "ENG"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/departments" -Method Post -Headers $headers -Body $body
```

## RDS Smoke Test

After setting up `.env` with real PostgreSQL credentials:

1. **Health check**: `curl http://localhost:8000/health` should return `{"status":"ok","checks":{"api":"ok","database":"ok"}}`

2. **List departments**: `curl http://localhost:8000/departments` should return department array

3. **Use seed UUIDs** from `db/sql/004_seed.sql`:
   - Engineering dept: `11111111-1111-1111-1111-111111111111`
   - Sales dept: `22222222-2222-2222-2222-222222222222`
   - Marketing dept: `33333333-3333-3333-3333-333333333333`

4. **Create test contact**:
   ```bash
   curl -X POST http://localhost:8000/contacts \
     -H "X-API-Key: your-key" \
     -H "Content-Type: application/json" \
     -d '{
       "department_id": "11111111-1111-1111-1111-111111111111",
       "full_name": "Test User",
       "email": "test@company.com"
     }'
   ```

## Authentication

Write operations (POST, PATCH, DELETE) require the `X-API-Key` header:

```
X-API-Key: your-secure-api-key-here
```

Missing or invalid keys return `401 Unauthorized`.

## Search & Pagination

**Search contacts**:
- Parameter: `?q=searchterm`
- Searches `full_name` and `email` fields (case-insensitive)
- Example: `/contacts?q=john` finds "John Smith" and "jane.johnson@company.com"

**Pagination**:
- `?limit=N` (default 50, max 100)
- `?offset=N` (default 0)
- Response includes `total`, `limit`, `offset` for navigation

## Deployment (AWS dev — devops-agent)

- **Port**: 8000
- **Health endpoint**: `/health`
- **Start command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Environment**: Variables from `.env.example`
- **Secrets**: Load `DATABASE_URL` and `API_KEY` from AWS Secrets Manager