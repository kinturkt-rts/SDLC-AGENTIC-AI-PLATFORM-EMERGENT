# Audit Finding Tracker

Internal audit system for managing SOC findings with centralized workflow, immutable audit trails, and executive reporting. Replaces Excel-based finding management with structured workflows and role-based access control.

## Features

- **Role-based Access Control**: Auditor, assignee, and executive roles with scoped data access
- **Status Workflow**: Enforced transitions from draft → assigned → in_progress → pending_verification → verified → closed
- **Optimistic Locking**: Version control with If-Match headers to prevent concurrent update conflicts
- **Immutable Audit Trail**: Complete status history for compliance and regulatory requirements
- **Evidence Management**: File upload and metadata tracking for remediation evidence
- **Executive Reporting**: Real-time dashboards with overdue findings and department summaries
- **Threaded Comments**: Collaborative discussion on findings with parent-child relationships

## API Documentation

After starting the application, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Local Development

### Prerequisites

- Python 3.12+
- PostgreSQL (or SQLite for testing)
- Git

### Setup (Windows)

Open Command Prompt or PowerShell at the **repo root** (folder containing `target-apps/`):

```cmd
cd target-apps\audit-finding-tracker
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

### Setup (bash/Linux/Mac)  

Open terminal at the **repo root** (folder containing `target-apps/`):

```bash
cd target-apps/audit-finding-tracker
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### Environment Configuration

Edit `.env` file with your settings:

```env
# Database - MUST include variable name, not just the URL
DATABASE_URL=postgresql+psycopg://username:password@localhost:5432/audit_tracker?sslmode=require
POSTGRES_SCHEMA=audit_finding_tracker

# JWT Authentication  
JWT_SECRET_KEY=your-super-secret-jwt-key-change-in-production

# File Storage
LOCAL_UPLOAD_DIR=./data/evidence
```

**Important**: 
- Every line needs the variable name — paste `DATABASE_URL=postgresql+psycopg://...`, not a bare URL
- URL-encode special characters in passwords (# → %23, @ → %40)
- For local development, you can use SQLite: `DATABASE_URL=sqlite:///./dev.db`

### Database Setup

The application expects PostgreSQL with the schema from `db/sql/` files. For development:

1. Create database: `CREATE DATABASE audit_tracker;`
2. Run migrations from `db/sql/` in order (001_users.sql, 002_audits.sql, etc.)
3. Load seed data: `011_seed.sql`

Or use SQLite for local testing (tests run on SQLite automatically).

### Run Application

**Terminal 1 (API Server)**:
```bash
cd target-apps/audit-finding-tracker
source .venv/bin/activate  # Windows: .venv\Scripts\activate
uvicorn app.main:app --reload --port 8000 --reload-exclude '.venv'
```

API will be available at http://localhost:8000

### Run Tests

```bash
cd target-apps/audit-finding-tracker  
source .venv/bin/activate
pytest tests/ -v
```

**Note**: Tests use SQLite in-memory database. Passing tests do not guarantee PostgreSQL compatibility — always test against RDS for production readiness.

## API Authentication

The API uses JWT Bearer tokens. Get a token via the login endpoint:

### Swagger UI Authentication

1. Go to http://localhost:8000/docs
2. Click "Authorize" button
3. Use format: `Bearer <your-jwt-token>`

### Manual API Testing

**Get JWT Token** (curl):
```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "priya.sharma@company.com",
    "password": "password"
  }'
```

**Get JWT Token** (PowerShell):
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/auth/login" -Method POST -ContentType "application/json" -Body '{
  "email": "priya.sharma@company.com", 
  "password": "password"
}'
```

**Use Token in Requests** (curl):
```bash
curl -X GET "http://localhost:8000/api/v1/findings/" \
  -H "Authorization: Bearer <your-jwt-token>"
