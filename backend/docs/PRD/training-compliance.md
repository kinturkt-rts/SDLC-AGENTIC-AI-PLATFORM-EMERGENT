# Training & Certification Compliance PRD

## 1. Overview

Marcus, an HR administrator, currently tracks mandatory training completions through spreadsheets and inbox searches. This creates blind spots: managers cannot see which direct reports are out of compliance until an issue is escalated, and quarterly audits are time-consuming and error-prone. There is no single authoritative source for course requirements, completion records, or expiry status across the organization.

The proposed solution is a web application (API-first, Streamlit UI) that centralizes the course catalog, employee roster, and completion records. It calculates compliance status in real time — distinguishing between "never taken," "current," and "expired" — and surfaces role-gated views so HR, managers, employees, and compliance officers each see exactly the data they need without being able to corrupt records outside their authority.

The MVP covers course catalog management, a role-to-course requirement matrix, completion recording with automatic expiry calculation, recertification logic, and four distinct role-gated UI screens. Inactive employees are excluded from live compliance counts while their history is preserved. Email/SMS, LMS integration, and multi-tenancy are out of scope.

---

## 2. Goals & Success Metrics

| Goal | Metric | Target | Notes |
|------|--------|--------|-------|
| Eliminate spreadsheet-based compliance tracking | % of completion records entered via application vs. spreadsheet | 100 % within target org after rollout | Baseline is 0 % |
| Reduce audit preparation time | Hours HR spends preparing quarterly compliance report | ≤ 1 hour (vs. current baseline TBD) | Measured via HR self-report |
| Surface at-risk employees before expiry | % of expiring-within-30-days completions visible to manager before expiry date | 100 % | System-calculated; verified by QA |
| Manager self-service compliance visibility | % of managers able to view their own team dashboard without HR assistance | 100 % | Usability test criterion |
| Data integrity on inactive employees | Inactive employees excluded from compliance rate calculations | 0 false inclusions | Automated test on compliance percentage endpoint |
| Demo readiness | Seed data covers all required scenario types | 6+ courses, 15+ employees, 3+ departments, mixed states | Verified by seeding script |

---

## 3. Non-Goals / Out of Scope

- LMS integration, SCORM content hosting, or video delivery
- Email or SMS reminder notifications (in-app alerts only)
- External certificate file storage beyond a free-text or URL reference field
- Multi-language / internationalization
- Multi-tenant architecture (single organization deployment)
- Role or department hierarchy beyond one manager-per-employee relationship
- Retroactive penalty when a job role's required course list changes
- Automated payroll or HR system sync (roster is managed manually in this application)
- Mobile-native application
- Payment or billing features

---

## 4. Users & Use Cases

| Persona | Need | Primary use case |
|---------|------|------------------|
| HR Administrator (Marcus) | Define course catalog, manage roster, record completions for any employee, run full org view | Creates a new mandatory course, assigns it to a job role, records batch completions after a training session, deactivates a departed employee |
| Manager | Monitor own team's compliance without accessing other departments or editing catalog | Opens team board each Monday; sees who has expired or expiring requirements; drills into an individual employee's status |
| Employee | View personal required trainings, completion dates, and expiry status | Logs in before a team meeting to confirm which courses are current and which need renewal |
| Compliance Officer | Read-only org-wide dashboards for audit evidence and gap analysis | Pulls quarterly report showing completion rate by department, overdue counts, and courses with the most gaps |
| Ops / Unauthenticated | Confirm the service is running (health check endpoint) | Monitoring tool pings `/health` to verify uptime |

---

## 5. Functional Requirements

