# Field Service Dispatch — Product Requirements Document

## 1. Overview

Dana's HVAC shop operates a 15-technician field service team whose dispatch workflow today relies on a shared whiteboard and group text threads. This creates coordination failures: unclear assignment ownership, no audit trail for disputes, no systematic SLA visibility, and no structured workload view for the owner. The tool must replace that informal system without the complexity or cost of enterprise platforms like Salesforce.

The proposed solution is a lightweight, role-aware web application backed by a FastAPI REST service and a Streamlit dispatcher board. It manages customer records, work orders, technician rosters, and daily dispatch in a single coherent interface. Three internal roles — Dispatcher, Technician, and Owner — each receive a scoped view and scoped write permissions, enforced at the API layer.

The MVP scope covers the complete work-order lifecycle (new → assigned → in-progress → completed/cancelled), same-day SLA flagging for urgent jobs, completion documentation with parts capture, and a full status-change audit log. GPS tracking, customer-facing SMS, payments, and inventory stock depletion are explicitly out of scope for this release.

---

## 2. Goals & Success Metrics

| Goal | Metric | Target | Notes |
|------|--------|--------|-------|
| Eliminate whiteboard dispatch | % of active work orders managed in system | 100 % within pilot period | Baseline is 0 % |
| Reduce missed SLA visibility lag | Time from SLA breach to dispatcher awareness | < 5 minutes (auto-surface on board refresh) | Board must highlight breaches without manual search |
| Correct assignment ownership | Orders with more than one active assignment | 0 (enforced by API constraint) | Business rule enforcement |
| Reduce dispute resolution time | Availability of full status-change audit trail | 100 % of state transitions logged with actor and timestamp | No gaps in history |
| Technician self-service status updates | % of status changes made by technicians on their own jobs | Target ≥ 80 % (reduce dispatcher manual updates) | Assumption |
| Demo readiness | Seed dataset covers all statuses, ≥ 1 breached SLA, parts on completed jobs | Pass/Fail checklist | Required for client demo |

---

## 3. Non-Goals / Out of Scope

- GPS or real-time location tracking of technicians or vehicles
- Outbound SMS or email notifications to customers
- Payment processing, invoicing, or billing workflows
- Inventory stock depletion or purchase-order management
- Customer-facing self-service portal or public scheduling
- Mobile-native application (iOS / Android)
- Integration with external CRM, ERP, or accounting systems
- Automated scheduling / AI-driven route optimization
- Multi-tenant / multi-shop support

---

## 4. Users & Use Cases

| Persona | Need | Primary use case |
|---------|------|------------------|
| **Dispatcher** | Create and manage customers, work orders, and technician assignments; reschedule and cancel orders; add addendum notes to completed jobs | Opens the board for today, views the unassigned queue and per-technician columns, drags or selects an assignment, monitors SLA breach highlights, reschedules an order when a tech calls out |
| **Technician** | View only their own assigned jobs for today; advance status (accepted → in-progress → completed); attach parts used and completion notes on active jobs | Arrives on site, opens "My Jobs Today", marks job in-progress, adds parts as they are used, submits completion notes to close the job |
| **Owner** | Read-only visibility into the full daily board, technician workload distribution, SLA breach count, and completed-job details | Reviews morning board to assess workload balance; checks end-of-day completed jobs and parts costs; spot-checks audit history on a disputed order |
| **Public / Unauthenticated** | Infrastructure health verification | Calls `GET /health` endpoint; receives 200 OK — no other data accessible |

---

## 5. Functional Requirements

