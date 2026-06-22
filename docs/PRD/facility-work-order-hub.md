# Facility Work Order Hub — PRD

## 1. Overview

Jordan, a facilities manager responsible for a multi-site office portfolio, faces a fragmented maintenance workflow: tenants report issues informally via email and whiteboards, technicians coordinate through a shared spreadsheet, and leadership receives unreliable monthly summary counts. The result is missed SLAs, wasted technician time, and eroded trust in operational data.

The Facility Work Order Hub replaces this patchwork with a single, role-gated web application. Employees file structured work orders; technicians see their personal queues and advance job status; facilities administrators triage, assign, and close all orders while managing the site/location catalog; and leadership accesses read-only aggregate dashboards with live overdue counts and average closure times. Every status transition is timestamped to create a reliable audit trail.

The MVP is delivered as a FastAPI backend (REST + OpenAPI) under `target-apps/facility-work-order-hub/` with a Streamlit front-end that consumes the API exclusively over HTTP. Authentication uses JWT bearer tokens issued at login. A realistic seed dataset spanning 60 days ensures the product is demo-ready on first launch.

---

## 2. Goals & Success Metrics

| Goal | Metric | Target | Notes |
|------|--------|--------|-------|
| Eliminate spreadsheet-based assignment tracking | % of active work orders managed in the hub | 100 % of new orders at go-live | Baseline is 0 % |
| Reduce admin time spent building monthly reports | Time to produce overdue-by-site report | < 30 seconds via dashboard | Currently manual, hours of effort |
| Achieve reliable SLA visibility | Overdue flag accuracy on dashboard | 100 % match between due-by timestamp and overdue badge | Verified by automated test |
| Reduce average days-to-close for urgent orders | Avg days-to-close for priority = urgent | Tracked from day 1; target set after 30-day baseline | (Assumption) |
| Ensure audit trail completeness | % of status transitions with recorded timestamp | 100 % — enforced at DB layer | Verified by integration test |
| Demonstrate system readiness | Seed data covers all statuses, 2 overdue, 1 reopened | Passes seed-data acceptance test in CI | Per brief spec |

---

## 3. Non-Goals / Out of Scope

- SSO / OAuth / SAML identity providers; login is email + password (JWT) only
- Mobile native application (iOS / Android)
- Photo or file attachments on work orders or comments
- Parts inventory management or vendor billing workflows
- Email, SMS, or push notifications of any kind — SLA alerts are in-app only
- Geographic maps or IoT sensor ingestion
- Multi-tenant property management (billing, lease management)
- Fine-grained per-room ACL beyond the four defined roles
- Comment editing or deletion after submission (immutable in MVP)
- Public-facing work order submission portal (all submitters must be authenticated)

---

## 4. Users & Use Cases

| Persona | Need | Primary use case |
|---------|------|------------------|
| Employee (Requester) | Report a maintenance issue and track its progress | Submit a work order with title, category, priority, and location; follow status updates and comment on own orders |
| Technician | Know exactly what jobs are assigned and move them forward | View personal assigned queue; transition status assigned → in_progress → completed; add comments |
| Facilities Administrator | Full control over the work order lifecycle and site catalog | Triage all submitted orders; assign/reassign technicians; edit any field; force-close orders; manage sites and locations; view technician workload |
| Leadership (Read-only) | Trust the numbers without manual extraction | View org-wide SLA dashboard: open vs. closed this month, overdue count, avg days-to-close by category, top sites by volume |
| Public / Unauthenticated | Confirm the service is running | Hit `/health` endpoint only; zero access to business data |

---

## 5. Functional Requirements

