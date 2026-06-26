# Field Service Dispatch — Product Requirements Document

## 1. Overview

Dana's HVAC shop operates with 15 field technicians whose daily coordination relies on a physical whiteboard and group text messages. This creates blind spots around technician workload, SLA compliance, and a verifiable audit trail — problems that compound as the business grows. A lightweight, purpose-built office tool is needed to replace ad-hoc dispatch with structured workflow, without the overhead or cost of enterprise CRM platforms like Salesforce.

The proposed solution is a role-aware web application backed by a FastAPI REST service and a Streamlit dispatcher interface. It centralises customer records, work orders, technician rosters, and daily assignments into a single source of truth. A visual "today's board" gives dispatchers a column-per-technician layout with an unassigned queue and highlighted SLA breaches; technicians get a focused "my jobs" view with inline status actions; and the owner gets read-only dashboard visibility into workload and compliance.

The MVP scope is deliberately narrow: dispatch workflow, SLA flagging for urgent same-day jobs, completion notes with parts capture, and a full status-change audit history. GPS tracking, customer-facing notifications, payments, and inventory management are explicitly excluded.

---

## 2. Goals & Success Metrics

| Goal | Metric | Target | Notes |
|------|--------|--------|-------|
| Replace whiteboard dispatch | % of work orders created and tracked in system | 100 % of daily orders in system within first week of go-live | Baseline is zero digital tracking today |
| Dispatcher efficiency | Time to assign or reassign a work order | < 30 seconds from board view | Measured via user observation |
| SLA visibility | Breached urgent SLAs surfaced on today's board | 100 % of same-day breaches visible in real time | Breach = urgent job not completed by end of scheduled date |
| Technician adoption | Technicians updating job status themselves | ≥ 80 % of status changes made by assigned technician (not dispatcher override) | Reduces dispatcher interrupt load |
| Audit completeness | Status-change history available for every work order | Every state transition has actor + timestamp recorded | Zero gaps acceptable at launch |
| Data quality at completion | Completion notes captured on every closed job | 100 % of completed work orders have non-empty notes | Enforced by API validation |

---

## 3. Non-Goals / Out of Scope

- GPS or real-time location tracking of technicians
- Automated SMS or email notifications to customers
- Payment processing or invoice generation
- Inventory stock-level management or depletion tracking
- Customer self-service portal
- Mobile native application (iOS / Android)
- Integration with third-party scheduling or ERP systems
- Recurring maintenance scheduling / subscription contracts
- Multi-branch or multi-company tenancy

---

## 4. Users & Use Cases

| Persona | Need | Primary use case |
|---------|------|-----------------|
| Dispatcher (Dana and staff) | Create and manage work orders, assign and reassign technicians, view today's board, cancel orders | Open the day's board; drag or select a technician for each unassigned order; monitor SLA breach highlights; reschedule or cancel jobs as needed |
| Technician | See only their assigned jobs for today, advance job status, add parts and completion notes | Log in, view "my jobs" list, tap In Progress when on-site, add parts used, submit completion notes to close job |
| Owner | Monitor overall workload, SLA compliance, technician utilisation without making changes | View today's board and workload summary in read-only mode; review historical order list and audit trails |
| Public / Unauthenticated | Confirm service availability | Call `/health` endpoint to verify the API is running; no other access granted |

---

## 5. Functional Requirements

