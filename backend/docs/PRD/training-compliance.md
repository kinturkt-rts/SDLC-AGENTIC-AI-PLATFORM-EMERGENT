# Training & Certification Compliance PRD

## 1. Overview

Marcus (HR) and his organization face a recurring audit burden: determining who has completed mandatory safety and security training is currently a manual process of spreadsheet reconciliation and inbox searches. Managers have no proactive visibility into their teams' compliance status, and findings only surface when someone escalates a problem. This creates audit risk, administrative overhead, and gaps in workforce safety and security posture.

The Training & Certification Compliance system provides a single authoritative platform where HR administrators define a course catalog with validity rules and role-based requirements, record employee completions, and expose tailored compliance views to each actor (employee, manager, compliance officer, and HR admin). The system calculates expiry dates automatically, maintains a historical record of all completions, and surfaces missing or expiring required courses before they become audit findings.

The MVP delivers a FastAPI backend with a Streamlit front-end segmented by role, seeded with realistic demo data, and enforces strict data isolation so managers see only their own teams, employees see only their own records, and compliance officers have org-wide read access without write privileges.

---

## 2. Goals & Success Metrics

| Goal | Metric | Target | Notes |
|------|--------|--------|-------|
| Eliminate manual spreadsheet auditing | Time HR spends assembling quarterly compliance report | < 30 minutes end-to-end using the system | Baseline TBD from current process |
| Give managers proactive visibility | % of overdue items discovered before escalation | ≥ 90 % caught in-system, not via escalation | Tracked via compliance view usage |
| Accurate expiry tracking | % of completion records with correct computed expiry date | 100 % | Verified by automated test suite |
| Role-based data isolation | Zero cross-team data leakage incidents | 0 incidents in QA acceptance and production audit logs | Enforced at API layer |
| Demo readiness | Compliance officer dashboard shows all required states | All four states (compliant, missing, expiring-soon, expired) visible in demo dataset | Verified against seed data spec |
| System availability for quarterly audits | Uptime during business hours | ≥ 99.5 % monthly | (Assumption) |

---

## 3. Non-Goals / Out of Scope

- LMS integration, SCORM content hosting, or video delivery
- Email or SMS reminder notifications (in-app alert surface only)
- External certificate file storage beyond a simple URL/reference string field
- Multi-language or internationalisation
- Multi-tenant architecture (single organisation deployment)
- Automated retroactive recalculation of requirements when a course is removed from a role (forward-only rule changes)
- Payment processing or subscription billing
- Mobile-native application

---

## 4. Users & Use Cases

| Persona | Need | Primary use case |
|---------|------|------------------|
| HR Administrator (Marcus) | Define courses, manage roster, record any completion, support audits | Create/edit course catalog; add employees; record completions on behalf of staff; deactivate leavers; export-ready compliance overview |
| Manager | Monitor own team's training status without affecting other teams | View team compliance board filtered to direct reports; identify who is missing or expiring within 30 days |
| Employee | Know what training is required of them and what is outstanding | View personal required-vs-completed dashboard; see expiry dates and missing items |
| Compliance Officer | Produce org-wide audit evidence without risk of data mutation | Read-only dashboard: completion rate by department, overdue list, expiring-within-30-days list, worst-gap courses |
| Ops / Unauthenticated | Confirm service health for infrastructure monitoring | GET /health returns 200 OK with no authentication |

---

## 5. Functional Requirements