```

**Use Token in Requests** (PowerShell):
```powershell  
$headers = @{ "Authorization" = "Bearer <your-jwt-token>" }
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/findings/" -Method GET -Headers $headers
```

## API Endpoints

| Method | Endpoint | Description | Role Required |
|--------|----------|-------------|---------------|
| POST | `/api/v1/auth/login` | Authenticate and get JWT token | None |
| GET | `/api/v1/audits/` | List audits (paginated) | Auditor/Executive |
| POST | `/api/v1/audits/` | Create new audit | Auditor/Executive |
| GET | `/api/v1/findings/` | List findings (role-scoped) | Any authenticated |
| POST | `/api/v1/findings/` | Create new finding | Auditor |
| PUT | `/api/v1/findings/{id}/status` | Update finding status | Auditor/Assignee |
| GET | `/api/v1/findings/{id}/history` | Get status history | Any authenticated |
| POST | `/api/v1/findings/{id}/evidence` | Upload evidence file | Auditor/Assignee |
| POST | `/api/v1/findings/{id}/comments` | Create comment | Any authenticated |
| GET | `/api/v1/reports/executive` | Executive dashboard | Executive |
| GET | `/health` | Health check | None |

## Test Users (from seed data)

| Email | Password | Role | Use Case |
|-------|----------|------|----------|
| priya.sharma@company.com | password | auditor | Create audits/findings, manage workflow |
| mike.chen@company.com | password | assignee | Work on assigned findings, upload evidence |
| sarah.johnson@company.com | password | executive | View reports and dashboards |

## Seed Finding IDs

Use these UUIDs for testing against seeded data:

```bash
# High severity finding (assigned)
FINDING_ID=770e8400-e29b-41d4-a716-446655440001

# Medium severity finding (in_progress) 
FINDING_ID=770e8400-e29b-41d4-a716-446655440002

# Critical finding (pending_verification)
FINDING_ID=770e8400-e29b-41d4-a716-446655440003
```

## Status Workflow

Valid finding status transitions:
- `draft` → `assigned`
- `assigned` → `in_progress`
- `in_progress` → `pending_verification` (requires evidence files)
- `in_progress` → `assigned` (reassignment)
- `pending_verification` → `verified`
- `pending_verification` → `in_progress` (rejected)
- `verified` → `closed`

## Optimistic Locking

Status updates require `If-Match` header with current version:

```bash
curl -X PUT "http://localhost:8000/api/v1/findings/{id}/status" \
  -H "Authorization: Bearer <token>" \
  -H "If-Match: \"2\"" \
  -H "Content-Type: application/json" \
  -d '{"status": "assigned", "comment": "Starting work"}'
```

## File Uploads

Evidence files are uploaded via multipart form data:

```bash
curl -X POST "http://localhost:8000/api/v1/findings/{id}/evidence" \
  -H "Authorization: Bearer <token>" \
  -F "file=@document.pdf"
```

Supported file types: PDF, Word, Excel, images (JPEG, PNG, GIF), plain text  
Maximum file size: 10MB (configurable via `MAX_FILE_SIZE_MB`)

## RDS Smoke Test

After configuring `.env` with PostgreSQL connection:

1. **Health Check**: `GET /health` should return `{"status": "ok", "checks": {"api": "ok", "database": "ok"}}`
2. **List Findings**: `GET /api/v1/findings/` with valid JWT should return seeded finding data
3. **Database Query**: Verify direct connection returns expected seed data

If health check fails, verify:
- Database is running and accessible
- `DATABASE_URL` format is correct
- Schema `audit_finding_tracker` exists  
- All migration files have been applied

## Production Deployment (AWS - devops-agent)

- **Port**: 8000
- **Health Check Path**: `/health`  
- **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- **Environment Variables**: See `.env.example` for required configuration
- **Secrets**: Store `DATABASE_URL`, `JWT_SECRET_KEY` in AWS Secrets Manager
- **File Storage**: Configure S3 bucket and set `FILE_STORAGE_TYPE=s3`

## Architecture

- **API Framework**: FastAPI with Pydantic v2
- **Database**: PostgreSQL with SQLAlchemy 2.x ORM
- **Authentication**: JWT Bearer tokens with role-based authorization
- **File Storage**: Local filesystem (MVP) / S3 (production)
- **Testing**: pytest with SQLite in-memory database