| ID | Description | Priority | Acceptance criteria (Given / When / Then) |
|----|-------------|----------|--------------------------------------------|
| FR-1 | **User authentication (JWT)** — The system issues a JWT access token on successful email + password login. All non-health endpoints reject requests without a valid token. | P0 | Given a registered user with correct credentials, when POST `/auth/token` is called, then a JWT is returned (HTTP 200) and subsequent requests using that token as `Authorization: Bearer` succeed; given an invalid password, then HTTP 401 is returned. |
| FR-2 | **Role-based access control** — Four roles enforced on every API route: `requester`, `technician`, `facilities_admin`, `leadership`. Permissions follow the business rules in the brief. | P0 | Given a requester token, when they attempt to assign a technician to a work order, then HTTP 403 is returned. Given an admin token on the same endpoint, then HTTP 200 is returned. |
| FR-3 | **Site catalog management** — Facilities admin can create, read, update (including toggle `active` flag), and list sites (site code, name, address, active flag). Only active sites accept new work orders. | P0 | Given an admin token, when POST `/sites` is called with valid fields, then the site is persisted and returned (HTTP 201). Given a requester token, when POST `/sites` is called, then HTTP 403. Given an inactive site ID, when a new work order references it, then HTTP 422 with a clear error message. |
| FR-4 | **Location catalog management** — Facilities admin can create, read, update, and list locations within a site (floor, optional room/area label, site FK). Locations belong to exactly one site. | P0 | Given an admin token, when POST `/sites/{site_id}/locations` is called with valid data, then the location is persisted (HTTP 201). Given a non-admin token, then HTTP 403. |
| FR-5 | **Work order creation** — Authenticated users with role `requester` or `facilities_admin` can create a work order supplying: title, description, category (HVAC \| plumbing \| electrical \| access \| general), priority (low \| normal \| urgent), site_id, optional location_id, optional due_by. Initial status is always `submitted`. Created timestamp is server-set. | P0 | Given a requester token and valid payload referencing an active site, when POST `/work-orders` is called, then the order is created with status `submitted`, `created_at` set server-side, and HTTP 201 returned. Given `due_by` earlier than `created_at`, then HTTP 422. Given an inactive site_id, then HTTP 422. |
| FR-6 | **Work order status lifecycle** — Status transitions follow the defined lifecycle: submitted → triaged → assigned → in_progress → completed → closed. Reopen (closed → in_progress) is allowed with a required reason field. Only facilities admin may force-close (skip to closed from any state). Technician may only move their own assigned orders from assigned → in_progress → completed. | P0 | Given a technician token for order assigned to them, when PATCH `/work-orders/{id}/status` with `in_progress` is called, then HTTP 200. Given the same token attempting `closed`, then HTTP 403. Given an admin token with `force_close=true`, then HTTP 200 from any state. Given a reopen request without a reason string, then HTTP 422. |
| FR-7 | **Work order assignment** — Facilities admin assigns or reassigns a technician to a work order; this transitions status from `triaged` to `assigned` and sets the `assigned_at` timestamp. Technicians cannot reassign work. | P0 | Given an admin token, when PATCH `/work-orders/{id}/assign` with a valid technician user_id, then status becomes `assigned`, `assigned_at` is set, and HTTP 200 is returned. Given a technician token on the same endpoint, then HTTP 403. |
| FR-8 | **Work order read access scoping** — Requesters retrieve only their own work orders. Technicians retrieve only their assigned work orders. Admins and leadership retrieve all work orders. List endpoints are paginated (page + page_size) and default-sorted newest `created_at` first. | P0 | Given a requester token, when GET `/work-orders` is called, then only orders where `requester_id` matches the caller are returned. Given 25 records and default page_size=20, then two pages exist and page 1 has 20 records. |
| FR-9 | **Comments thread** — Any user with read access to a work order (requester on own order, assigned technician, any admin, leadership) may POST a comment (author, body, created_at). Comments are immutable after creation (no edit/delete). Leadership comment author is surfaced as display name only (no raw PII). | P1 | Given a requester token for their own order, when POST `/work-orders/{id}/comments` is called with a non-empty body, then HTTP 201 and comment stored. Given the same token on another user's order, then HTTP 403. Given any token attempting DELETE `/work-orders/{id}/comments/{comment_id}`, then HTTP 405. |
| FR-10 | **SLA overdue flagging** — The API marks a work order as overdue when `due_by` is set, `due_by < now()`, and status is not `closed`. The work order list and detail responses include an `is_overdue` boolean. Urgent priority without a `due_by` returns a `warnings: ["urgent orders suggest due_by within 24h"]` field on create (non-blocking). | P0 | Given a work order with `due_by` 1 hour in the past and status `in_progress`, when GET `/work-orders/{id}` is called, then `is_overdue: true` is in the response. Given status `closed`, then `is_overdue: false`. Given urgent priority and no `due_by` on create, then HTTP 201 with a `warnings` field present. |
| FR-11 | **Leadership SLA dashboard** — Read-only aggregated endpoint returning: open vs. closed count this calendar month, overdue count (all sites), average days-to-close by category, top-N sites by total volume. | P0 | Given a leadership token, when GET `/dashboard/sla` is called, then HTTP 200 with all four aggregate fields populated. Given a requester token, then HTTP 403. |
| FR-12 | **Technician workload view** — Admin-only endpoint returning each technician's count of work orders in status `assigned` or `in_progress`. | P1 | Given an admin token, when GET `/dashboard/workload` is called, then HTTP 200 with a list of `{technician_id, display_name, open_count}`. Given a non-admin token, then HTTP 403. |
| FR-13 | **Audit timestamp trail** — Work orders store server-set timestamps for: `created_at`, `updated_at`, `assigned_at`, `started_at` (in_progress), `completed_at`, `closed_at`. Each is null until the corresponding transition occurs. | P0 | Given an order that moves through the full lifecycle, when GET `/work-orders/{id}` is called after closing, then all six timestamp fields are non-null. Given an order that is never assigned, then `assigned_at` is null. |
| FR-14 | **Seed data** — A seed script populates: ≥ 3 active sites with 2–3 locations each; ≥ 8 work orders across all statuses including 2 overdue and 1 reopened; comment threads on ≥ 4 orders; 6 users (2 requesters, 2 technicians, 1 admin, 1 leadership) with a single documented dev password; timestamps spread realistically over 60 days. | P0 | Given a fresh database, when the seed script runs, then all assertions above are verifiable by a smoke-test query; dev password documented in a SQL comment in the seed file. |
| FR-15 | **Streamlit role-gated UI** — The Streamlit app reads the JWT from session state and renders role-appropriate views: Requester (submit form, my orders table with status timeline); Technician (my queue, status buttons, comment box); Facilities Admin (triage board, assign dropdown, sites/locations CRUD, workload panel); Leadership (read-only dashboard charts/tables). The Streamlit layer calls the FastAPI backend exclusively over HTTP and never imports from `app/`. | P1 | Given a logged-in requester, the Streamlit UI shows only the submit form and own-orders table and no admin controls are visible. Given a leadership user, no write controls are rendered. Given an expired token, the UI redirects to the login page. |
| FR-16 | **Health check endpoint** — `GET /health` returns `{"status": "ok"}` with HTTP 200 and requires no authentication. | P0 | Given no Authorization header, when GET `/health` is called, then HTTP 200 and body `{"status": "ok"}`. |