| ID | Description | Priority | Acceptance criteria (Given / When / Then) |
|----|-------------|----------|-------------------------------------------|
| FR-1 | **Course catalog — CRUD** HR admin can create, update, and deactivate a course with fields: name (unique), category (safety \| security \| role-specific), validity period in months (nullable for one-time-only), required-for-all-staff flag, and an optional certificate reference field. | P0 | **Given** an authenticated HR admin; **When** they submit a valid course creation request; **Then** the course is persisted, returned with a system-generated ID, and appears in the catalog list. **When** they attempt to create a duplicate course name; **Then** the API returns HTTP 409. |
| FR-2 | **Employee roster — CRUD** HR admin can create, update, and soft-deactivate employees. Employee record includes: full name, email (unique), department, job role, manager (reference to another employee record), and active/inactive flag. Deactivation does not delete the record or its completion history. | P0 | **Given** an authenticated HR admin; **When** they deactivate an employee; **Then** the employee's `active` flag is set to `false`, all prior completion records are retained, and the employee no longer appears in active compliance counts or manager team views. |
| FR-3 | **Role-to-course requirement matrix** HR admin can assign one or more courses as mandatory for a given job role. Changing the matrix affects only future compliance evaluations for employees currently in that role; no retroactive penalty is applied for removed courses. | P0 | **Given** course C is added as mandatory for role R; **When** the compliance status for employee E (role R, no completion for C) is evaluated; **Then** E's status for C is "missing." **Given** course C is subsequently removed from role R's requirements; **When** E's compliance is re-evaluated; **Then** C no longer appears as a gap for E. |
| FR-4 | **Record training completion** HR admin (for any employee) or Employee (for themselves only) can record a completion with: employee, course, completion date. The system calculates expiry date as `completion_date + validity_period_months` (null expiry if the course has no validity period). A new completion for the same employee + course replaces the prior active record (recertification); the old record is preserved in history. | P0 | **Given** employee E has an existing active completion for course C with expiry date D; **When** a new completion is recorded for E + C with completion date D2 > D; **Then** the new record becomes the active completion, the expiry is recalculated from D2, and the original record is marked superseded but retained. |
| FR-5 | **Per-employee compliance view** The system derives a compliance status per required course for each active employee: `current` (active non-expired completion exists), `expired` (completion exists but expiry date < today), or `missing` (no current non-expired completion). Courses required for the employee's role and all-staff courses are included; courses not applicable to the role are excluded. | P0 | **Given** today is T; **When** the compliance endpoint for employee E is called; **Then** each applicable course appears exactly once with the correct status; inapplicable courses do not appear; inactive employees return HTTP 403 or empty active compliance (no contribution to percentages). |
| FR-6 | **Manager team compliance view** An authenticated manager can retrieve the compliance summary for all active employees where `manager_id` equals their own employee ID. The response must not include employees from other managers' teams. | P0 | **Given** manager M1 is authenticated; **When** they request the team compliance endpoint; **Then** only employees whose `manager` field references M1 are returned; a request including a different manager's employee ID returns HTTP 403 or an empty result for that employee. |
| FR-7 | **Compliance officer org-wide dashboard** A read-only compliance officer role can retrieve: (a) count and list of employees with at least one overdue required course, (b) employees with at least one required course expiring within the next 30 days, (c) completion rate (% employees fully current / total active employees) broken down by department, (d) courses ranked by number of active employees missing or expired. | P0 | **Given** seed data with known overdue/expiring states; **When** the dashboard endpoint is called by a compliance officer; **Then** overdue and expiring counts match expected values from seed data; completion rate per department is correct to ± 0; compliance officer cannot call any write endpoint (returns HTTP 403). |
| FR-8 | **Role-gated Streamlit UI** The Streamlit application provides four authenticated screens gated by role: (1) HR admin — catalog management, roster management, record completion; (2) Manager — team compliance board (own team only); (3) Employee — "My Trainings" view (required courses, status, expiry dates); (4) Compliance Officer — org-wide dashboard and alert panels. Unauthenticated users are redirected to a login screen. The Streamlit app communicates exclusively via the FastAPI REST API; it never imports application modules directly. | P0 | **Given** a user with role "manager" logs in; **When** they navigate the UI; **Then** only the team board screen is accessible; catalog management and other teams' data are not visible or reachable. **Given** an unauthenticated session; **When** any protected screen is accessed; **Then** the user is redirected to the login page. |
| FR-9 | **In-app compliance alerts** The system exposes an alerts endpoint (and surfaces results in the Compliance Officer and Manager UIs) that flags: (a) any active employee with at least one expired required course, (b) any employee marked inactive who has open compliance ownership items (informational — to prompt HR to reassign or archive). Inactive employees are excluded from active compliance counts automatically. | P1 | **Given** employee E has an expired required course; **When** the alerts endpoint is called; **Then** E appears in the overdue alert list. **Given** employee E is deactivated; **When** compliance percentages are computed; **Then** E is not counted in the denominator or numerator. |
| FR-10 | **Soft cap data-quality flag** The system flags any employee who has more than 20 active (non-superseded) course completion records. This flag is surfaced as a warning in the HR admin view and via the alerts endpoint; it does not block further record creation. | P2 | **Given** employee E has 21 non-superseded completion records; **When** the HR admin views E's record or calls the alerts endpoint; **Then** a data-quality warning is returned indicating the soft cap is exceeded. **Given** E has exactly 20 records; **Then** no warning is returned. |
| FR-11 | **Demo / seed data script** A runnable seed script populates: at least 6 courses spanning all-staff and role-specific categories, at least 3 job roles, at least 3 departments, at least 15 active employees with mixed compliance states (current, expired, missing), at least 3 employees with completions expiring within 30 days, at least 2 employees with never-started required courses, and at least 1 inactive employee with historical completion records. | P0 | **Given** a clean database; **When** the seed script is executed; **Then** all counts above are met, the compliance officer dashboard returns non-zero values for overdue and expiring-soon lists, and no errors are raised. |
| FR-12 | **Health check endpoint** An unauthenticated `GET /health` endpoint returns HTTP 200 with a JSON body indicating service status. | P0 | **Given** the service is running; **When** `GET /health` is called without authentication; **Then** HTTP 200 and `{"status": "ok"}` (or equivalent) are returned within 500 ms. |