| ID | Description | Priority | Acceptance criteria (Given / When / Then) |
|----|-------------|----------|-------------------------------------------|
| FR-1 | **Course catalog management** — HR admin can create, edit, and soft-delete a course with fields: name, category (`safety` \| `security` \| `role-specific`), validity period in months, required-for-all-staff flag, and an optional reference/notes field. | P0 | **Given** an authenticated HR admin; **When** they POST `/courses` with all required fields; **Then** the course is persisted, returned with a generated ID, and appears in GET `/courses`. Editing any field updates the record. A soft-deleted course is excluded from active catalog queries but its completion history is retained. |
| FR-2 | **Required-course matrix** — HR admin can assign one or more courses as mandatory for a given job role; assignments can be removed without retroactive effect. | P0 | **Given** an existing course and job role; **When** HR admin creates a role-course assignment; **Then** any active employee with that job role appears as "missing" in compliance views if they have no current non-expired completion. **When** an assignment is removed; **Then** employees previously missing that course are no longer penalised going forward; historical completions are unchanged. |
| FR-3 | **Employee roster management** — HR admin can create and update employee records containing: full name, department, manager (foreign key to another employee), job role, and active/inactive flag. Deactivating an employee preserves all history but removes them from active compliance counts and manager team totals. | P0 | **Given** an authenticated HR admin; **When** they PATCH an employee's `active` flag to `false`; **Then** that employee no longer appears in compliance percentage calculations, manager team boards, or the compliance officer's active overdue lists; their completion history remains queryable via HR admin views. |
| FR-4 | **Record and recertify training completions** — HR admin or an employee (for themselves only) can submit a completion record containing employee ID, course ID, and completion date. The system computes and stores `expiry_date = completion_date + validity_period_months`. A new submission for the same employee + course supersedes the prior active record (prior record archived, not deleted). | P0 | **Given** an employee with an existing completion for Course X; **When** a new completion is submitted for the same employee + course; **Then** the prior completion record is marked archived, the new record is active, and `expiry_date` equals `completion_date` plus the course's validity period in whole months. **Given** a course with `validity_period = 0` or null (no expiry); **When** a completion is recorded; **Then** `expiry_date` is null and the record never transitions to expired state. |
| FR-5 | **Compliance status derivation** — For each required course per active employee, the system derives one of four statuses: `compliant` (active completion, expiry_date > today or null), `expiring_soon` (active completion, expiry_date within 30 calendar days), `expired` (active completion, expiry_date ≤ today), `missing` (no active completion). | P0 | **Given** today's date and an employee's completion records; **When** compliance status is queried; **Then** each required course maps to exactly one of the four states using the stated rules. A course with no completion returns `missing`. A course with expiry_date = today returns `expired`. A course with expiry_date = today + 30 returns `expiring_soon`. |
| FR-6 | **Employee self-view** — An authenticated employee can view only their own required courses, completion dates, expiry dates, and current compliance status. They cannot view or modify other employees' records. | P0 | **Given** an authenticated employee; **When** they GET `/me/compliance`; **Then** the response contains only records scoped to their own employee ID. **When** they attempt GET `/employees/{other_id}/compliance`; **Then** the API returns HTTP 403. |
| FR-7 | **Manager team-compliance view** — An authenticated manager can view a compliance summary for all active employees whose `manager_id` equals the manager's own employee ID. They cannot view employees in other managers' teams or modify any catalog/roster records. | P0 | **Given** an authenticated manager; **When** they GET `/manager/team-compliance`; **Then** only employees with `manager_id = <current_user_employee_id>` and `active = true` are returned. **When** they attempt to POST or PATCH any course, roster, or completion record for an employee not in their team; **Then** the API returns HTTP 403. |
| FR-8 | **HR admin full access** — An HR admin role has unrestricted read and write access to course catalog, required-course matrix, employee roster, and completion records for any employee. | P0 | **Given** an authenticated HR admin; **When** they attempt any CRUD operation on any resource; **Then** the operation succeeds subject only to business-rule validation (e.g., duplicate detection), not permission denial. |
| FR-9 | **Compliance officer org-wide read-only dashboard data** — An authenticated compliance officer can retrieve: (a) org-wide completion rate by department, (b) list of all active employees with at least one `overdue` required course, (c) list of active employees with at least one `expiring_soon` course, (d) worst-gap courses ranked by count of `missing` + `expired` active employees. All endpoints are GET-only for this role. | P0 | **Given** an authenticated compliance officer; **When** they call any dashboard endpoint; **Then** data covers all active employees across all departments. **When** they attempt any POST/PATCH/DELETE; **Then** the API returns HTTP 403. |
| FR-10 | **Inactive employee exclusion** — Inactive employees are excluded from all compliance percentage calculations, manager team views, and compliance officer active-overdue and expiring-soon lists. | P0 | **Given** an employee with `active = false`; **When** any compliance aggregate or list endpoint is called; **Then** that employee does not appear in returned counts or lists. Their historical records remain accessible to HR admin via explicit employee-detail endpoints. |
| FR-11 | **Streamlit role-gated UI** — The Streamlit application presents four distinct screen sets gated by authenticated role: HR admin (catalog management, roster management, record completions), Manager (team board), Employee (my trainings), Compliance Officer (org dashboard). The UI communicates exclusively via the REST API and never imports application modules directly. | P1 | **Given** a user logs in with manager credentials; **When** the Streamlit session starts; **Then** only manager-scoped screens are rendered and HR/compliance officer screens are not accessible in the UI navigation. Each role's screens successfully render data from their respective API endpoints without error. |
| FR-12 | **Soft cap data-quality flag** — The system flags (via an API response field and UI indicator) any employee who has more than 20 active completion records. | P2 | **Given** an employee with 21 or more active (non-archived) completion records; **When** their record is fetched by HR admin; **Then** the response includes `data_quality_flag: "excess_active_records"`. No records are deleted or blocked; it is advisory only. |
| FR-13 | **Demo seed data** — The system ships with a seed script that creates ≥ 6 courses (mix of all-staff and role-specific), ≥ 3 job roles, ≥ 3 departments, ≥ 15 active employees with mixed compliance states, at least one inactive employee with historical completions, several expiring-within-30-days records, and several never-started required courses. | P1 | **Given** a fresh database; **When** the seed script is executed; **Then** the compliance officer dashboard shows all four compliance statuses populated, at least one department below 80 % completion rate, and the inactive employee is absent from active compliance counts. |

