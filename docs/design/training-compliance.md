# Training Compliance MVP — Solution Design

## 1. Summary
Centralises course catalog, employee roster, and completion records for a single org; derives real-time compliance status (current / expired / missing) per employee. Primary DB is PostgreSQL via SQLAlchemy; API is FastAPI REST (JWT-gated); Streamlit provides four role-gated UI screens.
Diagram: `docs/diagrams/generated-diagrams/training-compliance.png`
TBD: identity provider (JWT local auth assumed); validity period unit; expiring-soon window configurability.

## 2. Stack
| Layer | Technology | Path / Notes |
|-------|------------|--------------|
| UI | Streamlit | `ui/streamlit_app.py` — calls FastAPI over HTTP port 8501; never imports `app/` |
| API | FastAPI | `target-apps/training-compliance/app/` — REST + OpenAPI at `/docs` |
| Auth | JWT Bearer | `python-jose`; `user_id` + `role` claims; local username/password |
| ORM | SQLAlchemy 2 + Alembic | Migrations in `alembic/versions/` |
| Database | PostgreSQL (RDS) | Primary relational store |
| Cache | ElastiCache (Redis) | Dashboard / session caching; reduces RDS reads |

## 3. Data model
| Table | Columns | Indexes / Constraints |
|-------|---------|-----------------------|
| `departments` | `id uuid PK`, `name text UNIQUE NOT NULL` | — |
| `job_roles` | `id uuid PK`, `name text UNIQUE NOT NULL` | — |
| `courses` | `id uuid PK`, `name text UNIQUE NOT NULL`, `category enum(safety,security,role_specific)`, `validity_period_months int NULL`, `required_for_all_staff bool DEFAULT false`, `certificate_ref text NULL`, `is_active bool DEFAULT true` | idx on `is_active` |
| `employees` | `id uuid PK`, `full_name text NOT NULL`, `email text UNIQUE NOT NULL`, `department_id uuid FK(departments)`, `job_role_id uuid FK(job_roles)`, `manager_id uuid FK(employees) NULL`, `is_active bool DEFAULT true` | idx on `manager_id`, `is_active`, `job_role_id` |
| `role_requirements` | `id uuid PK`, `job_role_id uuid FK(job_roles)`, `course_id uuid FK(courses)` | UNIQUE(`job_role_id`, `course_id`) |
| `completion_records` | `id uuid PK`, `employee_id uuid FK(employees)`, `course_id uuid FK(courses)`, `completion_date date NOT NULL`, `expiry_date date NULL`, `is_active_record bool DEFAULT true`, `superseded_by_id uuid FK(completion_records) NULL`, `created_at timestamptz DEFAULT now()` | idx on `(employee_id, course_id, is_active_record)` |
| `users` | `id uuid PK`, `employee_id uuid FK(employees) NULL`, `email text UNIQUE NOT NULL`, `hashed_password text NOT NULL`, `role enum(hr_admin,manager,employee,compliance_officer)` | idx on `email` |
| `audit_log` | `id uuid PK`, `user_id uuid NOT NULL`, `action text NOT NULL`, `entity text`, `entity_id uuid NULL`, `timestamp timestamptz DEFAULT now()`, `detail jsonb NULL` | idx on `user_id`, `timestamp` |

## 4. API surface
| Method | Path | Request | Response | Notes |
|--------|------|---------|----------|-------|
| GET | `/health` | — | `{"status":"ok"}` | Unauthenticated; FR-12 |
| POST | `/auth/token` | `{email, password}` | `{access_token, token_type}` | Issues JWT |
| GET/POST/PATCH | `/courses` / `/courses/{id}` | `CourseIn{name,category,validity_period_months,required_for_all_staff,certificate_ref}` | `CourseOut` | HR admin only; 409 on duplicate name; FR-1 |
| GET/POST/PATCH | `/employees` / `/employees/{id}` | `EmployeeIn{full_name,email,department_id,job_role_id,manager_id}` | `EmployeeOut` | HR admin CRUD; PATCH `is_active=false` soft-deactivates; FR-2 |
| GET/POST/DELETE | `/requirements` | `RequirementIn{job_role_id,course_id}` | `RequirementOut` | HR admin only; FR-3 |
| POST | `/completions` | `CompletionIn{employee_id,course_id,completion_date}` | `CompletionOut` | HR admin (any) or employee (self); supersedes prior active record atomically; FR-4 |
| GET | `/compliance/employee/{id}` | — | `[{course_id,course_name,status:enum(current,expired,missing),expiry_date}]` | All roles (scoped); FR-5 |
| GET | `/compliance/team` | — | `[EmployeeComplianceSummary]` | Manager (own team only); FR-6 |
| GET | `/reports/dashboard` | — | `{overdue:[…],expiring_soon:[…],rate_by_dept:[…],course_gaps:[…]}` | Compliance officer only; FR-7 |
| GET | `/alerts` | query `?type=overdue\|expiring_soon\|data_quality` | `[AlertItem]` | Manager + compliance officer; FR-9, FR-10 |

## 5. Rules
- **Auth**: Every non-`/health` endpoint requires `Authorization: Bearer <JWT>`; missing token → 401 (NFR-3).
- **RBAC**: `hr_admin` — all write endpoints; `manager` — `/compliance/team`, `/alerts`, `/compliance/employee/{id}` (own team only); `employee` — `/compliance/employee/{own id}`, POST `/completions` (self only); `compliance_officer` — all GET read endpoints, no writes → 403 (FR-8, NFR-4).
- **Team isolation**: Manager queries filter `employees.manager_id = current_user.employee_id` server-side on every request; cross-team access → 403 (NFR-4).
- **Recertification atomicity**: Supersede prior `is_active_record=true` row and insert new record in a single DB transaction; prevents duplicate actives (FR-4, NFR-9).
- **Inactive exclusion**: All compliance queries add `WHERE employees.is_active = true`; inactive employees excluded from rate denominators (FR-2, FR-5).
- **Audit**: Write operations (POST/PATCH/DELETE on courses, employees, requirements, completions) insert a row to `audit_log`; records are never deleted (NFR-9, NFR-11).
- **Soft cap warning**: If `COUNT(is_active_record=true) > 20` for an employee, append `data_quality_warning: true` to response; does not block write (FR-10).
- **Logging**: Every request logged as structured JSON `{timestamp, method, path, status_code, duration_ms, user_id, role}`; no PII beyond `user_id` (NFR-7).

## 6. DB delivery
1. Migration order: `001_create_departments_jobroles.sql`, `002_create_courses.sql`, `003_create_employees.sql`, `004_create_role_requirements.sql`, `005_create_completion_records.sql`, `006_create_users.sql`, `007_create_audit_log.sql`
2. Seed (`seed.py`): 3 departments, 3 job roles, 6 courses (mix of all-staff + role-specific, varied validity), 15 active employees (current/expired/missing states, ≥3 expiring within 30 days, ≥2 never-started), 1 inactive employee with historical completions, 1 user per role for demo login; post-insert assertion checks all minimum counts (FR-11).
