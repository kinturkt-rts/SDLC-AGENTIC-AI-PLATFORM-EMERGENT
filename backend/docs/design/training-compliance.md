# Training & Certification Compliance — Solution Design

## 1. Summary
Single-org training compliance app: HR admins manage courses/rosters, managers view team gaps, employees track own status, compliance officers run audits. Postgres (RDS) stores all entities; FastAPI enforces RBAC via JWT; Streamlit provides four role-gated screens. Diagram: `docs/generated-diagrams/training-compliance.png`. TBD: deployment target, password-reset flow, retroactive expiry on validity-period change.

## 2. Stack
| Layer | Technology | Path |
|-------|------------|------|
| UI | Streamlit | `ui/streamlit_app.py` calls FastAPI over HTTP (port 8501) |
| API | FastAPI | `target-apps/training-compliance/app/` |
| Auth | JWT (PyJWT) + bcrypt | `POST /auth/token`; 8 h expiry; role claim re-validated server-side |
| Database | PostgreSQL (RDS) | SQLAlchemy ORM; `dateutil.relativedelta` for expiry calc |
| Container | Docker Compose | `docker-compose.yml` — api + db + streamlit services |

## 3. Data model
| Table | Columns | Indexes / constraints |
|-------|---------|----------------------|
| `departments` | `id uuid PK`, `name text UNIQUE` | — |
| `job_roles` | `id uuid PK`, `name text UNIQUE` | — |
| `courses` | `id uuid PK`, `name text UNIQUE`, `category enum('safety','security','role_specific')`, `validity_period_months int`, `scope enum('all_staff','role_specific')`, `reference_field text`, `created_at timestamptz` | idx on `scope` |
| `role_course_requirements` | `id uuid PK`, `job_role_id uuid FK job_roles`, `course_id uuid FK courses`, `assigned_at timestamptz` | UNIQUE(job_role_id, course_id) |
| `users` | `id uuid PK`, `email text UNIQUE`, `hashed_password text`, `role enum('hr_admin','manager','employee','compliance_officer')`, `employee_id uuid FK employees nullable` | idx on `email` |
| `employees` | `id uuid PK`, `full_name text`, `email text UNIQUE`, `department_id uuid FK departments`, `job_role_id uuid FK job_roles`, `manager_id uuid FK employees nullable`, `is_active bool DEFAULT true`, `user_account_id uuid FK users nullable` | idx on `manager_id`, `is_active`, `department_id` |
| `completion_records` | `id uuid PK`, `employee_id uuid FK employees`, `course_id uuid FK courses`, `completion_date date`, `expiry_date date`, `is_superseded bool DEFAULT false`, `recorded_by uuid FK users`, `created_at timestamptz` | idx on `(employee_id, course_id, is_superseded)`; no hard deletes (NFR-10) |

## 4. API surface
| Method | Path | Request | Response | Notes |
|--------|------|---------|----------|-------|
| POST | `/auth/token` | `username`, `password` (form) | `{access_token, token_type, role}` | No auth required |
| GET | `/health` | — | `{status, version}` | No auth (NFR-9) |
| GET/POST | `/courses` | POST: `{name,category,scope,validity_period_months,reference_field}` | Course object / list | HR Admin only; 409 on dup name (FR-1) |
| PUT | `/courses/{id}` | Partial course fields | Updated course | HR Admin; future expiries only (FR-1) |
| GET/POST | `/employees` | POST: `{full_name,email,department_id,job_role_id,manager_id}` | Employee object / list | HR Admin; GET available to manager/compliance |
| PATCH | `/employees/{id}` | `{is_active?,...}` | Updated employee | HR Admin; deactivate sets `is_active=false` (FR-2) |
| GET/POST | `/completions` | POST: `{employee_id,course_id,completion_date}` | Completion / list | HR Admin + self-employee; supersedes prior active record (FR-3) |
| GET | `/compliance/employee/{id}` | — | `[{course,status,completion_date,expiry_date}]`+`data_quality_warning` | HR Admin + scoped manager/self (FR-5,FR-12) |
| GET | `/compliance/team` | — | `[{employee,required,complete,expired,missing}]` | Manager sees own direct reports only (FR-6) |
| GET | `/reports/overdue` | — | `[{employee,course,expiry_date}]` | Compliance Officer + HR Admin (FR-8) |
| GET | `/reports/expiring-soon` | — | `[{employee,course,expiry_date}]` | 0 < days_remaining ≤ 30 (FR-8) |
| GET | `/reports/completion-by-department` | — | `[{department,rate_pct}]` | Active employees only (FR-8,FR-11) |
| GET | `/reports/gap-by-course` | — | `[{course,missing_plus_expired_count}]` | Ranked desc (FR-8) |

## 5. Rules
- **Auth** (FR-9, NFR-3, NFR-4): JWT Bearer required on all routes except `/health` and `/auth/token`; missing/expired token → 401; bcrypt cost≥12; API: `Depends(get_current_user)` on every router; Streamlit: `st.session_state.token` gated at app entry — absent token redirects to login form, login errors shown inline (FR-10).
- **RBAC** (FR-6, FR-7, FR-8, FR-9, NFR-5): roles `hr_admin|manager|employee|compliance_officer`; API: `Depends(require_role(...))` per endpoint; Streamlit: role-gated tabs — hr_admin=Catalog+Roster+Completions, manager=Team Board, employee=My Trainings, compliance_officer=Dashboard only.
- **Manager isolation** (FR-6): `GET /compliance/team` and `GET /compliance/employee/{id}` filter by `manager_id = current_user.employee_id`; cross-team ID → 403; enforced in route dependency, not client.
- **Recertification / supersession** (FR-3, NFR-10): on new completion insert, prior active record for same `(employee_id, course_id)` set `is_superseded=true`; no hard delete; exactly one active record enforced in service layer.
- **Compliance status calc** (FR-4, FR-5): computed at query time — COMPLETE: `expiry_date >= today`; EXPIRED: `expiry_date < today`; MISSING: required + no non-superseded record; uses `dateutil.relativedelta` for calendar-month arithmetic (NFR-12).
- **Inactive exclusion** (FR-2, FR-11): all aggregate queries and compliance views apply `WHERE is_active = true`; historical records accessible to HR Admin via `GET /completions?employee_id=`.
- **Data quality warning** (FR-12): service layer counts non-superseded records per employee; if >20, response includes `data_quality_warning: true`.
- **Audit / immutability** (NFR-10): `completion_records` has no DELETE route; `recorded_by` FK logged on insert; schema migration forbids cascade-delete on completions.

## 6. DB delivery
1. Migration order: `001_departments_jobroles.sql`, `002_courses.sql`, `003_role_course_requirements.sql`, `004_users.sql`, `005_employees.sql`, `006_completion_records.sql`
2. Seed data (`seed.py` / `make seed`): 3 departments, 3 job roles, 6 courses (3 all-staff, 3 role-specific, mix of categories), 1 compliance-officer user (no employee record), 16 employees (15 active + 1 inactive), completions covering COMPLETE / EXPIRED / MISSING / expiring-within-30-days states per FR-13; idempotent via `INSERT ... ON CONFLICT DO NOTHING`.
