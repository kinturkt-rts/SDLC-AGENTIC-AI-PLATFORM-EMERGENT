# Training & Certification Compliance PRD

## 1. Overview

Marcus, an HR administrator, faces quarterly audits on employee safety and security training completion. Today the process relies on spreadsheets and inbox searches, leaving managers unable to identify out-of-compliance direct reports until an escalation occurs. This reactive, fragmented approach creates audit risk and operational friction for HR, managers, and compliance officers alike.

The proposed solution is a web application — **Training & Certification Compliance** — that provides a single authoritative system for defining required trainings (course catalog), recording completions with automatic expiry calculation, and surfacing compliance gaps through role-gated views. HR administrators manage the full catalog and roster; managers see only their own team; employees see their own training status; compliance officers get org-wide read-only dashboards and alert views.

The MVP does not include LMS integration, file hosting, or email notifications. All business logic lives in a FastAPI backend; a Streamlit front-end provides role-gated screens for each persona. The system must correctly handle inactive employees, role-based course requirements, recertification (superseding prior records), and expired vs. missing distinctions.

---

## 2. Goals & Success Metrics

| Goal | Metric | Target | Notes |
|------|--------|--------|-------|
| Eliminate spreadsheet-based compliance tracking | % of compliance data managed in-system vs. spreadsheets | 100 % at go-live | Baseline is current spreadsheet process |
| Surface team compliance gaps to managers proactively | Manager sessions that include at least one compliance view | ≥ 90 % of weekly manager logins | Proxy for adoption |
| Accurate expiry calculation | Expiry date error rate vs. manual audit sample | 0 errors in 100-record sample | Verified at UAT |
| Reduce time to produce quarterly audit report | Time HR spends generating org-wide compliance summary | < 5 minutes from login to export | vs. current ad-hoc process |
| Correct role-based requirement resolution | Required courses correctly resolved for reassigned employees | 100 % correctness on role-change test cases | Verified by automated tests |
| Demo data quality | Compliance officer dashboard shows all four compliance states | Pass / fail demo script | At least 15 employees, 6 courses, 3 role types |

---

## 3. Non-Goals / Out of Scope

- LMS / SCORM integration or any video/content hosting
- Email or SMS reminder delivery (in-app alert surface only)
- External certificate file storage beyond an optional free-text or URL reference field
- Multi-language (i18n) support
- Multi-tenant / multi-organisation data separation
- Automated provisioning or SSO (authentication is local credential-based in MVP)
- Retroactive penalty when a course is removed from a role's requirement set
- Payments or billing
- Calendar or scheduling of training sessions

---

## 4. Users & Use Cases

| Persona | Need | Primary use case |
|---------|------|------------------|
| HR Administrator (Marcus and peers) | Define courses, manage roster, record completions for any employee, run audits | Add a new course with validity period; record a completion; deactivate a departed employee |
| Manager | Monitor own team's compliance without accessing other teams | View team compliance board; identify who is missing or expiring within 30 days |
| Employee | Know which courses are required, which are current, and which have expired | View "My Trainings" screen showing required vs. completed vs. expired |
| Compliance Officer | Produce org-wide audit evidence with no write access | View dashboards: overdue list, expiring-in-30-days list, completion rate by department, worst gaps by course |
| Operations / Monitoring (unauthenticated) | Verify service health | Call `/health` endpoint; receive 200 OK |

---

## 5. Functional Requirements

