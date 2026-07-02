# PR Diff Summarizer

AI-powered PR diff summarization and risk scoring service. Submit raw PR diffs, get structured summaries and risk assessments powered by AWS Bedrock (Claude Sonnet).

## Features

- **Submit PR diffs** — AI generates 2–4 sentence summaries with risk scoring
- **Heuristic risk adjustment** — deterministic rules for infrastructure, secrets, and small diffs
- **Risk classification** — low (0–30), medium (31–70), high (71–100)
- **Review history** — paginated, filterable by risk band
- **30-day statistics** — aggregate risk distribution
- **Streamlit dashboard** — three-tab UI for Submit, History, and Stats

## Architecture

- **API**: FastAPI (Python 3.12+)
- **Database**: PostgreSQL (RDS) with SQLAlchemy 2.x
- **LLM**: AWS Bedrock Claude Sonnet
- **UI**: Streamlit (calls API over HTTP only)
- **Auth**: API Key (`X-API-Key` header)

---

## Local Development

### Terminal 1 — API Server

**PowerShell (Windows):**
```powershell
cd target-apps/pr-diff-summarizer
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env — fill in DATABASE_URL, API_KEY, etc.
uvicorn app.main:app --reload --reload-dir app --reload-dir schemas --port 8000
```

**Bash (Linux/macOS):**
```bash
cd target-apps/pr-diff-summarizer
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env — fill in DATABASE_URL, API_KEY, etc.
uvicorn app.main:app --reload --reload-dir app --reload-dir schemas --port 8000
```

> ⚠️ **Important:** Do not paste a bare URL — always include the variable name `DATABASE_URL=postgresql+psycopg://...`.

> ⚠️ **Reload note:** Use `--reload-dir app --reload-dir schemas` instead of bare `--reload` to avoid watching `.venv/` which causes reload storms and Streamlit API timeouts.

### Terminal 2 — Streamlit UI

**PowerShell (Windows):**
```powershell
cd target-apps/pr-diff-summarizer
.\.venv\Scripts\Activate.ps1
cd ui
pip install -r requirements.txt
streamlit run streamlit_app.py --server.port 8501
```

**Bash (Linux/macOS):**
```bash
cd target-apps/pr-diff-summarizer
source .venv/bin/activate
cd ui
pip install -r requirements.txt
streamlit run streamlit_app.py --server.port 8501
```

The Streamlit app reads `API_KEY` and `API_BASE_URL` from the project `.env` file.
Open **http://localhost:8501** in your browser.

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | *(required)* |
| `POSTGRES_SCHEMA` | Database schema name | `pr_diff_summarizer` |
| `API_KEY` | API authentication key | *(required)* |
| `AWS_REGION` | AWS region for Bedrock | `us-east-2` |
| `BEDROCK_MODEL_ID` | Bedrock model identifier | `us.anthropic.claude-sonnet-4-20250514-v1:0` |
| `MAX_DIFF_BYTES` | Max diff size in bytes | `102400` |
| `APP_ENV` | Environment (development/production) | `development` |
| `PORT` | Server port | `8000` |
| `API_BASE_URL` | API URL for Streamlit | `http://localhost:8000` |

> Passwords containing special characters (e.g. `#`) must be URL-encoded in `DATABASE_URL` (e.g. `#` → `%23`).

---

## Database Setup

SQL migrations are in `db/sql/`. Apply them in order to your Postgres instance:

1. `001_create_enum_risk_band.sql` — creates `risk_band_enum` type
2. `002_create_reviews.sql` — creates `reviews` table with indexes
3. `011_seed.sql` (optional) — 7 dev fixture rows covering all risk bands

---

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/reviews` | ✅ `X-API-Key` | Submit diff for AI review (201) |
| `GET` | `/reviews` | ✅ `X-API-Key` | List reviews — `?limit=20&offset=0&risk_band=low` |
| `GET` | `/reviews/{id}` | ✅ `X-API-Key` | Get single review (200 / 404) |
| `GET` | `/stats` | ✅ `X-API-Key` | Risk distribution stats (30 days) |
| `GET` | `/health` | ❌ | Health check (DB + Bedrock client) |

---

## Manual API Test (Swagger)

Open **http://localhost:8000/docs** → click **Authorize** → enter your API key in the `X-API-Key` field.

**curl example — submit a review:**
```bash
curl -X POST http://localhost:8000/reviews \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{"title": "Test PR", "diff_text": "diff --git a/f.py b/f.py\n+hello"}'
```

**PowerShell example:**
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/reviews" -Method Post `
  -Headers @{"X-API-Key"="your-api-key-here"; "Content-Type"="application/json"} `
  -Body '{"title": "Test PR", "diff_text": "diff --git a/f.py b/f.py\n+hello"}'
```

**curl example — list reviews:**
```bash
curl http://localhost:8000/reviews?limit=10 \
  -H "X-API-Key: your-api-key-here"
```

**curl example — get stats:**
```bash
curl http://localhost:8000/stats \
  -H "X-API-Key: your-api-key-here"
```

---

## Testing

Run the test suite (no AWS credentials required — Bedrock is mocked):

```bash
cd target-apps/pr-diff-summarizer
pytest -q
```

All tests run with SQLite in-memory and mocked Bedrock client. Passing tests ≠ proof that RDS works — always run the RDS smoke test below with a live Postgres connection.

---

## RDS Smoke Test

After configuring `.env` with a real RDS connection:

```bash
# 1. Verify health
curl http://localhost:8000/health

# 2. Submit a review (needs Bedrock access)
curl -X POST http://localhost:8000/reviews \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{"title": "Smoke test PR", "diff_text": "diff --git a/f.py b/f.py\n+hello"}'

# 3. List reviews
curl http://localhost:8000/reviews \
  -H "X-API-Key: your-api-key-here"

# 4. Get stats
curl http://localhost:8000/stats \
  -H "X-API-Key: your-api-key-here"
```

Seed data IDs (from `011_seed.sql`):
- `a1b2c3d4-0001-4000-8000-000000000001` — low risk (25)
- `a1b2c3d4-0003-4000-8000-000000000003` — high risk (80)
- `a1b2c3d4-0005-4000-8000-000000000005` — medium risk (65)

---

## Deployment (AWS dev — devops-agent)

- Port: `8000`
- Health: `GET /health`
- Entry: `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}`
- Env: loaded from AWS Secrets Manager / SSM
- Region: `us-east-2`
