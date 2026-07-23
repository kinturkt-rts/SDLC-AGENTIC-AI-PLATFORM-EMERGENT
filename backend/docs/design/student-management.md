# Student Management API — Solution Design

## 1. Summary
Centralised internal REST API for student record management, replacing disconnected spreadsheets with a single authoritative PostgreSQL-backed service. FastAPI exposes full CRUD with two-tier API-key auth; a Streamlit UI provides staff-facing browse/manage views over HTTP. Diagram: `/tmp/generated-diagrams/student-management.png`
TBD: read-endpoint auth tier (env-key vs. network perimeter); seed endpoint disable flag in production.

## 2. Stack
| Layer | Technology | Path / Notes |
|-------|------------|--------------|
| UI | Streamlit | `ui/streamlit_app.py` calls FastAPI over HTTP (port 8501) |
| API | FastAPI | `target-apps/student-management/`; OpenAPI at `/docs` |
| Auth | API-key (`X-API-Key`) | `WRITE_API_KEY` / `READ_API_KEY` from `.env`; no Cognito |
| ORM | SQLAlchemy + Alembic | Async-compatible; migrations in `alembic/versions/` |
| DB | PostgreSQL (RDS) | Primary store; single-AZ sufficient for internal v1 |
| Container | ECS (Docker) behind ALB | Single container; 12-factor env config |

## 3. Data model
| Table | Columns | Indexes / Constraints |
|-------|---------|-----------------------|
| `students` | `id serial PK`, `student_id varchar UNIQUE NOT NULL`, `full_name varchar NOT NULL`, `email varchar UNIQUE NOT NULL`, `course varchar NOT NULL`, `enrollment_date date NOT NULL`, `status varchar NOT NULL DEFAULT 'active'`, `is_active bool NOT NULL DEFAULT true`, `created_at timestamptz NOT NULL DEFAULT now()`, `updated_at timestamptz NOT NULL DEFAULT now()` | `idx_students_course`, `idx_students_status`; CHECK `status IN ('active','inactive')`; CHECK `enrollment_date <= CURRENT_DATE` |

## 4. API surface
| Method | Path | Request | Response | Notes |
|--------|------|---------|----------|-------|
| GET | `/health` | — | `{status, db}` | Unauthenticated; 503 if DB unreachable (FR-10) |
| POST | `/api/v1/students` | `StudentCreate` | `StudentOut 201` | Write-key required (FR-1) |
| GET | `/api/v1/students` | `?course&status` | `list[StudentOut] 200` | Read-key required (FR-4) |
| GET | `/api/v1/students/{student_id}` | — | `StudentOut 200` | Includes inactive; 404 if missing (FR-3) |
| PUT | `/api/v1/students/{student_id}` | `StudentUpdate` | `StudentOut 200` | Write-key; 400 if `student_id` in body (FR-5) |
| PATCH | `/api/v1/students/{student_id}/deactivate` | — | `StudentOut 200` | Write-key; sets `status=inactive` (FR-6) |
| POST | `/api/v1/students/seed` | — | `{seeded: int} 200` | Write-key; idempotent upsert (FR-9) |

## 5. Rules
- **API-key auth** (FR-7, NFR-3): `WRITE_API_KEY` guards POST/PUT/PATCH; `READ_API_KEY` guards GET collection/detail; API: `Depends(require_write_key)` / `Depends(require_read_key)`; Streamlit: prompts for key in sidebar, stores in `st.session_state`; missing/invalid → 401, never logged.
- **Uniqueness** (FR-2, NFR-5): DB UNIQUE on `student_id` + `email`; API catches `IntegrityError` → 422/409; covers inactive records.
- **Enrollment date validation** (FR-8): Pydantic `@validator` rejects `enrollment_date > date.today()` → 422 with field-level error; UTC normalised server-side.
- **Soft-delete / no hard delete** (FR-6, NFR-8): DELETE route not exposed; `PATCH /deactivate` sets `status=inactive`, `is_active=false`; record remains queryable.
- **Immutable `student_id`** (FR-5): PUT handler raises 400 if `student_id` present in request body; field excluded from `StudentUpdate` schema.
- **Seed idempotency** (FR-9): Upsert on fixed `student_id` values via `ON CONFLICT DO NOTHING`; returns count of newly inserted rows.
- **Observability** (NFR-7): Starlette middleware logs method, path, status, latency on every request; errors log stack trace; seed calls tagged `seed=true` to exclude from record-count metrics.
- **Streamlit UI gates** (FR-4, FR-3): `st.session_state.api_key` required for all views; student list uses `GET /api/v1/students` with course/status filter widgets; write forms (create, update, deactivate) send write-key from session state.

## 6. DB delivery
1. Migration order: `001_create_students.sql`
2. Seed data (FR-9 fixed records):
   - `('STU-001','Alice Nguyen','alice@example.com','Computer Science','2024-01-15','active')`
   - `('STU-002','Ben Carter','ben@example.com','Data Engineering','2024-03-01','active')`
   - `('STU-003','Cleo Marsh','cleo@example.com','Cybersecurity','2023-09-10','inactive')`
3. NoSQL/Athena: not used.