---

## 6. Non-Functional Requirements

| ID | Category | Target | Measurement / verification | Notes |
|----|----------|--------|---------------------------|-------|
| NFR-1 | Performance | API p95 response time ≤ 500 ms for all read endpoints under expected load | Load test with realistic seed data (15–100 employees); measure p95 latency | (Assumption) — no explicit SLA stated in brief |
| NFR-2 | Performance | Compliance status computation for a single employee ≤ 200 ms | Unit + integration test timing assertions | (Assumption) |
| NFR-3 | Security / Auth | All non-health endpoints require a valid JWT Bearer token; role claim enforced server-side on every request | Automated tests: call each protected endpoint without token → expect HTTP 401; call with wrong role → expect HTTP 403 | Auth mechanism assumed JWT; scheme to be confirmed — see Open Questions |
| NFR-4 | Security / Privacy | Managers cannot retrieve any data for employees outside their direct team, enforced at the API layer (not only UI) | Integration test: manager token calls endpoint with another manager's employee ID; expect HTTP 403 or empty result | Critical business rule |
| NFR-5 | Availability | Service available ≥ 99 % during business hours | Uptime monitoring via `/health` check; alert on consecutive failures | (Assumption) — deployment target TBD |
| NFR-6 | Scalability | Data model and queries support at least 500 employees and 50 courses without schema changes | Query explain-plan review; optional load test at 500-employee scale | (Assumption) — org size not stated in brief |
| NFR-7 | Observability | All API requests logged with: timestamp, method, path, response status, latency, authenticated user ID (no PII in logs beyond user ID) | Log output verified in local and CI runs; structured JSON logging preferred | (Assumption) |
| NFR-8 | Observability | Application exposes a `/metrics` endpoint or equivalent for error rate and request count | Verified by calling endpoint; or confirmed via structured log aggregation | (Assumption) — tooling TBD |
| NFR-9 | Data Integrity | Completion records are never hard-deleted; deactivation and recertification use soft-delete / superseded flags | Database-level audit: verify record count is non-decreasing after deactivation and recertification operations | Core business rule |
| NFR-10 | Operability | Application configured entirely via environment variables (database URL, secret key, token expiry); no secrets in source code | Code review; `.env.example` provided; CI scan for hardcoded credentials | (Assumption) |
| NFR-11 | Compliance / Data Retention | Historical completion records retained indefinitely (no automatic purge) within the deployment's storage | No scheduled deletion jobs; verified by schema review | Aligns with audit requirement |

---

## 7. Data & Integrations

### Core Entities

| Entity | Key Fields |
|--------|-----------|
| `Course` | `id`, `name` (unique), `category` (enum: safety / security / role-specific), `validity_period_months` (nullable), `required_for_all_staff` (bool), `certificate_reference_field` (text, optional), `is_active` (bool) |
| `JobRole` | `id`, `name` (unique) |
| `Department` | `id`, `name` |
| `Employee` | `id`, `full_name`, `email` (unique), `department_id` (FK), `job_role_id` (FK), `manager_id` (FK → Employee, nullable), `is_active` (bool) |
| `RoleRequirement` | `id`, `job_role_id` (FK), `course_id` (FK) — composite unique |
| `CompletionRecord` | `id`, `employee_id` (FK), `course_id` (FK), `completion_date` (date), `expiry_date` (date, nullable), `is_active_record` (bool — false when superseded), `superseded_by_id` (FK → CompletionRecord, nullable), `created_at` |
| `User` | `id`, `employee_id` (FK, nullable for service accounts), `role` (enum: hr_admin / manager / employee / compliance_officer), `hashed_password` |

### Compliance Status Derivation (computed, not stored)

