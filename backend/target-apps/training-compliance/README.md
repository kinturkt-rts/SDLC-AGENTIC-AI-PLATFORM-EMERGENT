# Training & Certification Compliance

Centralises course catalog, employee roster, and completion records for a single org. Derives real-time compliance status (current / expired / missing) per employee. JWT-gated FastAPI REST API with four role-gated Streamlit UI screens.

## Quick Start

### Prerequisites

- Python 3.12+
- PostgreSQL (RDS) or local Postgres

### Setup (Windows PowerShell)

```powershell
cd target-apps/training-compliance
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Setup (Bash / macOS / Linux)

```bash
cd target-apps/training-compliance
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Configure Environment

```bash
cp .env.example .env
# Edit .env with your actual DATABASE_URL and JWT_SECRET_KEY
```

> ⚠️ **IMPORTANT:** Every line in `.env` needs the variable name — paste `DATABASE_URL=postgresql+psycopg://...`, not a bare URL.

### Run Migrations & Seed

The pipeline runs `scripts/apply_sql_to_rds.py`, which applies SQL to RDS and **automatically materializes bcrypt passwords** (no manual hash step). Re-apply only if you change seed SQL:

```bash
python scripts/apply_sql_to_rds.py --target-app training-compliance
```

### Terminal 1 — Start API

```bash
cd target-apps/training-compliance
.venv\Scripts\Activate.ps1  # or source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

### Terminal 2 — Start Streamlit UI

```bash
cd target-apps/training-compliance
.venv\Scripts\Activate.ps1  # or source .venv/bin/activate
cd ui
pip install -r requirements.txt
streamlit run streamlit_app.py --server.port 8501
```

UI: [http://localhost:8501](http://localhost:8501)

---

## Authentication

All endpoints (except `GET /health`) require a JWT Bearer token.

### Get a Token (Swagger)

1. Open [http://localhost:8000/docs](http://localhost:8000/docs)
2. Call `POST /auth/token` with body:
  ```json
   {"email": "marcus.chen@example.com", "password": "TrainingPass123!"}
  ```
3. Copy the `access_token` from the response
4. Click "Authorize" button → paste `Bearer <your_token>`

### Swagger Auth Header

In Swagger UI, use the Authorize button or add header:

```
Authorization: Bearer <access_token>
```

---

## Role & Endpoint Quick Reference


| Role                   | Seed User     | Email                                                         | Endpoints                                                                                                             |
| ---------------------- | ------------- | ------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| **hr_admin**           | Marcus Chen   | [marcus.chen@example.com](mailto:marcus.chen@example.com)     | All CRUD: `/courses`, `/employees`, `/requirements`, `/completions`, `/compliance/`*, `/reports/dashboard`, `/alerts` |
| **manager**            | Priya Sharma  | [priya.sharma@example.com](mailto:priya.sharma@example.com)   | `/compliance/team`, `/compliance/employee/{id}` (own team), `/alerts`                                                 |
| **employee**           | Alice Johnson | [alice.johnson@example.com](mailto:alice.johnson@example.com) | `/compliance/employee/{own_id}`, `POST /completions` (self only)                                                      |
| **compliance_officer** | David Okonkwo | [david.okonkwo@example.com](mailto:david.okonkwo@example.com) | All GET read endpoints, `/reports/dashboard`, `/alerts`                                                               |


**Password for all seed users:** `TrainingPass123!`

---

## Seed Data UUIDs


| Entity     | Name                           | UUID                                   |
| ---------- | ------------------------------ | -------------------------------------- |
| Department | Engineering                    | `a0000000-0000-4000-8000-000000000001` |
| Department | Operations                     | `a0000000-0000-4000-8000-000000000002` |
| Department | Finance                        | `a0000000-0000-4000-8000-000000000003` |
| Job Role   | Software Engineer              | `b0000000-0000-4000-8000-000000000001` |
| Job Role   | Operations Analyst             | `b0000000-0000-4000-8000-000000000002` |
| Job Role   | Finance Manager                | `b0000000-0000-4000-8000-000000000003` |
| Course     | Workplace Safety Fundamentals  | `c0000000-0000-4000-8000-000000000001` |
| Course     | Information Security Awareness | `c0000000-0000-4000-8000-000000000002` |
| Course     | Secure Coding Practices        | `c0000000-0000-4000-8000-000000000003` |
| Employee   | Marcus Chen (HR admin)         | `d0000000-0000-4000-8000-000000000001` |
| Employee   | Priya Sharma (Manager)         | `d0000000-0000-4000-8000-000000000002` |
| Employee   | Alice Johnson                  | `d0000000-0000-4000-8000-000000000004` |
| User       | Marcus (hr_admin)              | `10000000-0000-4000-8000-000000000001` |
| User       | Priya (manager)                | `10000000-0000-4000-8000-000000000002` |
| User       | Alice (employee)               | `10000000-0000-4000-8000-000000000003` |
| User       | David (compliance_officer)     | `10000000-0000-4000-8000-000000000004` |


---

## RDS Smoke Test

After configuring `.env` with your RDS credentials:

```bash
# 1. Health check (no auth required)
curl http://localhost:8000/health
# Expected: {"status":"ok","checks":{"api":"ok","database":"ok"}}