---

## 6. Non-Functional Requirements

| ID | Category | Target | Measurement / verification | Notes |
|----|----------|--------|---------------------------|-------|
| NFR-1 | Performance | p95 API response time ≤ 500 ms for list endpoints under typical load | Load test with k6 or locust at 50 concurrent users; assert p95 in CI | (Assumption) typical load defined as ≤ 50 concurrent users |
| NFR-2 | Performance | p99 response time ≤ 200 ms for single-resource GET endpoints | Same load test suite | (Assumption) |
| NFR-3 | Security / Auth | Passwords stored as bcrypt hashes (cost factor ≥ 12); plaintext never logged or returned | Code review + unit test asserting `bcrypt.verify` round-trips; grep CI step for password in logs | (Assumption) bcrypt; alternative argon2 acceptable |
| NFR-4 | Security / Auth | JWT tokens expire after configurable TTL (default 60 min); secret key loaded from environment variable, not hard-coded | Unit test for expiry rejection; CI lint step asserting no secret in source files | (Assumption) 60-min default |
| NFR-5 | Security / Privacy | Leadership role receives display-name-only for comment authors; no email or internal user ID exposed in comment payloads to leadership | Integration test: leadership GET `/work-orders/{id}/comments` response must not include `email` or `user_id` fields | Per brief requirement |
| NFR-6 | Availability | Service restarts cleanly within 30 s after crash; suitable for single-instance local/demo deployment | Manual smoke test; Docker `restart: unless-stopped` policy documented | (Assumption) no HA cluster required for MVP |
| NFR-7 | Scalability | Database schema uses indexed foreign keys on `work_orders(site_id)`, `work_orders(assignee_id)`, `work_orders(status)`, `work_orders(due_by)` to support dashboard aggregations | `EXPLAIN` output reviewed in PR; migration files checked in | (Assumption) PostgreSQL or SQLite acceptable for MVP |
| NFR-8 | Observability | All HTTP requests logged with method, path, status code, and duration; all unhandled exceptions logged with stack trace | Structured log output visible in `docker compose logs`; manual verification | (Assumption) stdlib logging or structlog |
| NFR-9 | Compliance / Data retention | All status-transition timestamps are immutable once set at the DB layer (no application-level overwrite path) | Integration test: attempt to PATCH `created_at` or `assigned_at` directly → HTTP 422 or field ignored | Per audit trail requirement |
| NFR-10 | Operability | Local dev documented: `uvicorn app.main:app --reload --reload-dir app --reload-dir schemas` to avoid `.venv` reload storms; README covers seed, migration, and Streamlit startup | README peer-review checklist item; developer smoke-test on clean checkout | Per brief requirement |