---

## 6. Non-Functional Requirements

| ID | Category | Target | Measurement / verification | Notes |
|----|----------|--------|---------------------------|-------|
| NFR-1 | Performance | P95 API response time ≤ 500 ms for all read endpoints under normal load | Load test with 50 concurrent users; check P95 in test report | (Assumption) |
| NFR-2 | Performance | Compliance status computation for an org of ≤ 500 employees returns within 2 seconds | Automated integration test with seed dataset at scale boundary | (Assumption) |
| NFR-3 | Security / Auth | All non-health endpoints require a valid authentication token (JWT Bearer or API key); unauthenticated requests return HTTP 401 | Automated test suite: call every protected endpoint without token, assert 401 | (Assumption — token mechanism TBD, see Open Questions) |
| NFR-4 | Security / Authorisation | Role-based access control enforced at the API layer; UI role-gating is supplementary only | Penetration / boundary test: manager token calling HR-only endpoint returns 403; employee token calling manager endpoint returns 403 | Roles: `hr_admin`, `manager`, `employee`, `compliance_officer` |
| NFR-5 | Security / Data privacy | No employee PII is logged in plain text in application logs | Code review + log audit in CI; confirm log output contains only IDs, not names or emails | (Assumption) |
| NFR-6 | Availability | Service uptime ≥ 99.5 % during business hours (Mon–Fri 07:00–19:00 local) | Uptime monitor alert threshold; reviewed monthly | (Assumption) |
| NFR-7 | Scalability | Data model and queries support ≥ 500 employees, ≥ 100 courses, ≥ 10 000 completion records without schema changes | Query-plan review; integration test at stated data volume | (Assumption — single-org deployment) |
| NFR-8 | Observability | Structured JSON logs for every API request including: timestamp, method, path, status code, response time ms, authenticated user role (not name) | Log output verified in CI; sample log line validated against schema | (Assumption) |
| NFR-9 | Observability | `/health` endpoint returns `{"status": "ok"}` with HTTP 200 within 200 ms; no auth required | Automated health-check test in CI and ops monitoring | |
| NFR-10 | Compliance / Data retention | Completion history (including archived/superseded records) is never hard-deleted via normal application operations; only explicit admin purge (out of scope for MVP) could remove records | Unit test: recertification flow confirms prior record status = `archived`, not deleted; row count unchanged | Business rule: audit trail must survive recertification |
| NFR-11 | Operability | Application deployable via a single `docker compose up` command with environment variables for secrets; seed script executable via one documented command | Verified by running documented setup steps on a clean environment in CI | (Assumption) |
| NFR-12 | Compliance / Business rules | Expiry date computation uses calendar-month arithmetic (not 30-day approximation) matching the validity_period_months field | Unit tests covering month-boundary edge cases (e.g., Jan 31 + 1 month = Feb 28/29) | |