| ID | Description | Priority | Acceptance criteria (Given / When / Then) |
|----|-------------|----------|-------------------------------------------|
| FR-1 | **Customer records** — The system shall allow a Dispatcher to create, view, edit, and soft-delete customer records containing: full name, primary phone, email (optional), and one or more service addresses (street, city, state/province, postal code). | P0 | **Given** a logged-in Dispatcher, **When** they submit a valid customer creation form with name, phone, and at least one service address, **Then** the customer is persisted, returned with a unique ID, and visible in the customer list. **Given** a missing required field, **Then** the API returns HTTP 422 with a field-level error. |
| FR-2 | **Work order lifecycle** — The system shall support work orders with fields: linked customer, description (free text), priority (`routine` or `urgent`), scheduled date, time window (`morning`, `afternoon`, `all_day`), and status progressing through the state machine: `new → assigned → in_progress → completed` or `new/assigned/in_progress → cancelled`. Only a Dispatcher may create, reschedule, or cancel a work order. | P0 | **Given** a Dispatcher, **When** they create a work order with all required fields, **Then** it is persisted with status `new`. **Given** a completed work order, **When** any actor attempts to cancel it, **Then** the API returns HTTP 409. **Given** a non-terminal work order, **When** a Dispatcher cancels it, **Then** status transitions to `cancelled` and a history record is written. |
| FR-3 | **Technician roster** — The system shall maintain a roster of technicians with: display name, skill tags (multi-select from a defined set, e.g. `residential`, `commercial`, `install`, `refrigeration`), and an `active` boolean flag. Only active technicians may be assigned to work orders. | P0 | **Given** a Dispatcher, **When** they attempt to assign an inactive technician to a work order, **Then** the API returns HTTP 422 with message "Technician is not active". **Given** an active technician, **When** retrieved via roster endpoint, **Then** their skills list and active status are included in the response. |
| FR-4 | **Assignment — one active assignment per order** — A Dispatcher may assign exactly one active technician to a work order in a dispatchable state (`new` only at time of first assignment). Reassignment is permitted if the order is in `assigned` state; the system shall record the reassignment in audit history. | P0 | **Given** a work order in `new` state and an active technician, **When** a Dispatcher posts an assignment, **Then** status transitions to `assigned`, technician is linked, and an audit record is written. **Given** a work order already in `in_progress` state, **When** an assignment attempt is made, **Then** the API returns HTTP 409. **Given** an assigned order, **When** a Dispatcher reassigns to a different active technician, **Then** the previous assignment is replaced, status remains `assigned`, and both old and new technician IDs appear in audit history. |
| FR-5 | **Technician status updates — own jobs only** — A Technician may advance the status of a work order only if it is currently assigned to them. Permitted transitions for a Technician: `assigned → in_progress`, `in_progress → completed`. A Technician may not modify orders assigned to another technician. | P0 | **Given** a Technician authenticated as Tech A, **When** they attempt to update status on an order assigned to Tech B, **Then** the API returns HTTP 403. **Given** an order assigned to the authenticated Technician in `assigned` state, **When** they POST a status transition to `in_progress`, **Then** status updates and an audit record is written with the technician's identity and timestamp. |
| FR-6 | **Completion — notes required, parts optional** — When a Technician transitions a work order to `completed`, the request must include non-empty completion notes. Optionally, one or more parts may be recorded (part name, quantity as positive integer, optional unit cost). | P0 | **Given** a Technician submitting a completion request with an empty or absent `completion_notes` field, **Then** the API returns HTTP 422 with message "Completion notes are required". **Given** a valid completion request with notes and at least one part entry, **Then** the work order status becomes `completed`, notes are persisted, and all part line items are stored linked to the order. **Given** a valid completion request with notes and no parts, **Then** the work order completes successfully. |
| FR-7 | **Today's dispatch board** — The system shall expose a board view for a given date (defaulting to today) containing: (a) an unassigned queue of work orders with no technician, (b) per-technician columns listing their assigned orders with current status, and (c) a list of SLA-breached urgent orders (urgent orders whose scheduled date is on or before today and status is not `completed` or `cancelled` when the server time is past the end of the business day threshold). | P0 | **Given** a request to the board endpoint for today's date, **When** the response is returned, **Then** it contains `unassigned`, `technician_columns` (keyed by technician ID), and `sla_breaches` arrays. **Given** an urgent order scheduled for yesterday with status `assigned`, **Then** it appears in `sla_breaches`. **Given** a routine order past its scheduled date, **Then** it does not appear in `sla_breaches`. |
| FR-8 | **Audit / status-change history** — Every state transition on a work order (including creation, assignment, reassignment, status changes, cancellation, and completion) shall be recorded with: work order ID, actor identity, previous status, new status, timestamp (UTC), and an optional context note. | P0 | **Given** any state change is committed on a work order, **When** the history endpoint for that order is queried, **Then** the new record appears with correct actor, timestamps, and status values. **Given** a work order with five state changes, **Then** five history records are returned in chronological order. |
| FR-9 | **Owner read-only access** — Users authenticated with the Owner role shall have GET access to all board, work order, customer, technician, and history endpoints. Owner role requests to any mutating endpoint (POST/PUT/PATCH/DELETE on business resources) shall be rejected. | P1 | **Given** an Owner-authenticated user, **When** they call any list or detail GET endpoint, **Then** a 200 response is returned with full data. **Given** an Owner-authenticated user, **When** they attempt to POST a new work order, **Then** the API returns HTTP 403. |
| FR-10 | **Workload summary** — The system shall provide an endpoint returning, for a given date, each active technician's job count by status and a flag if any of their jobs are SLA-breached urgents, to support the "who is overloaded today" use case. | P1 | **Given** a request to the workload endpoint for today, **Then** each active technician in the response includes fields: `total_assigned`, `in_progress_count`, `completed_count`, `sla_breach_flag`. **Given** a technician with no orders today, **Then** their counts are all zero and `sla_breach_flag` is false. |
| FR-11 | **Dispatcher addendum after completion** — A Dispatcher may append an addendum note to a completed work order's notes field without changing any other order data or status. No other field modifications are permitted on completed orders. | P1 | **Given** a completed work order, **When** a Dispatcher PATCHes the addendum field with non-empty text, **Then** the text is appended (not replaced) and an audit record is written. **Given** a Dispatcher attempts to change the status or technician on a completed order, **Then** the API returns HTTP 409. |
| FR-12 | **Streamlit dispatcher UI** — A Streamlit application shall implement the primary dispatcher user journeys: login with credential entry, today's board display with unassigned queue and per-technician columns, SLA breach highlight, work order creation form, assignment/reassignment controls, and status overview. The Streamlit app shall communicate exclusively via the REST API and shall not import application modules directly. | P0 | **Given** a Dispatcher logs in via the Streamlit UI, **When** credentials are valid, **Then** a JWT token is stored in session state and the board view renders. **Given** an SLA-breached urgent order exists, **When** the board is displayed, **Then** that order is visually distinguished (e.g. red highlight or badge). **Given** the Streamlit app is running, **Then** all data mutations are made via HTTP calls to the FastAPI backend — no direct DB or module imports. |
| FR-13 | **Technician UI — My Jobs** — The Streamlit application shall provide a Technician view showing only orders assigned to the logged-in technician for the current date, with inline controls to advance status and, on active jobs, a form to add parts and enter completion notes. | P0 | **Given** a Technician logs in, **Then** only orders assigned to their technician ID are visible. **Given** an assigned order, **When** the technician clicks "Start Job", **Then** an API call transitions the order to `in_progress` and the UI refreshes. **Given** an in-progress order, **When** the technician submits completion notes (non-empty) and optional parts, **Then** the order transitions to `completed` and the form is replaced with a completion summary. |
| FR-14 | **Seed / demo data** — The application shall include a seed script that populates: ≥ 5 technicians with varied skills and active flags, ≥ 8 customers, ≥ 15 work orders across all statuses (including at least one SLA-breached urgent, at least two completed orders with parts, and a mix of assigned/unassigned), and assignment records consistent with business rules. | P1 | **Given** the seed script is executed against a clean database, **Then** the database contains the minimum entity counts above and at least one work order in `sla_breaches` when the board endpoint is called for today or a configured demo date. |
| FR-15 | **Health check endpoint** — The API shall expose a public `GET /health` endpoint returning service status without authentication. | P0 | **Given** an unauthenticated HTTP client, **When** it calls `GET /health`, **Then** the response is HTTP 200 with a JSON body indicating service status (e.g. `{"status": "ok"}`). |

