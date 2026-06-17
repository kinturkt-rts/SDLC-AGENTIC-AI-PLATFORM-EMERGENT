# Healthcare Clinic Assistant — FAQ Chatbot API

A FastAPI + Streamlit demo chatbot that answers clinic FAQ questions grounded in Postgres-stored entries via AWS Bedrock. Single-clinic MVP; no HIPAA scope.

## Architecture

| Layer | Technology |
|-------|-----------|
| API | FastAPI + Uvicorn (Python 3.12) |
| ORM | SQLAlchemy 2.x + psycopg 3 |
| AI | AWS Bedrock (Claude) via boto3 |
| Auth | JWT bearer tokens (bcrypt + PyJWT) |
| UI | Streamlit (separate process) |
| DB | PostgreSQL (AWS RDS) |

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | Public | Health check |
| POST | `/auth/login` | Public | Get JWT token |
| POST | `/chat/sessions` | Public | Create chat session |
| POST | `/chat/message` | Public | Send message, get AI response |
| GET | `/chat/sessions/{session_id}/messages` | Public | Get session history |
| GET | `/faqs` | Public | List FAQ entries |
| POST | `/faqs` | Staff JWT | Create FAQ entry |
| PUT | `/faqs/{faq_id}` | Staff JWT | Update FAQ entry |
| GET | `/admin/stats` | Staff JWT | Admin dashboard stats |

---

## Local Development

### Terminal 1 — API Server

**From the repo root:**

```bash
# Navigate to the app directory
cd target-apps/healthcare-clinic-bot

# Create virtual environment
python -m venv .venv

# Activate (bash/macOS/Linux)
source .venv/bin/activate

# Activate (Windows PowerShell)
# .venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Copy env config
cp .env.example .env        # bash/macOS/Linux
# copy .env.example .env    # Windows CMD

# Edit .env — set DATABASE_URL, JWT_SECRET_KEY, AWS credentials

# Run the API server
uvicorn app.main:app --reload --port 8000
```

API available at: http://localhost:8000  
Swagger docs at: http://localhost:8000/docs

### Terminal 2 — Streamlit UI

**From the repo root:**

```bash
cd target-apps/healthcare-clinic-bot
source .venv/bin/activate       # or .venv\Scripts\Activate.ps1 on Windows
cd ui
pip install -r requirements.txt
streamlit run streamlit_app.py --server.port 8501
```

UI available at: http://localhost:8501

### Running Tests

```bash
cd target-apps/healthcare-clinic-bot
source .venv/bin/activate
pip install pytest httpx
pytest tests/ -q
```

> **Note:** Tests use SQLite in-memory — passing tests ≠ RDS proof. Always run the RDS smoke test below.

---

## Manual API Test (Swagger)

1. Open http://localhost:8000/docs
2. **Login:** Use `POST /auth/login` with `{"username": "admin", "password": "changeme"}` (seeded user)

   If login returns 401 after an earlier seed run, apply `db/sql/012_fix_staff_passwords.sql`
   (older seeds used a placeholder bcrypt hash that did not match `changeme`).
3. Copy the `access_token` from the response
4. Click "Authorize" (🔒) → enter `Bearer <your_token>`
5. Now staff-only endpoints (POST /faqs, PUT /faqs/{id}, GET /admin/stats) are accessible

### curl Examples

```bash
# Health check
curl http://localhost:8000/health

# Login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "changeme"}'

# Create a chat session
curl -X POST http://localhost:8000/chat/sessions \
  -H "Content-Type: application/json" \
  -d '{"session_label": "My Demo"}'

# Send a message (replace SESSION_ID)
curl -X POST http://localhost:8000/chat/message \
  -H "Content-Type: application/json" \
  -d '{"session_id": "SESSION_ID", "message": "What are your hours?"}'

# List FAQs
curl http://localhost:8000/faqs

# Create FAQ (staff auth required)
curl -X POST http://localhost:8000/faqs \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"category": "general", "question": "Do you have WiFi?", "answer": "Yes, free WiFi available."}'
```

