# Training & Certification Compliance — Solution Design

## 1. Summary
Single-org training compliance platform: HR admins manage a course catalog and record completions; managers, employees, and compliance officers get role-scoped views of compliance status. FastAPI + Postgres backend; Streamlit frontend; API-key auth via `X-API-Key` header.
TBD: OQ-2 (employee self-record), OQ-4 (validity=0 semantics), OQ-6 (soft-delete cascade to requirements).
Diagram: `docs/generated-diagrams/training-compliance.png`

## 2. Stack
| Layer | Technology | Path / Notes |
|-------|-----------|--------------|
| API | FastAPI (Uvicorn) | `target-apps/training-compliance/app/` |
| UI | Streamlit | `ui/streamlit_app.py` calls FastAPI over HTTP (port 8501) |
| Database | PostgreSQL (RDS / Docker) | Single instance, pgvector not required |
| Auth | API key in `.env` | `X-API-Key` header; `Depends(require_api_key)` + role from `users.role` |
| ORM | SQLAlchemy + Alembic | Migrations in `alembic/versions/` |
| Container | Docker Compose | Services: `api`, `ui`, `db` |

## 3. Data model
| Table | Columns | Indexes / constraints |
|-------|---------|----------------------|
| `departments` | `id uuid PK`, `name text UNIQUE` | — |
| `job_roles` | `id uuid PK`, `name text UNIQUE` | — |
| `courses` | `id uuid PK`, `name text`, `category varchar CHECK(safety\|security\|role_specific)`, `validity_period_months int nullable`, `required_for_all bool DEFAULT false`, `is_active bool DEFAULT true`, `reference_notes text` | idx on `is_active` |
| `employees` | `id uuid PK`, `full_name text`, `email text UNIQUE`, `department_id uuid FK(departments)`, `job_role_id uuid FK(job_roles)`, `manager_id uuid FK(employees) nullable`, `active bool DEFAULT true`, `created_at timestamptz` | idx `(manager_id, active)` |
| `role_requirements` | `id uuid PK`, `job_role_id uuid FK`, `course_id uuid FK`, `assigned_at timestamptz`, `removed_at timestamptz nullable` | UNIQUE `(job_role_id, course_id)` partial where `removed_at IS NULL` |
| `completion_records` | `id uuid PK`, `employee_id uuid FK`, `course_id uuid FK`, `completion_date date`, `expiry_date date nullable`, `status varchar CHECK(active\|archived)`, `certificate_reference text`, `recorded_by_employee_id uuid FK`, `created_at timestamptz` | UNIQUE `(employee_id, course_id)` partial where `status='active'`; idx `(employee_id, status)` |
| `users` | `id uuid PK`, `employee_id uuid FK(employees) nullable`, `role varchar CHECK(hr_admin\|manager\|employee\|compliance_officer)`, `api_key_hash text UNIQUE` | idx `api_key_hash` |
| `audit_log` | `id uuid PK`, `user_id uuid FK`, `user_role varchar`, `action text`, `resource_type text`, `resource_id uuid`, `ts timestamptz DEFAULT now()` | idx `(resource_type, resource_id)` |

## 4. API surface
| Method | Path | Request | Response | Notes |
|--------|------|---------|----------|-------|
| GET | `/health` | — | `{status, db}` | No auth (NFR-9) |
| POST | `/api/v1/auth/login` | `{api_key: str}` | `{role, employee_id, token}` | Returns role for UI routing |
| GET/POST | `/api/v1/courses` | POST: `{name, category, validity_period_months, required_for_all, reference_notes}` | Course object / list | hr_admin write; all roles read active |
| PATCH/DELETE | `/api/v1/courses/{id}` | `{field: value}` | Course object | DELETE = soft (`is_active=false`) |
| GET/POST | `/api/v1/employees` | POST: `{full_name, email, department_id, job_role_id, manager_id}` | Employee / list | hr_admin write; manager read own team |
| PATCH | `/api/v1/employees/{id}` | `{active?, full_name?, ...}` | Employee object | hr_admin only; deactivate sets `active=false` |
| GET/POST | `/api/v1/completions` | POST: `{employee_id, course_id, completion_date, certificate_reference?}` | Completion record | hr_admin only; archives prior active record in transaction |
| GET | `/api/v1/compliance/me` | — | `[{course, status, expiry_date}]` | Employee self-view (FR-6) |
| GET | `/api/v1/manager/team-compliance` | — | `[{employee, course, status}]` | Scoped to `manager_id=current_user` (FR-7) |
| GET | `/api/v1/reports/org` | `?view=overdue\|expiring\|rate_by_dept\|worst_gap` | Aggregate data | compliance_officer + hr_admin read-only (FR-9) |