---

## 7. Data & Integrations

### Core Entities

| Entity | Key Fields | Notes |
|--------|-----------|-------|
| `users` | id, email, hashed_password, display_name, role (requester \| technician \| facilities_admin \| leadership), created_at | Role is a single enum; one user = one role in MVP |
| `sites` | id, site_code (unique), name, address_line, active (bool), created_at, updated_at | Inactive sites reject new work orders |
| `locations` | id, site_id (FK), floor, area_label (nullable), created_at | Belongs to one site |
| `work_orders` | id, title, description, category, priority, status, requester_id (FK users), assignee_id (FK users, nullable), site_id (FK), location_id (FK, nullable), due_by (nullable), created_at, updated_at, assigned_at, started_at, completed_at, closed_at, is_overdue (computed), reopen_reason (nullable) | Timestamps null until transition occurs |
| `work_order_status_history` | id, work_order_id (FK), from_status, to_status, changed_by_user_id (FK), changed_at, reason (nullable) | Append-only audit log |
| `comments` | id, work_order_id (FK), author_id (FK users), body (text), created_at | Immutable after insert |

### External Integrations

- **None in MVP.** No email/SMS, no SSO, no IoT, no ERP.
- Future candidates (out of scope): SMTP for notifications, OAuth2 IdP, parts inventory API.

### API Surface

- All API routes under prefix `/api/v1/`
- OpenAPI schema auto-generated by FastAPI; accessible at `/docs` (dev only)
- Streamlit communicates with the API via HTTP (e.g., `httpx` or `requests`); no direct DB access from UI layer

---

## 8. Analytics & Observability

**Logging**
- Every inbound HTTP request logged: timestamp, method, path, query params (redacted if auth), response status, duration ms.
- Authentication failures logged at WARN level with masked email.
- All unhandled exceptions logged at ERROR with full stack trace.
- No PII (passwords, full email in production) in log lines.

**Key Application Metrics** *(collected via structured logs or lightweight middleware; no external APM required for MVP)*
- Work order creation rate (per hour/day)
- Status transition counts by type
- Overdue count snapshot at dashboard load time
- API error rate (4xx, 5xx) by route

**Dashboard Endpoint Metrics**
- `GET /dashboard/sla` response payload acts as the primary observability artifact for leadership; no separate BI tooling required in MVP.

**Alerts** *(assumption: out of scope for MVP infra; listed for future reference)*
- High 5xx rate → page on-call (future)
- DB connection pool exhaustion (future)

---

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Concurrent status transitions (two admins reassigning simultaneously) | Data inconsistency, wrong technician on record | Use DB-level optimistic locking or row-level locking on work order update; return HTTP 409 on conflict |
| Overdue flag staleness (computed at query time vs. stored) | Leadership dashboard shows stale counts | Compute `is_overdue` as a derived expression in SQL (`due_by < now() AND status != 'closed'`) rather than a stored column; refreshed on every read |
| Seed data dev password leaked to production | Security breach | Dev password documented only in seed SQL comment; seed script blocked by environment guard (`assert ENV == "development"`); production uses strong generated secrets |
| Streamlit importing app internals directly (bypassing API auth) | Role enforcement bypassed | CI lint rule (or import guard) asserting `ui/` has zero imports from `app/`; Streamlit must use HTTP client only |
| Inactive-site data loss confusion | Admin deactivates site; historical orders become confusing | Inactive site read access preserved; UI clearly labels orders from inactive sites; deactivation requires explicit confirmation in UI |
| Scope creep from stakeholders requesting notifications | Delays MVP delivery | Non-goals clearly documented; change requests require separate PRD addendum |
| SQLite file-locking under concurrent Streamlit + API load | Write contention in local dev | README recommends PostgreSQL for any concurrent-user testing; SQLite acceptable for single-user demo |

---

## 10. Open Questions