---

## 7. Data & Integrations

### Core Entities

| Entity | Key fields | Notes |
|--------|-----------|-------|
| `Course` | `id`, `name`, `category` (enum: safety/security/role_specific), `validity_period_months` (nullable), `required_for_all` (bool), `is_active` (soft-delete), `reference_notes` | validity_period_months = null → no expiry |
| `JobRole` | `id`, `name` | e.g., Engineer, Analyst, Manager |
| `Department` | `id`, `name` | e.g., Engineering, Operations, HR |
| `RoleCourseRequirement` | `id`, `job_role_id`, `course_id`, `assigned_at`, `removed_at` (nullable) | Soft-removal preserves history; active = removed_at IS NULL |
| `Employee` | `id`, `full_name`, `email`, `department_id`, `job_role_id`, `manager_id` (self-FK, nullable), `active` (bool), `created_at` | manager_id = null for top-level employees |
| `CompletionRecord` | `id`, `employee_id`, `course_id`, `completion_date`, `expiry_date` (computed, stored), `status` (enum: active/archived), `recorded_by_employee_id`, `created_at` | Only one `active` record per employee+course at a time |
| `User` | `id`, `employee_id` (FK, nullable for system accounts), `role` (enum: hr_admin/manager/employee/compliance_officer), `hashed_credential` | Auth identity linked to employee record |

### Derived / Computed Concepts
- **Compliance status** per employee+course: derived at query time from `CompletionRecord.expiry_date` vs today; not stored as a column to avoid staleness.
- **Team compliance summary**: aggregated at request time by filtering `Employee.manager_id`.

### External Integrations
- **None in MVP.** LMS, HRIS, and SCORM systems are explicitly out of scope.
- The `reference_notes` field on `Course` and a `certificate_reference` free-text field on `CompletionRecord` can store external URLs/IDs as plain strings for future use.

### API Structure
- Base path: `target-apps/training-compliance/`
- Framework: FastAPI
- OpenAPI schema auto-generated at `/docs` and `/openapi.json`
- Key route groups: `/health`, `/auth`, `/courses`, `/job-roles`, `/departments`, `/role-requirements`, `/employees`, `/completions`, `/compliance/me`, `/manager/team-compliance`, `/reports/org` (compliance officer)

---

## 8. Analytics & Observability

### Logging
- Structured JSON logs on every HTTP request: `timestamp`, `method`, `path`, `status_code`, `duration_ms`, `user_role`, `user_id` (opaque ID, not PII name).
- Business events logged at INFO level: course created/updated, employee activated/deactivated, completion recorded/archived.
- Errors logged at ERROR level with stack trace; no PII in log payloads.

### Key Metrics (in-app, no external APM assumed for MVP)
| Metric | Surface |
|--------|---------|
| Org-wide completion rate % | Compliance officer dashboard |
| Completion rate % by department | Compliance officer dashboard |
| Count of employees with ≥ 1 overdue required course | Compliance officer dashboard |
| Count of employees expiring within 30 days | Compliance officer dashboard |
| Worst-gap courses (missing + expired count, ranked) | Compliance officer dashboard |
| Team compliance % | Manager team board |
| Individual compliance status per course | Employee self-view and HR admin view |