| ID | Description | Priority | Acceptance criteria (Given / When / Then) |
|----|-------------|----------|-------------------------------------------|
| FR-1 | **Customer records management** — Dispatcher can create, read, update, and soft-delete customer records containing: full name, primary phone, email (optional), and service address (street, city, state, ZIP). | P0 | **Given** an authenticated Dispatcher, **When** a POST to `/customers` is submitted with valid required fields, **Then** the record is persisted and returned with a unique ID and 201 status. **When** a required field is missing, **Then** a 422 validation error is returned and no record is created. |
| FR-2 | **Work order lifecycle** — The system shall support work orders linked to a customer with fields: description, priority (`routine` or `urgent`), scheduled date, time window (`morning`, `afternoon`, `all-day`), and a lifecycle status machine: `new → assigned → in_progress → completed` (terminal) and `new / assigned / in_progress → cancelled` (terminal). Completed and cancelled orders are locked from further status advancement. | P0 | **Given** a work order in state `in_progress`, **When** a Dispatcher or Technician transitions it to `completed`, **Then** the status is updated and no further status transition is accepted. **When** a transition to a non-adjacent or illegal state is attempted, **Then** a 409/422 error is returned. |
| FR-3 | **Technician roster** — Dispatcher can create, read, update, and deactivate technicians with fields: name, skills (multi-select from a defined list: `residential`, `commercial`, `install`, extensible), and `active` boolean flag. Only active technicians may be assigned to orders. | P0 | **Given** a technician with `active = false`, **When** a Dispatcher attempts to assign that technician to a work order, **Then** a 422 error is returned with a message indicating the technician is inactive. **Given** an active technician, **When** skills are updated, **Then** the updated skills list is persisted and returned. |
| FR-4 | **Dispatcher assignment and reassignment** — Dispatcher may assign exactly one active technician to a work order that is in a dispatchable state (`new`). Assignment moves the order to `assigned`. Dispatcher may reassign (replace the technician) while the order is in `assigned` state. Only one active assignment per order is enforced at all times. | P0 | **Given** a work order in `new` state, **When** the Dispatcher assigns an active technician, **Then** the order moves to `assigned` and the assignment record is created. **When** the Dispatcher attempts a second concurrent assignment to the same order without first removing the current one, **Then** a 409 conflict error is returned. **Given** an order in `in_progress` state, **When** a reassignment is attempted, **Then** a 422 error is returned. |
| FR-5 | **Technician-scoped status updates** — Technicians may transition status only on work orders assigned to them. Permitted transitions for a technician: `assigned → in_progress`, `in_progress → completed`. Technicians may not touch orders assigned to other technicians. | P0 | **Given** an authenticated Technician whose user ID does not match the assigned technician on an order, **When** a status-update request is submitted, **Then** a 403 Forbidden is returned and no state change occurs. **Given** the correct assigned technician, **When** they transition `assigned → in_progress`, **Then** the order status is updated and the change is recorded in the audit log with the technician's ID and timestamp. |
| FR-6 | **Completion documentation** — Completing a work order requires non-empty completion notes (free text). Parts used may be submitted as a list of line items (part name, quantity [integer ≥ 1], optional unit cost). An empty parts list is valid. After completion the parts list and completion notes are immutable except for a Dispatcher addendum note field. | P0 | **Given** a Technician attempts to complete a job with an empty or whitespace-only completion notes field, **Then** a 422 error is returned and the order remains `in_progress`. **Given** valid completion notes and an optional parts list, **When** the completion is submitted, **Then** the order moves to `completed`, parts are persisted, and the completion timestamp is recorded. |
| FR-7 | **SLA breach detection and board flagging** — An urgent work order whose scheduled date equals today and whose status is not `completed` or `cancelled` at or after the end of the business day (Assumption: 17:00 local server time) is considered SLA-breached. The daily board API response shall include an `sla_breached` flag on each applicable order. The Streamlit board shall visually highlight breached orders (e.g. red indicator). | P0 | **Given** an urgent work order with `scheduled_date = today` and status `in_progress` and current time ≥ 17:00, **When** the board endpoint is called, **Then** `sla_breached: true` is present on that order's payload. **Given** a routine order under the same conditions, **Then** `sla_breached` is `false`. |
| FR-8 | **Today's dispatch board** — A board endpoint (and corresponding Streamlit view) shall return, for a given date, three sections: (1) unassigned queue (orders with no active assignment), (2) per-technician columns listing each active technician's assigned orders, and (3) a top-level count and list of SLA-breached orders. The board must be filterable by date (default: today). | P0 | **Given** an authenticated Dispatcher or Owner, **When** `GET /board?date=YYYY-MM-DD` is called, **Then** the response contains `unassigned`, `technicians` (array of technician + their orders), and `sla_breaches` sections. **Given** a date with no orders, **Then** the sections are present but empty. |
| FR-9 | **Status-change audit log** — Every transition of a work order's status must be recorded with: order ID, from-status, to-status, actor user ID, actor role, and UTC timestamp. The audit log for a given order is accessible to Dispatcher and Owner roles. | P1 | **Given** any status transition on any order, **When** the transition completes, **Then** a new audit entry exists containing correct `from_status`, `to_status`, `actor_id`, `actor_role`, and `changed_at` fields. **Given** an authenticated Technician requesting the audit log of a different technician's order, **Then** a 403 is returned. |
| FR-10 | **Role-based access control** — Three authenticated roles are enforced at the API layer: `dispatcher` (full CRUD on customers, orders, assignments, roster; addendum on completed orders), `technician` (read own assigned orders; status updates and parts on own active orders), `owner` (read-only on all resources). Unauthenticated requests receive 401 on all endpoints except `GET /health`. | P0 | **Given** an Owner-role token, **When** any mutating request (POST/PUT/PATCH/DELETE) is attempted on any resource, **Then** a 403 is returned and no data is changed. **Given** no auth token, **When** any endpoint other than `GET /health` is called, **Then** a 401 is returned. |
| FR-11 | **Streamlit dispatcher and technician UI** — A Streamlit application at `ui/streamlit_app.py` shall implement the primary user journeys: login/token entry, dispatcher board view (unassigned queue, per-technician columns, SLA breach highlights), technician "My Jobs Today" view with status action buttons, and Owner read-only board. The Streamlit app communicates exclusively via the FastAPI HTTP API and never imports from `app/` directly. | P1 | **Given** a logged-in Dispatcher, **When** the board page loads, **Then** the unassigned queue, technician columns, and any SLA-breached orders are rendered with breach highlighting. **Given** a logged-in Technician, **When** "My Jobs Today" loads, **Then** only orders assigned to that technician are displayed with eligible status-action buttons. |
| FR-12 | **Demo seed data** — A seed script shall populate: ≥ 5 technicians with varied skills, ≥ 5 customers, ≥ 15 work orders across all statuses, a mix of urgent and routine priorities, ≥ 1 urgent order with `scheduled_date` in the past and status not completed (breached SLA), ≥ 2 completed orders with parts line items and completion notes, and assignments covering multiple technicians. | P1 | **Given** the seed script is executed against a clean database, **When** `GET /board?date=<seed_date>` is called, **Then** all three board sections are populated, `sla_breaches` count ≥ 1, and at least two technician columns contain orders. |