# 2. Get token
TOKEN=$(curl -s -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"email":"marcus.chen@example.com","password":"TrainingPass123!"}' | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 3. List courses (DB read test)
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/courses
# Expected: JSON array of 6 courses from seed data
```

---

## API Endpoints


| Method          | Path                                  | Auth                   | Description             |
| --------------- | ------------------------------------- | ---------------------- | ----------------------- |
| GET             | `/health`                             | None                   | Health + DB ping        |
| POST            | `/auth/token`                         | None                   | Login, get JWT          |
| GET/POST/PATCH  | `/courses`, `/courses/{id}`           | JWT (HR admin write)   | Course catalog          |
| GET/POST/PATCH  | `/employees`, `/employees/{id}`       | JWT (HR admin write)   | Employee roster         |
| GET/POST/DELETE | `/requirements`, `/requirements/{id}` | JWT (HR admin)         | Role-course matrix      |
| POST            | `/completions`                        | JWT (HR admin or self) | Record completion       |
| GET             | `/compliance/employee/{id}`           | JWT (scoped)           | Per-employee compliance |
| GET             | `/compliance/team`                    | JWT (manager+)         | Team compliance view    |
| GET             | `/reports/dashboard`                  | JWT (CO/HR admin)      | Org-wide dashboard      |
| GET             | `/alerts`                             | JWT (manager/CO/HR)    | Compliance alerts       |


---

## Running Tests

```bash
cd target-apps/training-compliance
pip install pytest httpx
pytest tests/ -v
```

Tests use in-memory SQLite — no database required.

---

## Project Structure

```
target-apps/training-compliance/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app with lifespan
│   ├── config.py            # Settings from env
│   ├── database.py          # SQLAlchemy engine/session
│   ├── startup_checks.py    # Fail-fast validation
│   ├── security.py          # JWT + bcrypt utilities
│   ├── dependencies.py      # Auth dependencies
│   ├── models/
│   │   ├── __init__.py
│   │   ├── pg_types.py      # ENUM + UUID helpers
│   │   └── entities.py      # ORM models
│   └── routers/
│       ├── __init__.py
│       ├── health.py
│       ├── auth.py
│       ├── courses.py
│       ├── employees.py
│       ├── requirements.py
│       ├── completions.py
│       ├── compliance.py
│       ├── reports.py
│       └── alerts.py
├── schemas/
│   ├── __init__.py
│   ├── auth.py
│   ├── courses.py
│   ├── employees.py
│   ├── requirements.py
│   ├── completions.py
│   └── compliance.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_health.py
│   ├── test_auth.py
│   ├── test_courses.py
│   ├── test_employees.py
│   ├── test_requirements.py
│   ├── test_completions.py
│   ├── test_compliance.py
│   ├── test_reports.py
│   └── test_alerts.py
├── ui/
│   ├── streamlit_app.py     # Streamlit UI (Terminal 2)
│   └── requirements.txt
├── scripts/
│   └── seed_dev_users.py    # Bcrypt placeholder replacer
├── db/sql/                   # DDL + seed (read-only)
├── requirements.txt
├── .env.example
├── .gitignore
├── pytest.ini
└── README.md
```

