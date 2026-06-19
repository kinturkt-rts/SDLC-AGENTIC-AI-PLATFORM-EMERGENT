# PR Diff Summarizer

AI-powered pull request diff analysis service that generates summaries and risk scores using AWS Bedrock Claude. Provides REST API endpoints and a Streamlit UI for interactive analysis.

## Features

- 🤖 **AI Analysis**: Uses AWS Bedrock Claude Sonnet for intelligent diff summarization
- 📊 **Risk Scoring**: Combines AI assessment with code-based heuristics (0-100 scale)
- 🎯 **Risk Bands**: Categorizes PRs as low (0-30), medium (31-70), or high (71-100) risk
- 📈 **Analytics**: Track review patterns and risk distribution over time
- 🔐 **API Authentication**: Secure access via X-API-Key headers
- 💾 **PostgreSQL Storage**: Persistent review history and analysis data
- 🖥️ **Streamlit UI**: Interactive web interface for demo and testing

## API Endpoints

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/reviews/` | Analyze PR diff and create review | ✅ |
| GET | `/reviews/` | List reviews (paginated, filterable) | ✅ |
| GET | `/reviews/{id}` | Get specific review by ID | ✅ |
| GET | `/stats` | Get 30-day statistics | ✅ |
| GET | `/health` | Health check | ❌ |

## Local Development

### Prerequisites
- Python 3.12+
- PostgreSQL 13+ (or use SQLite for tests)
- AWS credentials with Bedrock access

### Setup

**Terminal 1 (API) - from repo root:**

```bash
cd target-apps/pr-diff-summarizer

# Create and activate virtual environment
# Windows:
python -m venv .venv
.venv\Scripts\activate
# Bash/Linux/macOS:
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Environment configuration
# Windows:
copy .env.example .env
# Bash:
cp .env.example .env

# Edit .env with your values (see Environment Variables section)
```

**Important**: Every line in `.env` needs the variable name — paste `DATABASE_URL=postgresql+psycopg://...`, not a bare URL.

```bash
# Start API server
uvicorn app.main:app --reload --port 8000 --reload-exclude '.venv'

# API available at: http://localhost:8000
# Swagger docs: http://localhost:8000/docs
```

**Terminal 2 (UI) - from repo root:**

```bash
cd target-apps/pr-diff-summarizer
# Activate same venv as Terminal 1
# Windows: .venv\Scripts\activate
# Bash: source .venv/bin/activate

cd ui
pip install -r requirements.txt

# Start Streamlit UI
streamlit run streamlit_app.py --server.port 8501

# UI available at: http://localhost:8501
```

### Environment Variables

| Variable | Example | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+psycopg://user:pass%23word@localhost:5432/dbname?sslmode=require` | Postgres connection (URL-encode passwords: # → %23) |
| `POSTGRES_SCHEMA` | `pr_diff_summarizer` | Database schema name |
| `API_KEY` | `your-secret-api-key-here` | Authentication key for API access |
| `AWS_REGION` | `us-east-2` | AWS region for Bedrock |
| `BEDROCK_REGION` | `us-east-2` | Specific Bedrock region |
| `BEDROCK_MODEL_ID` | `us.anthropic.claude-sonnet-4-20250514-v1:0` | Claude model identifier |
| `MAX_DIFF_SIZE_MB` | `10` | Maximum diff size limit |
| `MAX_TITLE_LENGTH` | `500` | Maximum PR title length |

### Testing

```bash
# Run tests (uses SQLite in-memory)
python -m pytest tests/ -v

# Note: Passing tests ≠ RDS proof. Always test against real Postgres after .env setup.
```

## Manual API Testing

### Swagger UI
1. Open http://localhost:8000/docs
2. Click "Authorize" button
3. Enter your API key in the "X-API-Key" field
4. Test endpoints directly in browser

### curl Examples

```bash
# Health check (no auth)
curl http://localhost:8000/health

# Create review
curl -X POST http://localhost:8000/reviews/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-api-key-here" \
  -d '{
    "title": "Add user authentication",
    "diff_text": "diff --git a/auth.py b/auth.py\nnew file mode 100644\nindex 0000000..abc123\n--- /dev/null\n+++ b/auth.py\n@@ -0,0 +1,5 @@\n+def authenticate(token):\n+    if not token:\n+        return False\n+    return validate_token(token)"
  }'

# List reviews
curl -H "X-API-Key: your-secret-api-key-here" \
  "http://localhost:8000/reviews/?limit=10&risk_band=medium"

# Get statistics  
curl -H "X-API-Key: your-secret-api-key-here" \
  http://localhost:8000/stats
```