---

## 6. Non-Functional Requirements

| ID | Category | Target | Measurement / verification | Notes |
|----|----------|--------|---------------------------|-------|
| NFR-1 | Performance | API p95 response time ≤ 300 ms for all read endpoints under normal load | Load test with realistic dataset (≥ 500 orders); measure via test client or k6 | (Assumption) |
| NFR-2 | Performance | Board endpoint (`GET /board`) responds within 500 ms with full-day dataset | Timed integration test | (Assumption) |
| NFR-3 | Security / Auth | All non-health endpoints require a valid bearer token; tokens encode role claim; role is validated server-side on every request | Automated tests asserting 401 on missing token, 403 on wrong role | JWT or API-key approach; decision in Open Questions |
| NFR-4 | Security / Data | No sensitive customer PII (phone, email, address) is logged in plaintext in application logs | Log-output review in test; grep for known seed PII strings | (Assumption) |
| NFR-5 | Availability | Service uptime ≥ 99 % during business hours (07:00–19:00 local) | Uptime monitor or health-check probe; alert on consecutive failures | (Assumption) |
| NFR-6 | Scalability | System must handle a roster of ≤ 50 technicians and ≤ 10,000 work orders without schema or query changes | Verified by load test and query EXPLAIN analysis | (Assumption — sized for small HVAC shop growth) |
| NFR-7 | Observability | All API requests are logged with: method, path, HTTP status, latency, and actor role (no PII in log line) | Structured log output reviewed in CI; no crashes on high volume | (Assumption) |
| NFR-8 | Observability | SLA breach count is surfaced as an application metric and increments correctly as time passes | Unit test asserting breach flag logic; integration test checking board response | |
| NFR-9 | Compliance / Data retention | Audit log entries are append-only; no API endpoint permits deletion or update of audit records | Automated test confirming DELETE/PATCH on audit entries returns 405/403 | |
| NFR-10 | Operability | Application starts with a single `docker compose up` or equivalent; seed script runs in ≤ 60 seconds on developer hardware | Manual verification during onboarding; CI smoke test | (Assumption) |
| NFR-11 | Operability | All environment-specific config (DB URL, secret key, port) is provided via environment variables; no hard-coded secrets in source | Static analysis / secret-scanning step in CI | (Assumption) |

---

## 7. Data & Integrations

### Core Entities