| # | Question | Suggested owner |
|---|----------|-----------------|
| 1 | What is the target deployment environment for the pilot? (Docker Compose on a VM, managed PaaS, cloud container service?) This affects NFR-6 availability targets. | Jordan / Engineering lead |
| 2 | Should a technician be assignable to multiple simultaneous work orders, or is there a cap? The workload view currently shows counts but no cap enforcement. | Jordan / Facilities admin |
| 3 | What is the desired JWT TTL for production? (60 min assumed; shorter TTL increases security but requires refresh token support not in scope.) | Security / Engineering |
| 4 | Are there regulatory requirements (e.g., data residency, retention periods for work order history) beyond the immutability requirement? | Legal / Compliance |
| 5 | Should the `reopen_reason` field be required for all reopens or only when closed by admin force-close? (Brief says reason required on reopen; clarify if symmetric.) | Jordan |
| 6 | Is the leadership role intended to be a standalone login or a shared dashboard link? Shared link would require token-less read access, which conflicts with the current JWT design. | Jordan / Leadership stakeholders |
| 7 | What is the expected row volume at 12 months? (Drives decision on PostgreSQL vs. SQLite for production.) | Jordan / Engineering |
| 8 | Should the `due_by` urgent-priority warning be surfaced visually in the Streamlit UI, or only in the API response `warnings` field? | Product / Jordan |
| 9 | Are categories (HVAC, plumbing, electrical, access, general) fixed enum values or should they be admin-configurable in a future phase? | Jordan |
| 10 | Who can delete a user account, and what happens to their open work orders on deletion? (Not in MVP scope but needs a placeholder policy.) | Jordan / Engineering |

---

## 11. Delivery & Client Surface

| Concern | Choice | Implementation notes |
|---------|--------|---------------------|
| Client UI | **Streamlit** | Role-gated views per persona; four distinct view contexts rendered based on JWT role stored in `st.session_state` |
| API | **FastAPI** under `target-apps/facility-work-order-hub/app/` | REST + OpenAPI; routes prefixed `/api/v1/`; auto-docs at `/docs` (disable in production) |
| UI location | `target-apps/facility-work-order-hub/ui/streamlit_app.py` | HTTP client to API only (`httpx` or `requests`); **never** import from `app/` |
| Auth for UI | JWT Bearer — same tokens as API | Streamlit stores token in `st.session_state["token"]`; on expiry redirects to login page; no refresh token in MVP |
| API process | `uvicorn app.main:app --reload --reload-dir app --reload-dir schemas` | Avoids `.venv` reload storms; documented in README |
| Streamlit process | `streamlit run ui/streamlit_app.py` | Runs separately from API; `FASTAPI_BASE_URL` env var configures API origin |
| Database | PostgreSQL (recommended) or SQLite for single-user demo | SQLAlchemy ORM with Alembic migrations; seed script at `scripts/seed.py` |
| Output directory | `target-apps/facility-work-order-hub/` | All app, UI, migration, script, and test files rooted here |
| OpenAPI schema | Auto-generated by FastAPI | Accessible at `/docs` and `/openapi.json` in dev; used as integration contract for Streamlit HTTP calls |

---

## Appendix: Assumptions

- **Database:** PostgreSQL is the recommended production database; SQLite is acceptable for local single-user demo. Assumption that the team will choose based on deployment context (Open Question 7).
- **ORM / migrations:** SQLAlchemy 2.x with Alembic for schema migrations. Pydantic v2 for request/response schemas.
- **JWT library:** `python-jose` or `PyJWT`; secret loaded from `SECRET_KEY` environment variable; 60-minute default TTL.
- **Password hashing:** `bcrypt` via `passlib`; cost factor 12.
- **Single role per user:** Each user has exactly one role. No multi-role user support in MVP.
- **`is_overdue` is computed dynamically** in SQL/ORM rather than stored, so it is always current without a background job.
- **`work_order_status_history` is append-only** and written by the API on every status transition; no direct DB write path bypasses it.
- **Pagination defaults:** page_size = 20, max page_size = 100.
- **API versioning:** `/api/v1/` prefix only; no version negotiation in MVP.
- **No background/async workers:** Overdue flagging and dashboard aggregations are synchronous query-time computations. No Celery, Redis, or cron jobs in MVP.
- **No email integration:** Confirmed by brief; SLA visibility is strictly in-app.
- **Seed dev password:** A single shared password (e.g., `DevPassword123!`) used for all seed users; documented in a SQL comment inside the seed file; not re-used in any other environment.
- **Streamlit chart library:** `st.bar_chart`, `st.table`, or `plotly` via `st.plotly_chart` for leadership dashboard — choice left to implementer.
- **Availability:** MVP targets single-instance deployment; no high-availability or load-balancing requirements assumed.
- **Comments visibility for leadership:** Leadership can read comments (GET) but the `author_id` / `email` fields are replaced with `display_name` only in the response serialization for the leadership role.
- **Reopen reason required symmetrically:** Both admin-initiated and status-driven reopens require a `reopen_reason` string (pending confirmation in Open Question 5).
- **`started_at` timestamp** is set when status transitions to `in_progress` (whether first time or after reopen; most recent transition time recorded).