### PowerShell Examples

```powershell
# Create review
$headers = @{ "X-API-Key" = "your-secret-api-key-here" }
$body = @{
    title = "Fix authentication bug"
    diff_text = "diff --git a/auth.py b/auth.py`n--- a/auth.py`n+++ b/auth.py`n@@ -10,1 +10,1 @@`n-    return token == 'admin'`n+    return bcrypt.checkpw(token, stored_hash)"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/reviews/" -Method POST -Headers $headers -Body $body -ContentType "application/json"
```

## RDS Smoke Test

After setting up `.env` with real PostgreSQL credentials:

1. **Health check with database:**
   ```bash
   curl http://localhost:8000/health
   # Should return: {"status": "ok", "checks": {"api": "ok", "database": "ok"}}
   ```

2. **Test with seeded data** (use seed UUIDs from `db/sql/004_seed.sql`):
   ```bash
   curl -H "X-API-Key: your-secret-api-key-here" \
     http://localhost:8000/reviews/550e8400-e29b-41d4-a716-446655440001
   ```

3. **Create new review:**
   ```bash
   curl -X POST http://localhost:8000/reviews/ \
     -H "X-API-Key: your-secret-api-key-here" \
     -H "Content-Type: application/json" \
     -d '{"title": "Test PR", "diff_text": "diff --git a/test.py b/test.py\n+print(\"hello\")"}'
   ```

## Risk Scoring Algorithm

### Base AI Score (0-100)
- AWS Bedrock Claude analyzes diff content and complexity
- Considers file types, change scope, and potential impact

### Heuristic Adjustments
- **+15 points**: Changes in `migrations/` directory
- **+10 points**: Contains security-related terms (secret, password, key, auth)
- **-10 points**: Small changes (<30 total lines)
- **Final score**: Clamped to 0-100 range

### Risk Bands
- **Low (0-30)**: Documentation, typos, minor config
- **Medium (31-70)**: Feature additions, moderate refactoring  
- **High (71-100)**: Database changes, security updates, major refactoring

## Deployment (AWS dev - devops-agent)

```bash
# Production settings
PORT=8000
uvicorn app.main:app --host 0.0.0.0 --port $PORT

# Health probe: GET /health
# Environment: Load from AWS Secrets Manager
# Required secrets: DATABASE_URL, API_KEY, AWS credentials
```

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Streamlit UI  │────│   FastAPI API    │────│   PostgreSQL    │
│  (Port 8501)    │    │   (Port 8000)    │    │  (pr_diff_...)  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                │
                         ┌─────────────────┐
                         │  AWS Bedrock    │
                         │  Claude Sonnet  │
                         └─────────────────┘
```

## Troubleshooting

### Common Issues

1. **Import errors on startup**: Check that all `app/*/` directories have `__init__.py` files

2. **Database connection fails**: 
   - Verify `DATABASE_URL` format: `postgresql+psycopg://user:password@host:port/database?sslmode=require`
   - URL-encode special characters in password (# → %23)
   - Check `POSTGRES_SCHEMA` matches database setup

3. **Bedrock errors**:
   - Verify AWS credentials and region (`us-east-2`)
   - Check IAM permissions for Bedrock access
   - Confirm model ID is correct for your region

4. **API key authentication fails**:
   - Ensure `X-API-Key` header is set correctly
   - Check that `API_KEY` environment variable matches request header

5. **Streamlit connection errors**:
   - Verify API is running on port 8000
   - Check `API_BASE_URL` environment variable
   - Ensure both services use same API key

### Debug Mode

Set `APP_ENV=development` in `.env` to get detailed error messages in API responses.

## Development Notes

- Uses SQLAlchemy 2.x with synchronous sessions
- Pydantic v2 for request/response validation  
- pytest with SQLite for fast testing
- Bedrock client mocked in tests (no live AWS calls)
- Follows FastAPI best practices for dependency injection