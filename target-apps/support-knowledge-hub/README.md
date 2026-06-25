# Support Knowledge Hub

Internal knowledge hub enabling employees to search articles semantically, contributors to author with duplicate-awareness, and admins to manage categories, pins, and analytics.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| API | Python 3.12, FastAPI, Pydantic v2 |
| Database | PostgreSQL + pgvector (1024-dim embeddings) |
| Auth | JWT Bearer tokens (python-jose + bcrypt) |
| Embeddings | AWS Bedrock Titan Embed v2 |
| LLM | AWS Bedrock Claude |
| UI | Streamlit |

## Quick Start

### 1. Clone & navigate

```bash
cd target-apps/support-knowledge-hub
```

### 2. Create virtual environment

**Bash (Linux/macOS):**
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**PowerShell (Windows):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Configure environment

Copy `.env.example` to `.env` and fill in your values:

**PowerShell (Windows):** `Copy-Item .env.example .env`

**Bash:** `cp .env.example .env`

> **⚠️ Important:** Every line in `.env` must be `KEY=value`. Paste `DATABASE_URL=postgresql+psycopg://...`, not a bare URL without `DATABASE_URL=`.

### 4. Run the API (Terminal 1)

```bash
uvicorn app.main:app --reload --port 8000 --reload-dir app --reload-dir schemas
```

Open Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)

### 5. Run Streamlit UI (Terminal 2)

Keep the API running in Terminal 1. In a **second** terminal:

**PowerShell (Windows):**
```powershell
cd target-apps\support-knowledge-hub
.\.venv\Scripts\Activate.ps1
cd ui
pip install -r requirements.txt
streamlit run streamlit_app.py --server.port 8501
```

**Bash (Linux/macOS):**
```bash
cd target-apps/support-knowledge-hub
source .venv/bin/activate
cd ui
pip install -r requirements.txt
streamlit run streamlit_app.py --server.port 8501
```

Open: [http://localhost:8501](http://localhost:8501)

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL DSN | (required) |
| `POSTGRES_SCHEMA` | DB schema | `support_knowledge_hub` |
| `JWT_SECRET_KEY` | Secret for signing JWT tokens | (required) |
| `JWT_ALGORITHM` | JWT signing algorithm | `HS256` |
| `JWT_EXPIRE_MINUTES` | Token expiry | `60` |
| `AWS_REGION` | AWS region for Bedrock | `us-east-2` |
| `BEDROCK_MODEL_ID` | Bedrock Claude model ID | `us.anthropic.claude-sonnet-4-20250514-v1:0` |
| `BEDROCK_EMBED_MODEL_ID` | Titan Embed model ID | `amazon.titan-embed-text-v2:0` |
| `EMBED_DIM` | Embedding dimension | `1024` |
| `CHUNK_SIZE` | Token chunk size | `512` |
| `RETRIEVAL_TOP_K` | Number of search results | `5` |

## Authentication

All API endpoints (except `GET /health` and `POST /api/v1/auth/login`) require a JWT Bearer token.

### Getting a token

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "priya.patel@example.com", "password": "KnowledgeHub2024!"}'
```

### Using the token

Add the `Authorization: Bearer <token>` header to subsequent requests.

In Swagger UI, click the "Authorize" button and paste: `Bearer <your_token>`.

## Seed Users (dev/test)

| Email | Role | Password |
|-------|------|----------|
| `alice.chen@example.com` | employee | `KnowledgeHub2024!` |
| `bob.martinez@example.com` | employee | `KnowledgeHub2024!` |
| `carol.jones@example.com` | contributor | `KnowledgeHub2024!` |
| `dave.lee@example.com` | contributor | `KnowledgeHub2024!` |
| `priya.patel@example.com` | knowledge_admin | `KnowledgeHub2024!` |
| `frank.wu@example.com` | leadership | `KnowledgeHub2024!` |

> Passwords are applied during pipeline DB apply (`materialize_seed_passwords.py`). Do not run seed scripts manually.

## Roles & Access

| Role | Access |
|------|--------|
| `employee` | Search, view published articles, submit feedback |
| `contributor` | + Create/edit own articles, publish own drafts |
| `knowledge_admin` | + Manage all articles, categories, pins; view analytics |
| `leadership` | Read-only analytics dashboard |

## API Endpoints

| Method | Path | Notes |
|--------|------|-------|
| `GET` | `/health` | Public health check |
| `POST` | `/api/v1/auth/login` | Get JWT token |
| `GET` | `/api/v1/articles` | List articles |
| `POST` | `/api/v1/articles` | Create article (contributor+) |
| `GET` | `/api/v1/articles/{id}` | Get article detail |
| `PATCH` | `/api/v1/articles/{id}` | Update article |
| `POST` | `/api/v1/articles/{id}/similar` | Similarity check |
| `POST` | `/api/v1/search` | Semantic search |
| `POST` | `/api/v1/feedback` | Submit feedback |
| `GET` | `/api/v1/categories` | List categories |
| `POST` | `/api/v1/categories` | Create category (admin) |
| `PATCH` | `/api/v1/categories/{id}` | Update category (admin) |
| `GET` | `/api/v1/pins/{category_id}` | List pinned articles |
| `POST` | `/api/v1/pins` | Create pin (admin) |
| `DELETE` | `/api/v1/pins/{id}` | Delete pin (admin) |
| `GET` | `/api/v1/analytics/gaps` | Gap analytics (admin/leadership) |

## Running Tests

```bash
cd target-apps/support-knowledge-hub
pytest tests/ -q
```

Tests use SQLite in-memory and do not require Postgres or AWS credentials.

## RDS Smoke Test

After setting `.env` with real RDS credentials:

```bash
curl http://localhost:8000/health
# → {"status":"ok","checks":{"api":"ok","database":"ok"}}
```