### Alerts (In-App Only)
- Badge / banner on manager board when ≥ 1 direct report has an expired required course.
- Banner on compliance officer dashboard when org-wide completion rate drops below a configurable threshold (default 80 %, assumption).
- Data quality indicator on employee detail when `data_quality_flag` is set (FR-12).

### Health Check
- `GET /health` → `{"status": "ok", "db": "ok"}` — checks database connectivity; no auth required.

---

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Compliance status computed incorrectly at month boundaries (e.g., leap years, month-end dates) | Audit findings, loss of trust | Unit-test calendar-month arithmetic with ≥ 10 edge cases; use a well-tested date library; store computed `expiry_date` at write time so reads are deterministic |
| Manager-scoping bypass: employee in two managers' teams or manager_id manipulation | Data privacy, compliance breach | Enforce `manager_id` filter exclusively at API layer; UI role-gating is defence-in-depth only; add integration test asserting cross-team 403s |
| Inactive employee data leaking into active compliance counts | Incorrect audit numbers | Centralise `active = true` filter in a shared query utility; test all aggregate endpoints with seeded inactive employees |
| Recertification race condition: two completions submitted simultaneously supersede each other incorrectly | Duplicate active records, incorrect compliance state | Use database transaction with row-level lock or unique constraint on (employee_id, course_id, status=active); test concurrent submission scenario |
| Seed data not representative enough to demonstrate all dashboard states | Poor demo / stakeholder confidence | Enumerate required demo states in FR-13 acceptance criteria; verify seed script in CI against that checklist |
| Auth token mechanism not decided before development starts | Blocked API integration with Streamlit | Resolve in kickoff (see Open Questions OQ-1); default to JWT Bearer if no decision made within one sprint |
| Growing completion history slows compliance aggregate queries over time | Degraded UX at audit time | Index `(employee_id, course_id, status)` on CompletionRecord; benchmark at 10 000 records before MVP release |

---

## 10. Open Questions

| # | Question | Suggested owner |
|---|----------|-----------------|
| OQ-1 | What authentication mechanism should be used? Options: JWT (self-issued), OAuth2/OIDC (SSO), or simple API-key per user. Impacts Streamlit session design. | Tech lead + HR stakeholder |
| OQ-2 | Should employees be able to self-record completions, or is that exclusively an HR admin action? (Brief implies HR admin records on behalf of anyone; employee self-service is ambiguous.) | HR (Marcus) |
| OQ-3 | What is the configurable threshold for the org-wide completion-rate alert banner? Is 80 % the right default? | Compliance officer persona |
| OQ-4 | Should `validity_period_months = 0` mean "no expiry" or "expires immediately"? The brief uses null for no-expiry; clarify whether 0 is a valid input or a validation error. | Tech lead |
| OQ-5 | Is there a requirement to export compliance data (CSV, PDF) for audit submission, or is the on-screen view sufficient for the quarterly audit? | HR (Marcus) |
| OQ-6 | How should role-course requirements behave when a course is soft-deleted? Should existing requirements be automatically removed, or block deletion if active requirements exist? | Tech lead + HR |
| OQ-7 | Should managers also have a `manager` job role, or is the `manager_id` foreign key on Employee independent of the job role field? (An employee can be both a manager of others and hold a non-manager job role.) | HR (Marcus) |
| OQ-8 | What is the expected deployment environment — local Docker only, or a cloud host? Affects NFR-6 uptime monitoring approach. | Engineering lead |
| OQ-9 | Is there a maximum lookback period for historical completion records visible to the compliance officer, or should all-time history be queryable? | Compliance officer persona |
| OQ-10 | Should the "expiring within 30 days" window be configurable per course or fixed org-wide? | HR (Marcus) |