---

## 6. Non-Functional Requirements

| ID | Category | Target | Measurement / verification | Notes |
|----|----------|--------|---------------------------|-------|
| NFR-1 | Performance | p95 API response latency ≤ 300 ms for board and list endpoints under normal load | Load test with 20 concurrent users; measure p95 via request logs | (Assumption) — target appropriate for a 15-tech shop with low concurrency |
| NFR-2 | Performance | Streamlit board page initial render ≤ 3 seconds on local network | Manual timing on demo hardware | (Assumption) |
| NFR-3 | Security / Auth | All non-health endpoints require a valid JWT Bearer token; tokens expire after 8 hours | Automated test: call protected endpoint without token → expect HTTP 401; call with expired token → expect HTTP 401 | (Assumption) JWT; expiry duration is configurable |
| NFR-4 | Security / Auth | Role-based access control enforced at API layer: Dispatcher, Technician, Owner roles with permissions as per FR-4 through FR-11 | Integration tests covering each role attempting each action class; forbidden actions return HTTP 403 | |
| NFR-5 | Security / Privacy | No customer PII stored beyond name, phone, email, and service address; no payment card or government ID data collected | Code review and data model inspection | Aligns with out-of-scope for payments |
| NFR-6 | Availability | API uptime ≥ 99 % during business hours (defined as 07:00–19:00 local time, Mon–Sat) | Uptime monitoring with synthetic health-check probe every 60 seconds | (Assumption) business hours window |
| NFR-7 | Scalability | System supports ≥ 30 concurrent authenticated users without degradation beyond NFR-1 targets | Load test simulation | (Assumption) growth headroom beyond current 15-tech shop |
| NFR-8 | Observability | Structured JSON logs emitted for every API request: method, path, response status, latency ms, actor role (no PII in logs) | Review log output in staging; confirm JSON parseable and role field present | (Assumption) |
| NFR-9 | Observability | Application emits an alertable metric / log line whenever an SLA breach is newly detected at board-refresh time | Inspect logs after seeding a breached order and calling board endpoint | |
| NFR-10 | Compliance / Data retention | Audit history records (FR-8) are immutable — no delete or update API for history rows; retained for minimum 2 years | Code review: confirm no DELETE/PUT on history table; DB backup policy documented | (Assumption) 2-year retention; confirm with Dana |
| NFR-11 | Operability | Application is containerisable via a single `docker compose up` command for local development and demo | Verify `docker compose up` from clean checkout produces running API + UI with seed data | (Assumption) Docker Compose for demo environment |
| NFR-12 | Operability | All configuration (DB URL, JWT secret, port, SLA breach threshold hour) supplied via environment variables; no secrets committed to repository | `git grep` for hardcoded secrets returns no results; `.env.example` provided | |

