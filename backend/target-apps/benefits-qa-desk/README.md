# Benefits Q&A Desk

Internal HR tool for uploading benefit PDFs into named collections and answering employee questions via RAG (pgvector + Amazon Bedrock). FastAPI backend enforces RBAC; Streamlit frontend communicates exclusively via HTTP.

## Demo Accounts

| Username | Password | Role |
|----------|----------|------|
| `admin` | `BenefitsDemo1!` | admin |
| `hr_contributor` | `BenefitsDemo1!` | contributor |
| `employee1` | `BenefitsDemo1!` | employee |
| `employee2` | `BenefitsDemo1!` | employee |
| `hr_manager` | `BenefitsDemo1!` | contributor |

## Role & Endpoint Quick Reference

| Role | Accessible Endpoints |
|------|---------------------|
| **employee** | `GET /api/v1/collections`, `GET /api/v1/collections/{id}/documents`, `POST /api/v1/collections/{id}/ask`, `GET /api/v1/faq-topics` |
| **contributor** | All employee endpoints + `POST /api/v1/collections`, `PATCH /api/v1/collections/{id}`, `POST /api/v1/collections/{id}/documents`, `POST /api/v1/faq-topics` |
| **admin** | All contributor endpoints + `GET /api/v1/audit` |

## Setup

### Prerequisites

- Python 3.12+
- Access to Postgres RDS (or local Postgres with pgvector)
- AWS credentials configured for Bedrock access (region: `us-east-2`)

### 1. Create virtual environment

**PowerShell (Windows):**
```powershell
cd target-apps/benefits-qa-desk
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**Bash (macOS/Linux):**
```bash
cd target-apps/benefits-qa-desk
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` with your actual values:
- **`DATABASE_URL`** — must start with `DATABASE_URL=postgresql+psycopg://...` (never paste a bare URL)
- **`JWT_SECRET_KEY`** — set to a long random string for production
- **`AWS_REGION`** — should be `us-east-2` (same region as RDS and Bedrock)

### 3. Terminal 1 — Start the API

**PowerShell (Windows):**
```powershell
cd target-apps/benefits-qa-desk
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000 --reload-dir app --reload-dir schemas
```

**Bash:**
```bash
cd target-apps/benefits-qa-desk
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000 --reload-dir app --reload-dir schemas
```

### 4. Terminal 2 — Start the Streamlit UI

**PowerShell (Windows):**
```powershell
cd target-apps/benefits-qa-desk
.\.venv\Scripts\Activate.ps1
cd ui
pip install -r requirements.txt
streamlit run streamlit_app.py --server.port 8501
```

**Bash:**
```bash
cd target-apps/benefits-qa-desk
source .venv/bin/activate
cd ui
pip install -r requirements.txt
streamlit run streamlit_app.py --server.port 8501
```

## Swagger UI / API Auth

Open `http://localhost:8000/docs` in your browser.

1. Click **Authorize** (lock icon)
2. First, obtain a token: `POST /auth/token` with body `{"username": "admin", "password": "BenefitsDemo1!"}`
3. Copy the `access_token` value
4. In the Authorize dialog, enter: `Bearer <your_token>`
5. Now all protected endpoints are accessible

## Seed UUIDs

| Entity | ID | Name |
|--------|-----|------|
| Admin user | `a1b2c3d4-0001-4000-8000-000000000001` | admin |
| HR Contributor | `a1b2c3d4-0002-4000-8000-000000000002` | hr_contributor |
| Employee 1 | `a1b2c3d4-0003-4000-8000-000000000003` | employee1 |
| Collection | `b1b2c3d4-0001-4000-8000-000000000001` | 2026 Benefits Demo |
| Document (ready) | `c1b2c3d4-0001-4000-8000-000000000001` | 2026_benefits_summary.pdf |

## RDS Smoke Test

After starting the API with a valid `.env`:

```bash
# Health check (should return {"status":"ok","checks":{"database":"ok"}})
curl http://localhost:8000/health

# Login
TOKEN=$(curl -s http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"username":"employee1","password":"BenefitsDemo1!"}' | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# List collections (DB list route)
curl http://localhost:8000/api/v1/collections \
  -H "Authorization: Bearer $TOKEN"
```

## Running Tests

```bash
cd target-apps/benefits-qa-desk
pytest tests/ -q
```

## Architecture

- **API:** FastAPI under `app/` — all business logic, RBAC, Bedrock calls
- **UI:** Streamlit under `ui/` — calls API over HTTP only; never imports `app/`
- **Auth:** JWT Bearer (PyJWT, 8-hour TTL)
- **Database:** Postgres + pgvector (schema: `benefits_qa_desk`)
- **AI:** Amazon Bedrock (Titan Embed v2 for embeddings, Claude for answers)