---

## 11. Delivery & Client Surface

| Concern | Choice | Implementation notes |
|---------|--------|---------------------|
| Client UI | **Streamlit** | Role-gated screens: HR catalog & roster, manager team board, employee "my trainings", compliance officer dashboard. Login screen determines role from auth response and conditionally renders screen set. |
| API | FastAPI under `target-apps/training-compliance/` | REST + OpenAPI; auto-docs at `/docs`. Route groups per section 7. |
| UI location | `target-apps/training-compliance/ui/streamlit_app.py` | HTTP client (e.g., `httpx` or `requests`) to API only — never import `app/` or internal modules from Streamlit layer. |
| Auth for UI | Matches API auth mechanism (JWT Bearer, per OQ-1) | Streamlit stores token in `st.session_state`; passed as `Authorization: Bearer <token>` header on every API call. Token cleared on logout or session expiry. |
| Role-gating in UI | Server-enforced (API 403) + client-side nav filtering | On login, Streamlit reads `role` from auth response and renders only that role's sidebar navigation. API enforcement is the authoritative gate. |
| Demo data | Seed script at `target-apps/training-compliance/scripts/seed_demo_data.py` | Satisfies FR-13 spec: ≥ 6 courses, ≥ 3 roles, ≥ 3 depts, ≥ 15 employees, mixed compliance states, one inactive employee. |
| Health check | `GET /health` — no auth | Returns `{"status": "ok", "db": "ok"}` for ops monitoring. |
| Deployment | `docker compose up` from `target-apps/training-compliance/` | Separate services: `api` (FastAPI/Uvicorn), `ui` (Streamlit), `db` (PostgreSQL or SQLite for MVP — see OQ-8). Environment variables for secrets via `.env` file. |

---

## Appendix: Assumptions

- **Authentication token format**: JWT Bearer token is assumed as the default; final decision pending OQ-1. If a simpler API-key approach is chosen, the Streamlit session design adapts accordingly.
- **Database**: PostgreSQL is assumed for production-like deployments; SQLite may be acceptable for local demo runs — to be confirmed via OQ-8.
- **No expiry = validity_period_months IS NULL**: A null value means the course never expires. Zero is treated as a validation error until OQ-4 is resolved.
- **"Expiring soon" window is fixed at 30 calendar days** for the MVP; configurability deferred unless OQ-10 is resolved before development.
- **Employee self-recording completions is not permitted in MVP** unless OQ-2 resolves otherwise; only HR admin records completions on behalf of any employee.
- **Calendar-month arithmetic**: `expiry_date` is computed as `completion_date` plus `validity_period_months` calendar months using standard date library semantics (e.g., Jan 31 + 1 month = last day of February).
- **Single organisation deployment**: No multi-tenancy; all data belongs to one organisation. Isolation is role-based, not tenant-based.
- **Org-wide completion-rate alert threshold defaults to 80 %** pending confirmation from OQ-3.
- **P95 latency target of 500 ms** and **99.5 % availability** are reasonable defaults for an internal compliance tool; not stated in the brief.
- **User accounts are pre-provisioned by HR admin**: There is no self-registration flow in MVP. HR admin creates employee records; a linked user account is created separately or simultaneously (mechanism TBD with OQ-1).
- **`manager_id` and job role are independent fields**: An employee can hold any job role and simultaneously be listed as the manager of other employees without those being the same concept (pending OQ-7 confirmation).
- **Soft-deleted courses block new completions** but existing completion history and active role-requirements referencing them require explicit handling (see OQ-6).
- **No file upload**: The `certificate_reference` field on CompletionRecord is a plain text/URL string; no binary storage is provided.
- **Streamlit runs as a separate process/container** from the FastAPI service and communicates only over HTTP; no shared in-process state.
- **Demo seed script is idempotent**: Re-running it on a populated database does not duplicate records (uses upsert or clears and re-seeds).