- **current**: `CompletionRecord` with `is_active_record = true` AND (`expiry_date IS NULL` OR `expiry_date >= today`)
- **expired**: `CompletionRecord` with `is_active_record = true` AND `expiry_date < today`
- **missing**: No `CompletionRecord` with `is_active_record = true` for the applicable course

Applicable courses = courses where `required_for_all_staff = true` OR course is in `RoleRequirement` for employee's `job_role_id`.

### External Integrations

| System | Scope | Notes |
|--------|-------|-------|
| None in MVP | — | LMS, HRIS, email, and SSO are explicitly out of scope |
| FastAPI REST API | Internal | Streamlit UI communicates with FastAPI only via HTTP; no direct DB access from UI layer |

### API Structure

- Base path: `target-apps/training-compliance/`
- OpenAPI spec auto-generated by FastAPI at `/docs` and `/openapi.json`
- Key route groups: `/health`, `/auth`, `/courses`, `/employees`, `/roles`, `/requirements`, `/completions`, `/compliance`, `/reports`, `/alerts`

---

## 8. Analytics & Observability

**Structured Logging**
- Every API request logged as JSON: `timestamp`, `method`, `path`, `status_code`, `duration_ms`, `user_id`, `role`.
- No PII (names, emails) written to logs; use `user_id` only.
- Error responses log full exception traceback at ERROR level (server-side only).

**Key Business Metrics to Track**
| Metric | How surfaced |
|--------|-------------|
| Org-wide compliance rate (% employees fully current) | `/reports/compliance-rate` endpoint; Compliance Officer dashboard |
| Employees overdue (≥ 1 expired required course) | `/alerts/overdue` endpoint |
| Employees expiring within 30 days | `/alerts/expiring-soon?days=30` endpoint |
| Completion rate by department | `/reports/by-department` endpoint |
| Courses with most gaps | `/reports/course-gaps` endpoint |
| Data-quality flags (>20 active records) | `/alerts/data-quality` endpoint |

**Operational Alerts (Assumption)**
- Monitoring system (TBD) polls `/health` every 60 seconds; pages on-call if two consecutive failures occur.
- Application logs shipped to a log aggregator (tooling TBD); alert on error rate > 5 % over 5-minute window.