## 5. Rules
- **API-key auth (NFR-3, NFR-4):** Every non-health endpoint calls `Depends(require_api_key)` which hashes incoming `X-API-Key`, looks up `users.api_key_hash`, attaches `CurrentUser(role, employee_id)`; missing/invalid → 401. Streamlit: `login_form()` gates ALL views when `st.session_state.token` absent; stores `role` from login response.
- **RBAC (FR-6, FR-7, FR-8, FR-9, NFR-4):** `Depends(require_role(*roles))` on every route; employee → own records only (filter `employee_id=current`); manager → `manager_id=current` filter; compliance_officer → GET-only on `/reports/org` + `/employees` (POST/PATCH → 403); hr_admin → unrestricted. Streamlit tabs: employee=my-trainings, manager=team-board, compliance_officer=org-dashboard, hr_admin=catalog+roster+completions.
- **Row-level isolation (FR-6, FR-7, NFR-4):** API service layer appends ownership filters before every query; no raw `employee_id` param accepted from employee/manager roles — ID sourced only from `CurrentUser`.
- **Recertification atomicity (FR-4, NFR-10):** `POST /completions` runs in a single DB transaction: `UPDATE completion_records SET status='archived' WHERE employee_id=? AND course_id=? AND status='active'` then inserts new active record; unique partial index prevents duplicates. Prior record count unchanged (audit trail preserved).
- **Compliance status derivation (FR-5, NFR-12):** Computed at query time: `expiry_date IS NULL OR expiry_date > today` → `compliant`; `0 < expiry_date - today ≤ 30` → `expiring_soon`; `expiry_date ≤ today` → `expired`; no active completion → `missing`. Calendar-month arithmetic via `dateutil.relativedelta` at write time for `expiry_date`.
- **Inactive exclusion (FR-3, FR-10):** Shared query util always appends `AND employees.active = true` for compliance aggregates, manager views, and compliance officer lists; hr_admin explicit detail endpoints bypass this filter.
- **Audit logging (NFR-5, NFR-8):** FastAPI middleware writes structured JSON log (`timestamp, method, path, status_code, duration_ms, user_role, user_id`); business events (course created/updated, completion recorded/archived, employee deactivated) insert rows into `audit_log`; no PII (names/emails) in any log payload.
- **Data quality flag (FR-12):** `GET /employees/{id}` (hr_admin) counts active completions; if ≥ 21 appends `data_quality_flag: "excess_active_records"` to response; advisory only, no records blocked.

## 6. DB delivery
1. Migration order: `001_departments_job_roles.sql`, `002_courses.sql`, `003_employees.sql`, `004_role_requirements.sql`, `005_completion_records.sql`, `006_users.sql`, `007_audit_log.sql`
2. Seed data (`scripts/seed_demo_data.py`, idempotent upsert): 3 departments (Engineering, Operations, HR); 3 job roles (Engineer, Analyst, HR Manager); 6 courses (2 safety all-staff, 2 security all-staff, 2 role-specific); ≥15 active employees across all managers with mixed states (compliant, missing, expiring-within-30-days, expired); 1 inactive employee with archived completions; 4 users one per role; completion records covering all four compliance statuses; at least one department seeded below 80% completion rate.