| Entity | Key Fields | Relationships |
|--------|-----------|---------------|
| `Customer` | id, full_name, phone, email (nullable), street, city, state, zip, created_at, deleted_at (soft delete) | Has many WorkOrders |
| `Technician` | id, name, skills (array/JSON), active (bool), created_at | Has many Assignments; has many AuditLog entries as actor |
| `User` | id, username, hashed_password, role (`dispatcher` / `technician` / `owner`), technician_id (FK, nullable — links User to Technician record) | Role drives RBAC |
| `WorkOrder` | id, customer_id (FK), description, priority (`routine` / `urgent`), scheduled_date, time_window (`morning` / `afternoon` / `all_day`), status, completion_notes (nullable), dispatcher_addendum (nullable), created_at, updated_at | Belongs to Customer; has one active Assignment; has many AuditLogs; has many Parts |
| `Assignment` | id, work_order_id (FK, unique), technician_id (FK), assigned_by (User FK), assigned_at, is_active (bool) | Unique constraint on `(work_order_id, is_active=true)` ensures one active assignment |
| `PartLineItem` | id, work_order_id (FK), name, quantity (int ≥ 1), unit_cost (decimal, nullable), created_at | Belongs to WorkOrder; immutable after completion |
| `AuditLog` | id, work_order_id (FK), from_status, to_status, actor_id (User FK), actor_role, changed_at (UTC) | Append-only |

### External Integrations

None in MVP scope. All data is internal to the application database.

### API Surface

- REST API served by FastAPI under `target-apps/field-service-dispatch/`
- OpenAPI schema auto-generated at `/docs` and `/redoc`
- `GET /health` — unauthenticated liveness check
- Resource prefixes: `/customers`, `/technicians`, `/work-orders`, `/assignments`, `/board`, `/audit-logs`

---

## 8. Analytics & Observability

**Logging**
- Structured JSON logs (INFO level default, DEBUG via env flag)
- Each log line includes: timestamp, level, method, path, status_code, duration_ms, actor_role (no actor_id in logs to reduce PII exposure)
- Errors include exception type and sanitized message; never raw SQL or stack traces in production log level

**Metrics (application-level)**
- `work_orders_by_status` — count of orders per status, refreshed on each board call
- `sla_breach_count_today` — count of urgent/overdue orders flagged on the board
- `assignments_today` — total assignments created for today's date

**Alerts (Assumption)**
- Health check failure → alert within 2 minutes (implementation depends on deployment environment; TBD in Open Questions)
- SLA breach count increases during business hours → surfaced on board UI (no automated external alert in MVP)

**Audit Trail**
- The `AuditLog` table itself serves as the primary observability record for order disputes
- Accessible to Dispatcher and Owner via `GET /work-orders/{id}/audit-log`