---

## 7. Data & Integrations

### Core Entities

| Entity | Key Attributes |
|--------|---------------|
| Customer | `id`, `full_name`, `phone`, `email?`, `service_addresses[]` (street, city, state, postal_code), `created_at`, `is_active` |
| WorkOrder | `id`, `customer_id`, `description`, `priority` (routine/urgent), `scheduled_date`, `time_window` (morning/afternoon/all_day), `status`, `assigned_technician_id?`, `completion_notes?`, `created_at`, `updated_at` |
| WorkOrderPart | `id`, `work_order_id`, `part_name`, `quantity`, `unit_cost?` |
| Technician | `id`, `display_name`, `skills[]`, `is_active`, `user_id` (FK to auth user) |
| StatusHistory | `id`, `work_order_id`, `actor_user_id`, `actor_role`, `previous_status`, `new_status`, `context_note?`, `changed_at` |
| User | `id`, `username`, `hashed_password`, `role` (dispatcher/technician/owner), `technician_id?` |

### State Machine

```
new ──assign──► assigned ──tech start──► in_progress ──tech complete──► completed
 │                │                          │
 └──cancel──► cancelled ◄──cancel────────────┘
```

### External Integrations

- **None at MVP.** All data is internal to the application database.
- TBD: If email notifications are added in a future phase, an SMTP or transactional email provider would be required (out of scope).
- TBD: Authentication provider — self-contained username/password with JWT is assumed (see Assumptions). No OAuth/SSO at MVP.

### API Surface