### PowerShell Example

```powershell
# Health check
Invoke-RestMethod -Uri http://localhost:8000/health

# Login
$body = @{username="admin"; password="changeme"} | ConvertTo-Json
$resp = Invoke-RestMethod -Uri http://localhost:8000/auth/login -Method Post -Body $body -ContentType "application/json"
$token = $resp.access_token

# List FAQs
Invoke-RestMethod -Uri http://localhost:8000/faqs

# Create FAQ (authenticated)
$headers = @{Authorization="Bearer $token"}
$faqBody = @{category="general"; question="WiFi?"; answer="Yes."} | ConvertTo-Json
Invoke-RestMethod -Uri http://localhost:8000/faqs -Method Post -Body $faqBody -ContentType "application/json" -Headers $headers
```

---

## RDS Smoke Test

After filling `.env` with real RDS credentials:

1. **Health check:**
   ```bash
   curl http://localhost:8000/health
   # → {"status":"ok"}
   ```

2. **List FAQs** (verifies DB connectivity + seed data):
   ```bash
   curl http://localhost:8000/faqs
   # Should return 8 seeded FAQ entries
   ```

3. **Login with seeded admin:**
   ```bash
   curl -X POST http://localhost:8000/auth/login \
     -H "Content-Type: application/json" \
     -d '{"username": "admin", "password": "changeme"}'
   ```

4. **Chat test** (verifies Bedrock connectivity):
   ```bash
   # Create session
   curl -X POST http://localhost:8000/chat/sessions \
     -H "Content-Type: application/json" \
     -d '{}' 
   # Use the session_id from response
   curl -X POST http://localhost:8000/chat/message \
     -H "Content-Type: application/json" \
     -d '{"session_id": "b2c3d4e5-0001-4000-8000-000000000001", "message": "What are your hours?"}'
   ```

### Seed UUIDs (from `db/sql/011_seed.sql`)

| Entity | ID | Description |
|--------|----|-------------|
| User | `a1b2c3d4-0001-4000-8000-000000000001` | admin (staff) |
| User | `a1b2c3d4-0002-4000-8000-000000000002` | dr.jones (staff) |
| Session | `b2c3d4e5-0001-4000-8000-000000000001` | Demo: Office Hours |
| Session | `b2c3d4e5-0002-4000-8000-000000000002` | Demo: Insurance |
| Session | `b2c3d4e5-0003-4000-8000-000000000003` | Demo: Parking |

---

## .env Configuration

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | `postgresql+psycopg://user:pass@host:5432/db?sslmode=require` |
| `POSTGRES_SCHEMA` | Yes | `healthcare_clinic_bot` |
| `JWT_SECRET_KEY` | Yes | Random secret for token signing |
| `JWT_ALGORITHM` | No | Default: `HS256` |
| `JWT_EXPIRE_MINUTES` | No | Default: `480` (8 hours) |
| `BEDROCK_MODEL_ID` | No | Default: `us.anthropic.claude-sonnet-4-20250514-v1:0` |
| `AWS_REGION` | No | Default: `us-east-2` |
| `FAQ_RELEVANCE_THRESHOLD` | No | Default: `0.1` |
| `PORT` | No | Default: `8000` |

> **Password encoding:** If your RDS password contains `#`, encode it as `%23` in the URL.

---

## Deployment (AWS dev — devops-agent)

- **Port:** 8000
- **Health:** `GET /health`
- **Entry:** `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}`
- **Env vars:** See `.env.example` — inject via AWS Secrets Manager or SSM Parameter Store
- **AWS auth:** Task IAM role with `bedrock:InvokeModel` permission for the configured model
- **DB:** RDS Postgres (schema `healthcare_clinic_bot`) — run SQL files in `db/sql/` order