---

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Compliance status computed incorrectly (expiry date off-by-one, timezone handling) | Audit failure; regulatory exposure | Comprehensive unit tests covering boundary dates (today = expiry date is "current"), UTC-normalized date storage, explicit test cases in CI |
| Manager data isolation breach (sees other team's data) | Privacy violation; trust loss | Server-side enforcement of `manager_id` filter on every query; integration tests specifically asserting cross-team data is blocked |
| Inactive employees incorrectly counted in compliance percentages | Misleading audit report | Automated test validates denominator excludes inactive; seed data includes inactive employee to exercise this path |
| Role changes causing retroactive compliance gaps | User confusion; incorrect remediation | Business rule explicitly implemented: requirement matrix is evaluated at query time against current role; no historical penalty; documented in UI |
| Recertification creates duplicate active records | Data integrity issue | Database constraint or application-layer enforcement: before inserting new completion, supersede existing active record for same employee + course atomically |
| Seed data does not cover all compliance states | Demo failure during stakeholder review | Seed script has assertion checks post-insert to verify minimum counts; run in CI |
| Streamlit UI imports app modules directly (coupling) | Breaks separation of concerns; hidden failures in API | Code review gate: Streamlit files must only use `requests` / `httpx`; import linting rule or test |
| Authentication token not validated server-side on write endpoints | Privilege escalation | Every endpoint has an explicit role guard; automated security test suite covers each endpoint × each unauthorized role |

---

## 10. Open Questions

| # | Question | Suggested owner |
|---|----------|-----------------|
| 1 | What identity provider or auth mechanism should be used? (Local username/password with JWT assumed for MVP — confirm before implementation) | HR stakeholder + Engineering lead |
| 2 | Is `completion_date` always self-reported, or will there be bulk import from training vendors in a future phase? (Affects data model extensibility) | Marcus (HR) |
| 3 | What is the expected maximum number of employees in the organization? (Affects indexing strategy and pagination defaults) | HR / IT |
| 4 | Should the compliance officer role be a separate login account or a flag on an existing employee record? | Marcus (HR) |
| 5 | What is the deployment target — local Docker, cloud PaaS, on-premise server? (Affects NFR-5 availability design) | Engineering / IT Ops |
| 6 | Is the `validity_period_months` always in whole months, or do some courses use days/weeks? (Affects expiry date calculation precision) | Marcus (HR) |
| 7 | Are there courses required for all staff AND also have additional role-specific completions (i.e., can a course be both flags simultaneously)? | Marcus (HR) |
| 8 | Should the "expiring within 30 days" window be configurable (e.g., some orgs want 60 days)? | Compliance Officer |
| 9 | Is there a need for manager delegation (e.g., acting manager while primary manager is on leave)? | HR stakeholder |
| 10 | Should the certificate reference field store a URL, a document ID, or free text? Are there access control requirements on that reference? | Marcus (HR) + Legal/Compliance |
| 11 | What happens if an employee changes job roles? Should their prior role's completed-but-no-longer-required courses remain visible in history? | Marcus (HR) |
| 12 | Is multi-factor authentication required given this is a compliance system handling audit-relevant data? | IT Security |

---

## 11. Delivery & Client Surface

| Concern | Choice | Implementation notes |
|---------|--------|---------------------|
| Client UI | **Streamlit** | Role-gated screens: HR Catalog & Roster, Manager Team Board, Employee "My Trainings", Compliance Officer Dashboard. Login screen for unauthenticated sessions. |
| API | **FastAPI** under `target-apps/training-compliance/` | REST + OpenAPI; auto-docs at `/docs`; all business logic lives here |
| UI location | `target-apps/training-compliance/ui/streamlit_app.py` | Communicates with API via HTTP (`requests` or `httpx`) only — **never** imports `app/` or any FastAPI module directly |
| Auth for UI | JWT Bearer token (Assumption) | Streamlit stores token in `st.session_state`; token sent as `Authorization: Bearer <token>` header on every API call; login screen collects credentials and calls `/auth/token` |
| Role enforcement | Server-side (API layer) — UI reflects role but does not gate security | UI hides irrelevant screens per role for UX; API rejects unauthorized calls regardless of UI state |
| Seed / demo data | `target-apps/training-compliance/seed.py` | Idempotent script; verifies post-insert counts; runnable via `python seed.py` |
| Directory structure | `target-apps/training-compliance/` root contains `app/` (FastAPI), `ui/` (Streamlit), `seed.py`, `requirements.txt`, `.env.example`, `README.md` | Standard layout per project conventions |

---

## Appendix: Assumptions

- **Authentication**: JWT Bearer token with local username/password for MVP. No external SSO or OAuth provider assumed. Token contains `user_id` and `role` claims.
- **Database**: A relational database (e.g., SQLite for local dev / PostgreSQL for production) is assumed. ORM-based access (e.g., SQLAlchemy). No NoSQL or document store required.
- **Timezone handling**: All dates stored as UTC. `today` for expiry comparisons is evaluated server-side in UTC. Client displays dates in local timezone (Streamlit).
- **One manager per employee**: The data model supports a single `manager_id` per employee. Matrix/dotted-line reporting is out of scope.
- **Validity period in whole months**: `expiry_date = completion_date + relativedelta(months=validity_period_months)`. Confirmed as assumption pending Open Question 6.
- **All-staff courses apply regardless of job role**: If `required_for_all_staff = true`, the course appears in every active employee's compliance view independent of role matrix.
- **Compliance rate definition**: `(active employees with zero missing/expired required courses) / (total active employees) × 100`. Employees with no required courses count as fully compliant.
- **Recertification atomicity**: Superseding the prior active record and inserting the new record occur in a single database transaction to prevent duplicate active records.
- **User accounts are separate from employee records**: A `User` table holds credentials and role; it references the `Employee` table. Not every user need have an employee record (e.g., a system admin), but in practice all four named personas correspond to employee records.
- **Soft cap of 20 active records is advisory only**: It does not block writes or trigger any automated action beyond a warning flag.
- **Performance targets** (p95 ≤ 500 ms, compliance computation ≤ 200 ms) are reasonable defaults for an internal tool at the stated scale; no explicit SLA was provided.
- **Availability target** (99 % during business hours) is a reasonable default for an internal compliance tool; no explicit uptime requirement was stated.
- **Expiring-soon window** defaults to 30 days as stated in the brief; assumed to be hardcoded for MVP (configurable in a later phase).
- **No bulk import in MVP**: Completions are entered individually via the UI or API; CSV import is not in scope unless added as a future requirement.
- **No pagination specified**: API endpoints will return paginated results (default page size 50) to support future scale; pagination parameters are optional for MVP with small seed data.
- **Certificate reference field**: Free-text / URL string, no access control or storage integration required in MVP.