- REST API under `target-apps/field-service-dispatch/app/`
- OpenAPI/Swagger docs auto-generated by FastAPI at `/docs`
- Key route groups: `/auth`, `/customers`, `/work-orders`, `/technicians`, `/board`, `/workload`, `/health`

---

## 8. Analytics & Observability

**Logging**
- Structured JSON logs (stdout) for every HTTP request: timestamp, method, path, status code, latency_ms, user_id (hashed or opaque), role. No raw PII in log lines.
- Application-level log entries for: SLA breach detected (work_order_id, scheduled_date, current_time), assignment made/changed (order_id, old_tech, new_tech), status transition (order_id, old, new, actor).

**Key Operational Metrics** *(to be wired into a monitoring tool in a later phase; at MVP, derivable from logs)*
- `work_orders_created_total` — counter by priority
- `work_orders_completed_total` — counter by priority
- `sla_breaches_active` — gauge: count of urgent orders past scheduled date and not completed
- `board_requests_total` and `board_latency_p95` — request-level metrics

**Alerts** *(recommended, implementation deferred post-MVP)*
- SLA breach count > 0 for more than 30 minutes during business hours → notify dispatcher channel
- API error rate (5xx) > 1 % over 5-minute window → page on-call

**Demo / Seed Observability**
- Seed script logs entity counts on completion so demo setup is verifiable at a glance.

---

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Technician adoption — techs may prefer group text over logging into a new app | Low utilisation undermines the product's value proposition | Keep the Technician UI to a single screen with minimal steps; dispatcher can fall back to updating status on behalf of techs as a transition measure |
| SLA breach logic depends on server clock and business-hours definition | Incorrect breach flagging erodes trust in the board | Make the breach-threshold hour (e.g. 17:00) configurable via environment variable; include unit tests with fixed timestamps |
| Single active assignment rule creates dispatch bottleneck if reassignment UX is clunky | Dispatcher works around the system | Reassignment must be a single-action operation on the board; test with Dana in a UAT session before go-live |
| Status-history immutability vs. database migration needs | History rows cannot be corrected if seeded incorrectly | Seed script is idempotent and separate from migration scripts; history table has no update/delete routes |
| Scope creep toward SMS / payments during build | MVP delayed | Non-goals section agreed with Dana before development starts; change requests logged separately |
| Demo data date alignment | Breached SLA orders may not appear breached if demo is run on a future date | Seed script accepts a configurable `DEMO_DATE` so the "today" reference stays meaningful |
| Data loss on restart in local dev (SQLite default) | Repeated re-seeding slows demos | Default to a persisted volume in Docker Compose; document DB reset procedure |

---

## 10. Open Questions

| # | Question | Suggested owner |
|---|----------|-----------------|
| 1 | What is the exact business-hours end time that triggers an SLA breach flag for urgent orders — e.g. 17:00, 18:00, or end of the scheduled time window? | Dana (Product owner) |
| 2 | Should the Owner role be able to see individual technician phone numbers / personal details, or only job-level data? | Dana |
| 3 | Is the "dispatcher" a single user or multiple staff members sharing a role? Are there any per-dispatcher restrictions? | Dana |
| 4 | What skill taxonomy should be pre-seeded — should skills be a fixed enum or free-form tags that dispatchers can define? | Dana / Dev lead |
| 5 | Are work orders ever multi-day (e.g. a large commercial install spanning two days), or is one work order always one scheduled date? | Dana |
| 6 | What database engine should be used for production (PostgreSQL assumed)? Is a managed cloud DB available or self-hosted? | Infrastructure owner |
| 7 | Should the "completed jobs locked except addendum" rule also lock the parts list, or can a dispatcher amend parts post-completion? | Dana |
| 8 | Is there a requirement to export or print the day's board (e.g. PDF or CSV) for offline reference? | Dana |
| 9 | What is the intended deployment environment — local server at Dana's office, a cloud VPS, or a managed PaaS? | Infrastructure owner |
| 10 | Should reassignment trigger any visible notification to the newly assigned technician within the UI (e.g. a banner on next load)? | Dana / UX |
| 11 | Is a 2-year audit history retention period acceptable, or does the business have a shorter/longer requirement? | Dana / Legal (if applicable) |
| 12 | Are there any existing customer records (e.g. in a spreadsheet) that need to be imported at launch? | Dana |

