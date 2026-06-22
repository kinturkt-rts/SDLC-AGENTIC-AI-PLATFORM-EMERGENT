# Support Knowledge Hub

Internal knowledge hub with semantic article search, lifecycle management (draft→published→archived), AI-assisted duplicate detection, and role-gated analytics.

## Tech Stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2.x, PostgreSQL (pgvector)
- **Auth:** JWT Bearer tokens (bcrypt password hashing)
- **UI:** Streamlit (role-gated views)
- **Database:** AWS RDS PostgreSQL (`support_knowledge_hub` schema)

## Quick Start

### Prerequisites

- Python 3.12+
- Access to RDS PostgreSQL instance (or local Postgres with pgvector)

### 1. Setup (from repo root)

```bash
cd target-apps/support-knowledge-hub

# Create virtual environment
python -m venv .venv

# Activate (Windows PowerShell)
.venv\Scripts\Activate.ps1

# Activate (Bash/macOS)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

**⚠️ IMPORTANT:** Every line in `.env` must be `KEY=value` format. Paste:
```
DATABASE_URL=postgresql+psycopg://postgres:yourpassword@agenticaidbinstance.c1u0cggiolxp.us-east-2.rds.amazonaws.com:5432/sdlc_agentic_ai?sslmode=require
```

Do NOT paste a bare URL without `DATABASE_URL=` prefix.

Set a real `JWT_SECRET_KEY` for production (any string ≥ 32 chars).

### 3. Terminal 1 — Start API

```bash
cd target-apps/support-knowledge-hub
.venv\Scripts\Activate.ps1  # or source .venv/bin/activate
# Limit reload to app code only — do NOT watch .venv (pytest edits cause reload storms / Streamlit timeouts)
uvicorn app.main:app --reload --port 8000 --reload-dir app --reload-dir schemas
```

API available at http://localhost:8000  
Swagger UI: http://localhost:8000/docs

### 4. Terminal 2 — Start Streamlit UI

```bash
cd target-apps/support-knowledge-hub
.venv\Scripts\Activate.ps1  # or source .venv/bin/activate
cd ui
pip install -r requirements.txt
streamlit run streamlit_app.py --server.port 8501
```

UI available at http://localhost:8501

## Swagger Auth

1. Open http://localhost:8000/docs
2. Call `POST /auth/token` with credentials below
3. Copy `access_token` from response
4. Click "Authorize" button → paste `Bearer <token>`

## Seed Users & Credentials

Password for all seed users: `KnowledgeHub2024!`

| Email | Role | UUID |
|-------|------|------|
| priya@example.com | knowledge_admin | a1000000-0000-0000-0000-000000000001 |
| carlos@example.com | contributor | a1000000-0000-0000-0000-000000000002 |
| mei@example.com | contributor | a1000000-0000-0000-0000-000000000003 |
| james@example.com | leadership | a1000000-0000-0000-0000-000000000004 |
| alice@example.com | employee | a1000000-0000-0000-0000-000000000005 |
| bob@example.com | employee | a1000000-0000-0000-0000-000000000006 |
| dana@example.com | employee | a1000000-0000-0000-0000-000000000007 |
| frank@example.com | employee | a1000000-0000-0000-0000-000000000008 |
| grace@example.com | employee | a1000000-0000-0000-0000-000000000009 |

> Seed passwords are applied during RDS pipeline DB apply (bcrypt materialized automatically).

## Role & Endpoint Quick Reference

| Role | Accessible Endpoints |
|------|---------------------|
| **employee** | `POST /search`, `GET /articles`, `GET /articles/{id}`, `POST /feedback` |
| **contributor** | All employee routes + `POST /articles`, `PATCH /articles/{id}` (own), `POST /articles/{id}/similar` |
| **knowledge_admin** | All routes: articles CRUD (any), categories, pins, analytics |
| **leadership** | `GET /articles` (published), `GET /admin/analytics/gaps` |

### Example Usage per Role

- **Employee:** Login as `alice@example.com` → Search articles, browse published, submit feedback
- **Contributor:** Login as `carlos@example.com` → Create drafts, publish, check similarity
- **Admin:** Login as `priya@example.com` → Manage categories, pin articles, view analytics
- **Leadership:** Login as `james@example.com` → View analytics dashboard (read-only)

## RDS Smoke Test

```bash
# 1. Health check
curl http://localhost:8000/health
# Expect: {"status":"ok","version":"0.1.0","checks":{"api":"ok","database":"ok"}}

# 2. Login
curl -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"email":"priya@example.com","password":"KnowledgeHub2024!"}'

# 3. List articles (use token from step 2)
curl http://localhost:8000/articles \
  -H "Authorization: Bearer <token>"
```

## Running Tests

```bash
cd target-apps/support-knowledge-hub
pytest tests/ -q
```

Tests use SQLite in-memory — no RDS connection required.

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| DATABASE_URL | Yes | — | PostgreSQL DSN (`postgresql+psycopg://...?sslmode=require`) |
| POSTGRES_SCHEMA | Yes | support_knowledge_hub | Schema name |
| JWT_SECRET_KEY | Yes | — | Secret for JWT signing |
| JWT_ALGORITHM | No | HS256 | JWT algorithm |
| JWT_EXPIRE_MINUTES | No | 60 | Token TTL |
| EMBED_MODEL_NAME | No | all-MiniLM-L6-v2 | Embedding model |
| EMBED_DIM | No | 384 | Embedding dimension |
| SIMILARITY_THRESHOLD | No | 0.75 | Cosine similarity threshold |
| AWS_REGION | No | us-east-2 | AWS region |
| APP_ENV | No | development | App environment |
