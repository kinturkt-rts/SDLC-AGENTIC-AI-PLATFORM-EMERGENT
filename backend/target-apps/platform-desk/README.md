# Platform Desk (Runbook Vector Desk)

Internal SRE operations tool that ingests structured runbooks, embeds step text for semantic search, and exposes a role-gated on-call console.

## Architecture

| Layer | Technology |
|-------|-----------|
| UI | Streamlit (`ui/streamlit_app.py`) |
| API | FastAPI (Python 3.12+) |
| Auth | API Key (`X-API-Key` header) |
| DB | PostgreSQL (RDS) via SQLAlchemy 2.x |
| Vector Store | ChromaDB (local) + sentence-transformers |
| Driver | `psycopg[binary]` (`postgresql+psycopg://`) |

---

## Quick Start

### Prerequisites
- Python 3.12+
- Access to the RDS Postgres instance (or local Postgres)

### 1. Clone & navigate

```bash
cd target-apps/platform-desk
```

### 2. Create virtual environment

**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**macOS / Linux (bash):**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env` — every line **must** be `KEY=value` format.

> ⚠️ **Important:** Paste `DATABASE_URL=postgresql+psycopg://...`, not a bare URL without the variable name prefix.

### 4. Terminal 1 — Start the API

```bash
cd target-apps/platform-desk
source .venv/bin/activate  # or .venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000 --reload-dir app --reload-dir schemas
```

Verify: `curl http://localhost:8000/health` should return `{"status":"ok","checks":{"api":"ok","database":"ok"}}`.

### 5. Terminal 2 — Start Streamlit UI

```bash
cd target-apps/platform-desk
source .venv/bin/activate  # or .venv\Scripts\Activate.ps1
pip install -r ui/requirements.txt
cd ui
streamlit run streamlit_app.py --server.port 8501
```

---

## Authentication

All endpoints except `GET /health` require the `X-API-Key` header.

In Swagger UI (`http://localhost:8000/docs`), click **Authorize** and add:
```
X-API-Key: RunbookDesk2024!
```

---

## Roles & Endpoint Quick Reference

| Role | API Key (dev) | Accessible Endpoints |
|------|---------------|---------------------|
| **viewer** | `RunbookDesk2024!` | `GET/POST /api/v1/search`, `GET /api/v1/runbooks`, `GET /api/v1/runbooks/{id}/steps`, `GET/POST /api/v1/incident-touches` |
| **editor** | `RunbookDesk2024!` | All viewer + `POST /api/v1/runbooks`, `POST .../activate`, `POST .../retire`, CRUD on steps |
| **admin** | `RunbookDesk2024!` | All editor + `GET/POST/PUT/DELETE /api/v1/services`, `GET /api/v1/admin/report/reliance`, `GET /api/v1/admin/analytics`, `GET/POST /api/v1/admin/index-refresh` |

> **Note:** The dev API key (`RunbookDesk2024!`) grants admin-level access. In production, keys are stored as SHA-256 hashes in the `api_keys` table with per-key role assignment. The seed SQL uses `__BCRYPT_PLACEHOLDER__` — RDS login will work after `python scripts/apply_sql_to_rds.py --target-app platform-desk` materializes the hashes.

---

## Seed Data (UUIDs for testing)

| Entity | ID | Description |
|--------|-----|------------|
| Service: payments-api | `a1000000-0000-0000-0000-000000000001` | Criticality 1 |
| Service: auth-gateway | `a1000000-0000-0000-0000-000000000002` | Criticality 1 |
| Runbook: Redis Connection Pool Recovery | `b2000000-0000-0000-0000-000000000001` | Active, 5 steps |
| Runbook: Database Failover Procedure | `b2000000-0000-0000-0000-000000000002` | Active, 5 steps |
| Runbook: Redis Cluster Rebalance | `b2000000-0000-0000-0000-00000000000c` | Draft, 3 steps |
| API Key (viewer) | `d4000000-0000-0000-0000-000000000001` | dev-viewer-key |
| API Key (editor) | `d4000000-0000-0000-0000-000000000002` | dev-editor-key |
| API Key (admin) | `d4000000-0000-0000-0000-000000000003` | dev-admin-key |

---

## API Surface

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | None | Liveness + DB ping |
| GET/POST | `/api/v1/services` | Admin | Service catalog CRUD |
| GET/PUT/DELETE | `/api/v1/services/{id}` | Admin | Service by ID |
| GET/POST | `/api/v1/runbooks` | Viewer+/Editor+ | List/Create runbooks |
| GET | `/api/v1/runbooks/{id}` | Viewer+ | Get runbook |
| POST | `/api/v1/runbooks/{id}/activate` | Editor+ | Activate draft |
| POST | `/api/v1/runbooks/{id}/retire` | Editor+ | Retire active |
| GET/POST | `/api/v1/runbooks/{id}/steps` | Viewer+/Editor+ | List/Create steps |
| GET/PUT/DELETE | `/api/v1/runbooks/{id}/steps/{step_id}` | Viewer+/Editor+ | Step CRUD |
| GET/POST | `/api/v1/search` | Viewer+ | Semantic symptom search |
| GET/POST | `/api/v1/incident-touches` | Viewer+ | Log incident touch |
| GET | `/api/v1/admin/report/reliance` | Admin | Service reliance report |
| GET | `/api/v1/admin/analytics` | Admin | Search analytics |
| GET/POST | `/api/v1/admin/index-refresh` | Admin | Re-index vector store |

---

## RDS Smoke Test

After `.env` is configured with your RDS credentials:

```bash
# 1. Health check (verifies DB connectivity)
curl http://localhost:8000/health

# 2. List services (verifies schema + seed data)
curl -H "X-API-Key: RunbookDesk2024!" http://localhost:8000/api/v1/services

# 3. List active runbooks
curl -H "X-API-Key: RunbookDesk2024!" "http://localhost:8000/api/v1/runbooks?lifecycle_status=active"
```

---

## Running Tests

```bash
cd target-apps/platform-desk
source .venv/bin/activate
pytest tests/ -q
```

Tests use an in-memory SQLite database (no RDS required). Vector search is disabled/mocked in tests.

---

## Optional: ChromaDB Vector Search

For semantic search to work locally, install optional dependencies:

```bash
pip install chromadb sentence-transformers
```

Without these packages, the API still functions — search returns empty results, and all CRUD operations work normally.