---

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Concurrent assignment race condition (two dispatchers assign simultaneously) | One order gets two active assignments, violating core business rule | Database-level unique constraint on `(work_order_id, is_active=true)` plus optimistic locking or DB transaction; integration test covers concurrent requests |
| SLA breach time logic is server-timezone-dependent | Breach flags fire at wrong local time if server clock differs from business location | Expose timezone as a configurable environment variable; document assumption; add unit tests for edge cases (midnight, DST) |
| Technician user–Technician roster link misconfigured | A technician user sees wrong jobs or can update jobs they don't own | `User.technician_id` FK is validated on login; integration tests assert correct scoping with mismatched IDs |
| Streamlit session state holding stale data | Dispatcher sees outdated board, misses new urgent jobs | Add explicit "Refresh" button and set a short auto-rerun interval (e.g. 30 s) in Streamlit; API is always source of truth |
| Scope creep from "parts list" into inventory management | MVP timeline at risk | PRD explicitly excludes stock depletion; parts capture is documentation only; enforce in backlog grooming |
| Demo seed data not matching demo script | Poor client demo outcome | Seed script is a required deliverable (FR-12); seed data verified by automated integration test before demo |
| Auth mechanism not decided early enough | Blocks all role-based test writing | Resolve auth approach in sprint 0 (see Open Questions #1) |

---

## 10. Open Questions

| # | Question | Suggested owner |
|---|----------|-----------------|
| 1 | What auth mechanism should be used for MVP — JWT (stateless) or session-based API keys? JWT preferred for multi-client support; confirm with team. | Tech lead |
| 2 | What is the canonical "end of business day" time for SLA breach evaluation — is 17:00 correct, and in which timezone? Should this be configurable per deployment? | Dana (client) / PM |
| 3 | Should technicians be able to reject or decline an assignment (e.g. `assigned → rejected` state), or is acceptance implicit once assigned? | Dana (client) |
| 4 | Is dispatcher addendum on a completed job a free-text append (immutable after each add) or an editable field? Clarify for audit integrity. | PM / Dana |
| 5 | Should cancellation require a reason/note, or is it always allowed without documentation from non-terminal states? | Dana (client) |
| 6 | Will multiple dispatchers operate simultaneously in production? If yes, concurrent-edit conflict UX in Streamlit needs definition. | Dana (client) |
| 7 | What is the deployment target — local Docker only, a managed PaaS, or a cloud VM? Affects NFR-5 (availability) and alerting strategy. | Tech lead / Dana |
| 8 | Should the Owner role have access to parts cost data, or is that sensitive to share with the owner vs. dispatcher level? | Dana (client) |
| 9 | Is the skills list for technicians a fixed enum or user-editable? Brief lists examples; confirm if Dispatcher can add new skill tags. | PM / Dana |
| 10 | Should the board default to "all active technicians" including those with no jobs today, or only technicians with at least one assignment? | Dana (client) |

---

## 11. Delivery & Client Surface

| Concern | Choice | Implementation notes |
|---------|--------|---------------------|
| Client UI | **Streamlit** | Dispatcher board, technician "My Jobs Today", Owner read-only board; all primary user journeys implemented in Streamlit per FR-11 |
| API | **FastAPI** under `target-apps/field-service-dispatch/` | REST + auto-generated OpenAPI at `/docs`; all business logic and enforcement lives here |
| UI location | `ui/streamlit_app.py` | HTTP client to FastAPI only — never imports from `app/` directly; uses `requests` or `httpx` to call the API |
| Auth for UI | Bearer token (JWT or API key, see Open Question #1) | Streamlit stores token in `st.session_state` after login; passed as `Authorization: Bearer <token>` header on all API calls |
| Board refresh | Streamlit `st.rerun` with configurable interval (default 30 s) + manual Refresh button | Prevents stale board state; interval configurable via env var |
| Output directory | `target-apps/field-service-dispatch/` | API app, models, routers, seed script all under this path |
| Seed script | `target-apps/field-service-dispatch/seed.py` | Idempotent; satisfies FR-12 demo data requirements |
| Health endpoint | `GET /health` — no auth required | Returns `{"status": "ok"}` with HTTP 200; used by uptime monitors |

---

## Appendix: Assumptions

- **Business hours / SLA cutoff**: SLA breach for urgent jobs is evaluated at 17:00 local server time. Timezone is assumed configurable via environment variable; default is UTC until confirmed (Open Question #2).
- **Database**: A relational database (e.g. PostgreSQL or SQLite for local dev) is used. Specific engine is TBD but schema design assumes SQL with FK constraints.
- **Single-shop deployment**: The system serves one HVAC shop (Dana's). No multi-tenancy is needed in MVP.
- **Technician–User mapping is 1:1**: Each technician in the field has exactly one system user account. A dispatcher or owner user does not have a corresponding technician record.
- **Skills are a predefined list**: `residential`, `commercial`, `install` are the initial values. Whether the list is user-extensible is deferred to Open Question #9; implementation should allow for extension.
- **Time windows are labels, not clock ranges**: `morning`, `afternoon`, `all-day` are informational only; no automated scheduling logic is applied based on them.
- **Parts costs are optional and informational**: There is no tax, markup, or invoice computation in MVP. Cost fields are for dispatcher/owner reference only.
- **Soft delete for customers**: Customers are soft-deleted (deleted_at timestamp) rather than hard-deleted to preserve work order history integrity.
- **Reassignment is only permitted in `assigned` state**: Once a job moves to `in_progress`, the technician cannot be swapped without cancelling and recreating the order. This is a conservative interpretation; see Open Question #3.
- **Auth tokens are short-lived** (e.g. 24-hour expiry): Appropriate for a same-day dispatch tool; no refresh token flow required in MVP.
- **NFR performance targets** (300 ms p95, 99 % uptime) are reasonable defaults for a single-shop internal tool and are not derived from explicit client SLAs.
- **No email or push notifications**: All communication remains in-app; no outbound notification infrastructure is built in MVP.
- **Streamlit "login"** is implemented as a token/credential entry form that retrieves a bearer token from the API's auth endpoint; full SSO or LDAP is out of scope.