| ID | Description | Priority | Acceptance criteria (Given / When / Then) |
|----|-------------|----------|-------------------------------------------|
| FR-1 | **Course Catalog — Create & Edit** HR Admin can create a course with: name (unique), category (safety / security / role-specific), validity period in months (positive integer), scope flag (all-staff or role-specific), and optional reference field (URL / text). HR Admin can edit any field; changes apply to future expiry calculations only. | P0 | **Given** a logged-in HR Admin **When** they submit a valid course form **Then** the course is persisted and returned by `GET /courses` with all supplied fields; duplicate name returns HTTP 409. |
| FR-2 | **Employee Roster — Create, Edit, Deactivate** HR Admin can add an employee with: full name, email (unique), department, job role, manager (FK to another employee), and active/inactive flag. Deactivating an employee sets the flag to inactive; the employee disappears from active compliance counts and manager team totals but history is preserved. | P0 | **Given** an active employee record **When** HR Admin sets the employee to inactive **Then** `GET /compliance/overview` excludes the employee from completion-rate percentages; historical completion records remain queryable via `GET /completions?employee_id=`. |
| FR-3 | **Record Training Completion & Automatic Expiry** HR Admin or Employee (self) can record a completion for a (employee, course) pair with a completion date. The system calculates `expiry_date = completion_date + validity_period_months`. A new completion for the same (employee, course) supersedes the prior active record (recertification); the prior record is retained in history with a superseded flag. | P0 | **Given** an existing active completion for Employee A on Course X **When** HR Admin records a new completion for the same pair **Then** the prior record is marked superseded; `GET /compliance/employee/{id}` reflects the new expiry date; the count of active records for that pair is exactly 1. |
| FR-4 | **Required-Course Matrix** HR Admin can assign one or more courses as mandatory for a given job role. An all-staff course is mandatory for every active employee regardless of role. Removing a course from a role's requirement set does not retroactively affect employees who already completed it; it only removes the "missing" flag going forward. | P0 | **Given** Course Y is required for role "Warehouse Associate" **When** an active employee whose role is "Warehouse Associate" has no current non-expired completion for Course Y **Then** `GET /compliance/employee/{id}` lists Course Y with status `MISSING`; after the role requirement is removed, Course Y no longer appears as `MISSING` for that role. |
| FR-5 | **Compliance Status Calculation per Employee** The system derives and exposes a compliance status for each (employee, required course) pair: `COMPLETE` (non-expired completion exists), `EXPIRED` (completion exists but expiry_date < today), `MISSING` (required, no current non-expired completion), `NOT_REQUIRED` (course not required for this employee's role). Inactive employees are excluded from active compliance views. | P0 | **Given** today is 2025-06-01 and an employee has a completion with expiry_date 2025-05-15 **When** `GET /compliance/employee/{id}` is called **Then** the status for that course is `EXPIRED`; a required course with no completion record has status `MISSING`; a non-required course is absent or `NOT_REQUIRED`. |
| FR-6 | **Manager Team Compliance View** A logged-in Manager sees a compliance summary for only the employees where `employee.manager_id = current_user.employee_id`. The view shows each direct report's name, role, total required courses, count complete, count expired, count missing. The Manager cannot view employees in other teams, edit catalog, or record completions for others. | P0 | **Given** Manager M has 4 direct reports **When** M calls `GET /compliance/team` **Then** exactly 4 employee records are returned; an attempt to call `GET /compliance/employee/{id}` for an employee outside M's team returns HTTP 403. |
| FR-7 | **Employee "My Trainings" View** A logged-in Employee can view their own required courses with status (COMPLETE / EXPIRED / MISSING), completion date, and expiry date. An Employee cannot view other employees' records or record completions for others. | P0 | **Given** a logged-in Employee **When** they call `GET /compliance/me` **Then** only their own required courses with statuses are returned; calling `GET /compliance/employee/{other_id}` returns HTTP 403. |
| FR-8 | **Compliance Officer Org-Wide Dashboard** A Compliance Officer (read-only role) can access: (a) list of all active employees with an expired required course, (b) list of active employees with a required course expiring within 30 days, (c) completion rate (% COMPLETE) by department, (d) worst-gap courses ranked by count of MISSING + EXPIRED across active employees. No write operations are permitted. | P0 | **Given** a logged-in Compliance Officer **When** they call `GET /reports/overdue`, `GET /reports/expiring-soon`, `GET /reports/completion-by-department`, `GET /reports/gap-by-course` **Then** each returns correct aggregated data; a POST/PUT/DELETE to any resource returns HTTP 403. |
| FR-9 | **Role-Based Access Control (RBAC)** The system enforces four authenticated roles: `hr_admin`, `manager`, `employee`, `compliance_officer`. Each API endpoint enforces the role permissions described in FR-6 through FR-8. Unauthenticated requests to any endpoint other than `/health` and `/auth/token` return HTTP 401. | P0 | **Given** an unauthenticated request **When** it is sent to any endpoint except `/health` and `/auth/token` **Then** the response is HTTP 401; a `compliance_officer` token sent to `POST /completions` returns HTTP 403. |
| FR-10 | **Streamlit Role-Gated UI** The Streamlit application implements login and routes the user to the appropriate screen based on their role: HR Admin → Catalog & Roster management + completion entry; Manager → Team Board; Employee → My Trainings; Compliance Officer → Dashboard. Each screen calls the FastAPI backend exclusively; no direct database or app-layer imports. Login errors are displayed inline. | P1 | **Given** a user logs in with `manager` credentials **When** the Streamlit app authenticates them **Then** only the Team Board screen is rendered; navigating to the HR Catalog screen is not possible; an invalid credential attempt shows an error message without crashing the app. |
| FR-11 | **Inactive Employee Exclusion from Active Counts** Inactive employees are excluded from: compliance percentage calculations, manager team totals, and Compliance Officer dashboards' active compliance views. Their historical completion records remain accessible to HR Admin. | P0 | **Given** Employee Z is deactivated **When** `GET /reports/completion-by-department` is called **Then** Employee Z's records do not affect the department's completion rate; `GET /completions?employee_id=Z` returns the historical records to an HR Admin. |
| FR-12 | **Soft Cap — Active Record Flag** If an employee accumulates more than 20 active (non-superseded) completion records across all courses, the system attaches a `data_quality_warning: true` flag on that employee's compliance response. | P2 | **Given** an employee has 21 active completion records **When** `GET /compliance/employee/{id}` is called **Then** the response includes `"data_quality_warning": true`; an employee with ≤ 20 records does not include this flag. |
| FR-13 | **Demo / Seed Data** A seed script populates: ≥ 6 courses (mix of all-staff and role-specific, multiple categories), ≥ 3 job roles, ≥ 3 departments, ≥ 15 active + 1 inactive employee, completions covering all four statuses (COMPLETE, EXPIRED, MISSING, expiring within 30 days). | P1 | **Given** the seed script is run against an empty database **When** `GET /reports/expiring-soon` and `GET /reports/overdue` are called **Then** each returns at least 2 records; `GET /reports/completion-by-department` returns 3 department rows. |

---

## 6. Non-Functional Requirements

| ID | Category | Target | Measurement / verification | Notes |
|----|----------|--------|---------------------------|-------|
| NFR-1 | Performance | p95 API response time ≤ 400 ms for compliance calculation endpoints under normal load | Load test with 50 concurrent users; measure p95 via test report | (Assumption) — no load figure given in brief |
| NFR-2 | Performance | Streamlit page render (after API response received) ≤ 2 s on standard broadband | Manual timing during UAT; Streamlit profiler | (Assumption) |
| NFR-3 | Security / Auth | All authenticated endpoints require a valid JWT Bearer token; tokens expire after 8 hours | Automated test: expired token returns 401; missing token returns 401 | (Assumption) token lifetime; brief does not specify SSO |
| NFR-4 | Security / Privacy | Passwords stored as bcrypt hashes (cost factor ≥ 12); plaintext passwords never logged | Code review; grep for plaintext password in logs in CI | (Assumption) |
| NFR-5 | Security / Privacy | Role claims embedded in JWT; server re-validates role on every request (no client-side role enforcement only) | Automated test: tampered role claim in JWT returns 403 | (Assumption) |
| NFR-6 | Availability | API uptime ≥ 99.5 % measured monthly | Uptime monitor (e.g., healthcheck ping); monthly report | (Assumption) — deployment target TBD |
| NFR-7 | Scalability | Data model supports ≥ 10 000 employees and ≥ 500 courses without schema changes | Load / volume test with synthetic data at 10 k employees | (Assumption) — actual org size not stated |
| NFR-8 | Observability | All API requests logged with method, path, status code, latency, and authenticated user ID (no PII in log line beyond user ID) | Log review during QA; confirm PII absent in sample | (Assumption) |
| NFR-9 | Observability | Structured JSON logs; `/health` endpoint returns `{"status": "ok"}` and HTTP 200 with no auth required | Automated smoke test in CI pipeline | (Assumption) |
| NFR-10 | Compliance / Data Retention | Completion history (including superseded records) is never hard-deleted; only soft-delete / inactive flag permitted | Code review: no `DELETE` cascade on completions table; automated test confirms history persists after deactivation | Explicit business rule from brief |
| NFR-11 | Operability | Application packaged with a `docker-compose.yml` (API + DB + Streamlit); `make seed` or equivalent one-command seed for demo data | Runbook verification: fresh `docker-compose up` + seed completes without errors | (Assumption) — deployment method not specified |
| NFR-12 | Compliance / Correctness | Expiry date calculation is deterministic: `expiry_date = completion_date + validity_period_months` using calendar-month arithmetic (not 30-day approximation) | Unit tests covering month-boundary edge cases (e.g., Jan 31 + 1 month) | Derived from brief requirement |

---

## 7. Data & Integrations

### Core Entities

| Entity | Key Fields | Notes |
|--------|-----------|-------|
| `Course` | id, name (unique), category (enum: safety / security / role_specific), validity_period_months, scope (enum: all_staff / role_specific), reference_field (optional text/URL), created_at | |
| `JobRole` | id, name (unique) | e.g., "Warehouse Associate", "Engineer", "Manager" |
| `RoleCourseRequirement` | id, job_role_id → JobRole, course_id → Course, assigned_at | Junction table; deletion removes requirement going forward |
| `Department` | id, name | |
| `Employee` | id, full_name, email (unique), department_id → Department, job_role_id → JobRole, manager_id → Employee (self-FK, nullable), is_active (bool), user_account_id → User | |
| `User` | id, email, hashed_password, role (enum: hr_admin / manager / employee / compliance_officer), employee_id → Employee (nullable for pure admin accounts) | |
| `TrainingCompletion` | id, employee_id → Employee, course_id → Course, completion_date, expiry_date (computed), is_superseded (bool), recorded_by → User, created_at | expiry_date = completion_date + validity_period_months |

### Derived / Computed
- **ComplianceStatus** per (employee, required course): computed at query time from `TrainingCompletion` and `RoleCourseRequirement`; not stored as a separate table to avoid staleness.

### External Integrations
- None in MVP. All data entry is manual or via API.
- Optional reference field on `Course` may point to an external LMS URL (plain text, not validated in MVP).

### API Structure
- Base path: `target-apps/training-compliance/app/`
- Routers: `/auth`, `/courses`, `/job-roles`, `/employees`, `/completions`, `/compliance`, `/reports`
- OpenAPI docs served at `/docs`

---

## 8. Analytics & Observability

**Logging**
- Structured JSON logs (Python `structlog` or equivalent) on every request: timestamp, method, path, status_code, latency_ms, user_id (from JWT, null for unauth).
- No PII (names, emails) in log lines; use opaque IDs only.
- Log level configurable via environment variable `LOG_LEVEL` (default: `INFO`).

**Key Application Metrics** (to be instrumented, exposed at `/metrics` if Prometheus scraping is available):
- `api_request_duration_ms` histogram by endpoint and status code
- `compliance_records_total` counter by status (COMPLETE / EXPIRED / MISSING)
- `active_employees_total` gauge
- `expiring_soon_count` gauge (expiring within 30 days)

**Alerts (Conceptual — in-app surface only per brief):**
- Employee has ≥ 1 expired required course → surfaced in Compliance Officer overdue list and Manager team board badge.
- Employee is inactive but still referenced as a manager on active employees → flagged as a data quality issue (surfaced to HR Admin).
- Employee has > 20 active completion records → `data_quality_warning` flag in API response (FR-12).

**Health Check**
- `GET /health` → `{"status": "ok", "version": "<app_version>"}`, HTTP 200, no authentication required.

---

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Expiry date arithmetic errors on month boundaries (e.g., 31-Jan + 1 month) | Compliance dates wrong; audit liability | Use a battle-tested date library (`dateutil.relativedelta` or equivalent); cover edge cases in unit tests (NFR-12) |
| Manager-isolation bypass (manager queries another team via direct ID) | Data privacy violation; trust loss | Server enforces manager_id filter on every team endpoint; automated penetration test cases in test suite |
| Inactive employee still counted in compliance percentages | Inflated/deflated audit numbers | Explicit filter `is_active = true` on all aggregate queries; integration test confirms exclusion (FR-11) |
| Role changes retroactively affect compliance history | Confusion / unfair penalties | Business rule: role change only updates requirement set going forward; old completions are retained and neutral; documented in API behaviour |
| Demo seed data not covering all compliance states | Dashboard looks incomplete in demos; client confidence drops | Seed script validated by automated smoke tests (FR-13) |
| Stale compliance status if computed on every request at scale | Slow dashboard for large orgs | Materialised view or caching layer (Redis) as a Phase 2 optimisation; acceptable for MVP at ≤ 10 k employees (NFR-7) |
| User account / employee record misalignment (user has no linked employee) | Manager view returns empty; employee view breaks | Data integrity constraint: manager/employee roles require a linked employee_id; enforced at DB and API validation layer |

---

## 10. Open Questions

| # | Question | Suggested owner |
|---|----------|-----------------|
| 1 | What is the deployment target (cloud provider, container orchestration, on-prem)? Affects availability SLA and Docker vs. K8s packaging. | Engineering lead |
| 2 | Should HR Admin be able to record completions on behalf of *any* user including other HR Admins, or only non-admin employees? | Marcus (HR) / Product |
| 3 | Is there a requirement for password reset / "forgot password" flow in MVP, or is admin-reset sufficient? | HR / Engineering |
| 4 | What is the expected org size at go-live (number of employees, courses)? Affects indexing and query optimisation decisions. | Marcus (HR) / IT |
| 5 | Should the optional certificate reference field accept a URL that the system validates / fetches, or purely free text? | Product |
| 6 | Are there specific job roles / departments / course names required in the demo data, or is representative synthetic data acceptable? | Marcus (HR) |
| 7 | Should a manager also have an employee record and appear in their own team's compliance view, or are manager accounts purely administrative? | Product |
| 8 | Is there an audit log requirement (who recorded or edited a completion and when) beyond the `recorded_by` field, e.g. full change history? | Compliance Officer / Legal |
| 9 | What happens when a course's validity period is changed — should existing unexpired completions recalculate their expiry date? | Product / Marcus (HR) |
| 10 | Are there any accessibility (WCAG) requirements for the Streamlit UI? | Product / Client |

---

## 11. Delivery & Client Surface

| Concern | Choice | Implementation notes |
|---------|--------|---------------------|
| Client UI | **Streamlit** | Role-gated screens: HR Catalog & Roster, Manager Team Board, Employee My Trainings, Compliance Officer Dashboard |
| API | **FastAPI** under `target-apps/training-compliance/` | REST + OpenAPI; served at `/docs`; all business logic and RBAC enforced here |
| UI location | `target-apps/training-compliance/ui/streamlit_app.py` | HTTP client calls to FastAPI only — never imports `app/` or DB layer directly |
| Auth for UI | JWT Bearer token | Streamlit stores token in `st.session_state`; token passed as `Authorization: Bearer <token>` header on every API call |
| Auth for API | `POST /auth/token` returns JWT | Username + password (form body); role embedded in JWT claims; validated server-side on every request |
| Seed / demo data | `make seed` or `python seed.py` | Populates all entities per FR-13; idempotent (safe to re-run) |
| Directory structure | `target-apps/training-compliance/` | `app/` (FastAPI), `ui/` (Streamlit), `tests/`, `docker-compose.yml`, `Makefile`, `README.md` |

---

## Appendix: Assumptions

- **Authentication mechanism**: JWT-based local auth (username + password) is assumed. No SSO, LDAP, or OAuth provider is mentioned; these are Phase 2 considerations.
- **Token expiry**: 8-hour JWT lifetime assumed as a reasonable balance between security and usability for an internal HR tool.
- **Password storage**: bcrypt with cost factor ≥ 12 assumed; no specific hashing requirement stated in the brief.
- **Deployment environment**: Docker Compose assumed as the packaging format for MVP; no cloud provider specified.
- **Database**: A relational database (e.g., PostgreSQL) is assumed given the relational nature of employees, roles, courses, and completions. Engine choice is TBD per Engineering.
- **Calendar-month arithmetic**: `completion_date + N months` uses calendar months (e.g., Feb 28 + 1 month = Mar 28), not 30-day intervals.
- **"Expiring within 30 days"**: Defined as `today < expiry_date ≤ today + 30 days` and the completion is currently COMPLETE (not already expired).
- **All-staff courses apply to active employees only**: Inactive employees are excluded from all-staff requirement checks.
- **Manager is also an employee**: A manager has their own employee record and is subject to the same compliance requirements for their role. Whether they appear in their own team view is an open question.
- **Compliance Officer has no employee record required**: The compliance_officer role may be a standalone user account without a linked employee record.
- **Single-organisation scope**: Multi-tenancy is out of scope; all data belongs to one organisation.
- **No file upload**: The certificate reference field is a plain text / URL string; no binary file storage is implemented.
- **Validity period change effect**: A change to a course's validity period does not retroactively recalculate existing completion expiry dates (open question logged; assumption is no retroactive change for MVP stability).
- **No self-service registration**: User accounts are created by HR Admin; there is no public sign-up flow.
- **Performance baseline**: 50 concurrent users and 10 000 employees used as sizing assumptions; actual figures not provided in the brief.
- **Observability tooling**: Structured JSON logging is assumed; Prometheus/Grafana integration is optional and not required for MVP.