---

## 11. Delivery & Client Surface

| Concern | Choice | Implementation notes |
|---------|--------|----------------------|
| Client UI | **Streamlit** | Dispatcher board, technician my-jobs view, and owner read-only dashboard implemented as a Streamlit multi-page app |
| API | **FastAPI** under `target-apps/field-service-dispatch/` | REST + OpenAPI; auto-generated Swagger UI at `/docs`; all business logic and DB access lives here |
| UI location | `target-apps/field-service-dispatch/ui/streamlit_app.py` (with sub-pages in `ui/pages/`) | Streamlit app communicates with the API via HTTP only — **never** imports `app/` modules directly |
| Auth for UI | JWT Bearer token (username + password login) | Streamlit stores JWT in `st.session_state`; token sent as `Authorization: Bearer <token>` header on every API call; 8-hour expiry (configurable) |
| Role routing in UI | Post-login redirect based on `role` field in JWT claims | Dispatcher → board view; Technician → my-jobs view; Owner → read-only board/workload view |
| DB (default) | SQLite for local dev / Docker Compose demo; PostgreSQL for production | DB URL supplied via `DATABASE_URL` env var; SQLAlchemy ORM for portability |
| Seed data | `target-apps/field-service-dispatch/scripts/seed.py` | Idempotent; accepts `DEMO_DATE` env var for SLA breach alignment; logs entity counts on completion |
| Container setup | `docker-compose.yml` at repo root of the target app | Services: `api` (FastAPI + Uvicorn), `ui` (Streamlit), optional `db` (Postgres); `docker compose up` starts all three |
| OpenAPI spec | Auto-generated at `GET /openapi.json` | Can be used to generate client stubs if a future native mobile app is scoped |

---

## Appendix: Assumptions

- **Authentication** is self-contained username/password with JWT; no external OAuth, SSO, or LDAP provider is assumed for MVP.
- **JWT expiry** is 8 hours, aligned with a typical dispatcher shift; this is configurable via environment variable.
- **Database** defaults to SQLite for development/demo and PostgreSQL for production; the ORM abstraction (SQLAlchemy) supports both.
- **SLA breach threshold** is assumed to be end-of-business-day (e.g. 17:00 local time) unless Dana specifies otherwise; this value is externalised as a config variable.
- **Skills** are treated as a pre-defined set of string tags (e.g. `residential`, `commercial`, `install`, `refrigeration`) at MVP; the exact list is to be confirmed with Dana (Open Question 4).
- **One work order = one scheduled date**; multi-day orders are out of scope for MVP pending confirmation (Open Question 5).
- **Parts unit cost** is optional and not aggregated into any invoice or payment workflow at MVP.
- **"Dispatcher addendum"** appends to the existing completion notes string (e.g. with a timestamp prefix) rather than replacing it; exact format TBD during implementation.
- **Completed orders lock the parts list** as well as other fields; a dispatcher addendum only touches the notes field (Open Question 7 flagged for confirmation).
- **Workload** considers only orders with `scheduled_date = today`; historical overdue orders are not counted in the daily workload summary.
- **Active flag** on Technician defaults to `true` on creation; an inactive technician's existing completed orders remain visible in history.
- **Reassignment** is only permitted when the order is in `assigned` state (not `in_progress`); a dispatcher must first take a manual step to revert to `assigned` if a job is already in progress — this business rule is an assumption and should be confirmed.
- **Owner role** does not correspond to a Technician record; it is a standalone user role.
- **No rate limiting** is implemented at MVP given the small user base (≤ 20 users); recommended for production hardening.
- **Uptime SLA** of 99 % during business hours is an internal engineering target, not a contractual obligation to customers at this stage.
- **Streamlit** is the UI framework; "or equivalent" in the brief is resolved to Streamlit for implementation consistency.
- **Demo date** in the seed script defaults to the current date at seed-run time; a `DEMO_DATE` environment variable overrides it to keep SLA breaches visible on a fixed date.
