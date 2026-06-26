# Bug Deduper

FastAPI service that accepts bug reports, embeds descriptions via AWS Bedrock Titan, and detects near-duplicate open bugs using pgvector cosine similarity. Includes a Streamlit analyst UI.

## Architecture

| Layer | Technology |
|-------|------------|
| API | FastAPI (Python 3.12+) |
| DB | PostgreSQL + pgvector |
| Embedding | AWS Bedrock Titan (`amazon.titan-embed-text-v2:0`) |
| Auth | API key (`X-API-Key`) — two tiers: `standard` / `admin` |
| UI | Streamlit (calls API over HTTP) |

## Quick Start

### 1. Clone and create virtual environment

```bash
cd target-apps/bug-deduper
python -m venv .venv

# Windows PowerShell:
.venv\Scripts\Activate.ps1

# Bash/macOS:
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
```

**Edit `.env`** — every line must be `KEY=value` format. Paste your actual RDS credentials:

```
DATABASE_URL=postgresql+psycopg://user:password@host:5432/sdlc_agentic_ai?sslmode=require
```

⚠️ Never paste a bare URL without the `DATABASE_URL=` prefix.

### 4. Run the API (Terminal 1)

```bash
uvicorn app.main:app --reload --port 8000
```

Open Swagger: http://localhost:8000/docs

### 5. Run the Streamlit UI (Terminal 2)

```bash
cd target-apps/bug-deduper
source .venv/bin/activate  # or .venv\Scripts\Activate.ps1
cd ui
pip install -r requirements.txt
streamlit run streamlit_app.py --server.port 8501
```

Open UI: http://localhost:8501

## API Authentication

All endpoints except `GET /health` require an `X-API-Key` header.

| Tier | Key (dev seed) | Access |
|------|----------------|--------|
| standard | `dev-standard-key` | Create/read/update bugs |
| admin | `dev-admin-key` | All standard + resolve + mark duplicate |

In Swagger UI: click **Authorize** → enter your key in the `X-API-Key` field.

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | None | DB + Bedrock health check |
| POST | `/bugs` | standard | Submit bug with dedup detection |
| GET | `/bugs/{id}` | standard | Retrieve a bug by ID |
| PATCH | `/bugs/{id}` | standard | Update bug (re-embeds on description change) |
| POST | `/bugs/{id}/duplicate` | admin | Mark bug as duplicate |
| POST | `/bugs/{id}/resolve` | admin | Resolve a bug |

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | — | Postgres DSN (`postgresql+psycopg://...`) |
| `POSTGRES_SCHEMA` | No | `bug_deduper` | DB schema name |
| `API_KEY_STANDARD` | Yes | — | Standard-tier API key (plaintext) |
| `API_KEY_ADMIN` | Yes | — | Admin-tier API key (plaintext) |
| `AWS_REGION` | No | `us-east-2` | AWS region |
| `BEDROCK_REGION` | No | `us-east-2` | Bedrock region |
| `BEDROCK_MODEL_ID` | No | `amazon.titan-embed-text-v2:0` | Embedding model ID |
| `SIMILARITY_THRESHOLD` | No | `0.85` | Cosine similarity threshold for "likely duplicate" |
| `TOP_K` | No | `3` | Max similar bugs to return |

## Seed Data

The database seed (`db/sql/011_seed.sql`) pre-populates:

- **2 API keys:** `dev-standard-key` (standard) / `dev-admin-key` (admin)
- **7 bugs:** 5 open, 1 duplicate, 1 resolved (zero-vector embeddings for dev)

Seed passwords are applied during the pipeline DB apply step (RDS).

## Running Tests

```bash
cd target-apps/bug-deduper
pytest tests/ -q
```

Tests use SQLite in-memory and mock all Bedrock calls — no AWS credentials needed.

## RDS Smoke Test

After `.env` is configured with real RDS credentials:

```bash
curl http://localhost:8000/health
# Should return: {"status":"ok","checks":{"api":"ok","database":"ok","bedrock":"ok"}}
```

## Project Structure

```
app/
  main.py              # FastAPI app factory
  config.py            # Settings from env
  database.py          # SQLAlchemy engine + session
  startup_checks.py    # Fail-fast validation
  dependencies.py      # API key auth
  models/
    bug.py             # Bug ORM model
    api_key.py         # ApiKey ORM model
    pg_types.py        # Postgres type helpers
  routers/
    health.py          # GET /health
    bugs.py            # Bug CRUD + dedup
  services/
    bedrock_client.py  # AWS Bedrock Titan embeddings
    vector_search.py   # pgvector similarity search
schemas/
  bug.py               # Pydantic request/response models
ui/
  streamlit_app.py     # Streamlit analyst UI
  requirements.txt     # UI dependencies
tests/
  conftest.py          # Test fixtures + mocks
  test_health.py       # Health endpoint tests
  test_bugs.py         # Bug endpoint tests
db/
  sql/                 # DDL migrations (read-only)
```
