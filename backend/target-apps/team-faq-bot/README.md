# Team FAQ Bot

A single-team FAQ chatbot. Admins upload a plain-text FAQ file; users ask natural-language questions via REST API; FastAPI retrieves top-k chunks via pgvector cosine similarity, then Bedrock Claude composes a cited answer (or returns "not in FAQ").

## Architecture

| Layer | Technology |
|-------|-----------|
| API | FastAPI (Python 3.12+) |
| DB | Postgres (RDS) + pgvector extension |
| Embeddings | Amazon Bedrock Titan Embed (`amazon.titan-embed-text-v2:0`) — 1024 dims |
| LLM | Amazon Bedrock Claude (`anthropic.claude-3-haiku`) |
| Auth | API-key (X-API-Key header) |

## Quick Start

### 1. Clone and navigate

```bash
cd target-apps/team-faq-bot
```

### 2. Create virtual environment

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**Bash (macOS / Linux / WSL):**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env` with your actual RDS credentials and API keys.

> **IMPORTANT:** Every line in `.env` needs the variable name — paste `DATABASE_URL=postgresql+psycopg://...`, never a bare URL without the `DATABASE_URL=` prefix.

### 4. Run the API

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 5. Verify

```bash
curl http://localhost:8000/health
# → {"status":"ok","checks":{"api":"ok","database":"ok"}}
```

## API Endpoints & Auth

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/health` | None | Liveness + DB ping |
| `POST` | `/api/v1/ask` | User API key (`X-API-Key`) | Ask a question |
| `POST` | `/api/v1/upload` | Admin API key (`X-API-Key`) | Upload FAQ file |
| `GET` | `/api/v1/gaps` | Admin API key (`X-API-Key`) | List unanswered questions |

### Role & Endpoint Quick Reference

| Role | API Key Env Var | Accessible Endpoints |
|------|----------------|---------------------|
| User | `API_KEY` | `POST /api/v1/ask` |
| Admin | `ADMIN_API_KEY` | `POST /api/v1/upload`, `GET /api/v1/gaps` |

### Swagger Auth

1. Open `http://localhost:8000/docs`
2. For user endpoints: pass header `X-API-Key: <your API_KEY value>`
3. For admin endpoints: pass header `X-API-Key: <your ADMIN_API_KEY value>`

You can use "Try it out" in Swagger — add `X-API-Key` in the request headers.

## Example Requests

### Ask a question
```bash
curl -X POST http://localhost:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-api-key-change-me" \
  -d '{"question": "How do I request PTO?"}'
```

### Upload FAQ file (admin)
```bash
curl -X POST http://localhost:8000/api/v1/upload \
  -H "X-API-Key: dev-admin-key-change-me" \
  -F "file=@my-faq.txt"
```

### Get gap list (admin)
```bash
curl http://localhost:8000/api/v1/gaps?from=2024-02-01&to=2024-02-28 \
  -H "X-API-Key: dev-admin-key-change-me"
```

## Seed Data (after RDS apply)

The database seed (`005_seed.sql`) creates:

| Table | Count | Notes |
|-------|-------|-------|
| `faq_collection` | 5 rows | ID 1 is active |
| `faq_chunks` | 6 rows | Linked to collection ID 1 (zero vectors as dev placeholders) |
| `question_log` | 8 rows | Mix of `answered` and `not_in_faq` |

### Seed IDs for Testing

- Active FAQ collection: `id = 1` (filename: `engineering-faq-v1.txt`)
- Gap questions (not_in_faq): IDs 3, 4, 6, 7

## RDS Smoke Test

After `.env` is configured with real RDS credentials:

```bash
# Health check (verifies DB connectivity)
curl http://localhost:8000/health
# Expected: {"status":"ok","checks":{"api":"ok","database":"ok"}}

# List gaps (verifies seed data)
curl http://localhost:8000/api/v1/gaps \
  -H "X-API-Key: <ADMIN_API_KEY>"
# Expected: JSON array of not_in_faq entries
```

## Running Tests

```bash
pytest -q
```

Tests use an in-memory SQLite database with mocked Bedrock calls — no AWS credentials or live DB required.

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | — | Postgres DSN (`postgresql+psycopg://...?sslmode=require`) |
| `POSTGRES_SCHEMA` | Yes | `team_faq_bot` | Schema for all tables |
| `API_KEY` | Yes | — | User API key for `/ask` |
| `ADMIN_API_KEY` | Yes | — | Admin API key for `/upload`, `/gaps` |
| `AWS_REGION` | Yes | `us-east-2` | AWS region for Bedrock |
| `BEDROCK_MODEL_ID` | Yes | `anthropic.claude-3-haiku-20240307-v1:0` | Bedrock LLM model |
| `BEDROCK_EMBED_MODEL_ID` | Yes | `amazon.titan-embed-text-v2:0` | Embedding model |
| `CONFIDENCE_THRESHOLD` | No | `0.75` | Min cosine similarity for FAQ match |
| `RETRIEVAL_TOP_K` | No | `5` | Number of chunks to retrieve |
| `FAQ_MAX_CHARS` | No | `50000` | Max upload file size (chars) |
| `RETENTION_DAYS` | No | `90` | Question log retention period |
