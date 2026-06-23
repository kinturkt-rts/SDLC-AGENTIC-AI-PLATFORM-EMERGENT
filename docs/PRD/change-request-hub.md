# Change Request Hub — PRD

## 1. Overview

IT change management at many mid-sized companies still runs on email threads and shared spreadsheets, creating blind spots around scheduled production changes, missing approvals, and untraceable status transitions. Sam (Change Manager) and her colleagues at a 600-person company face exactly this problem: implementers merge without approval, leadership cannot assess risk in real time, and nobody has a single view of what is happening in production this weekend.

The **Change Request Hub** provides a single, role-aware web application backed by a versioned REST API. Requesters draft changes against a curated service catalog; change managers triage, approve, reject, and schedule those changes against environment blackout windows; implementers work a personal queue and mark changes complete; and leadership reads aggregated risk dashboards without accessing raw request data beyond display names. Every status transition, approval decision, and comment is timestamped and append-only, giving Sam the audit trail she needs for compliance and post-incident review.

The MVP is a Streamlit front-end communicating exclusively over HTTP with a FastAPI + PostgreSQL back-end, deployed locally for demo and designed for containerised production. The app slug is `change-request-hub`; all server code lives under `target-apps/change-request-hub/`; Streamlit lives at `ui/streamlit_app.py`.

---

## 2. Goals & Success Metrics

| Goal | Metric | Target | Notes |
|------|--------|--------|-------|
| Eliminate approval-less production changes | % of completed changes with an approval record | 100 % in system (enforced by API) | Enforced via status lifecycle guard |
| Give managers real-time visibility | Time to find overdue or emergency changes on dashboard | < 10 seconds from login | Leadership dashboard auto-loads |
| Prevent scheduling into blackout windows | Blackout-overlap requests blocked at API | 0 changes scheduled during active blackouts | 422 returned on overlap |
| Full audit traceability | Every non-draft change has ≥ 1 status_history row | 100 % of transitions recorded | Append-only enforcement |
| Reduce triage queue time for managers | Manager can approve/schedule/assign from single triage table | All actions available without page navigation | Streamlit triage table |
| Capture emergency changes with correct urgency | Emergency changes flagged separately on dashboard | Dashboard separates emergency count from normal/standard | Separate dashboard metric |

---

## 3. Non-Goals / Out of Scope

- SSO / external identity provider (SAML, OIDC, LDAP)
- ServiceNow or Jira synchronisation / webhook integration
- Email or in-app push notifications for approvals or reminders
- CAB calendar invites or calendar feed export
- Auto-implementation triggers or CI/CD pipeline hooks
- Multi-tenant organisation isolation (single-tenant MVP)
- File or binary attachments beyond the `rollback_plan` free-text field
- Mobile-native application
- Role or permission administration UI (roles are seeded)
- Archival / purge workflows beyond closed status

---

## 4. Users & Use Cases

| Persona | Need | Primary use case |
|---------|------|------------------|
| **Change Requester** | Draft, submit, and track own change requests | Fills in change form (service, environment, dates, rollback plan), submits for approval, monitors status, adds comments on own changes |
| **Change Manager** | Triage all requests, approve/reject, schedule, manage catalog | Reviews triage queue sorted newest-first, approves or rejects with comment, schedules approved changes, assigns implementers, manages service/environment/blackout catalog |
| **Implementer** | See assigned work queue and record execution | Views personal queue of scheduled/implementing changes, clicks Start then Complete, adds implementation comments |
| **Leadership** | Read-only risk and volume overview | Views dashboard: counts by status/risk, overdue scheduled items, monthly volume by environment, top services, emergency flag |
| **Unauthenticated / monitoring** | Verify service health | Calls `GET /health` — no auth required |

---

## 5. Functional Requirements

| ID | Description | Priority | Acceptance criteria (Given / When / Then) |
|----|-------------|----------|-------------------------------------------|
| **FR-1** | **JWT Authentication** — `POST /api/v1/auth/token` accepts `email` + `password`, returns a signed JWT Bearer token encoding `user_id` and `role`. | P0 | **Given** a seeded user with correct credentials **When** `POST /api/v1/auth/token` is called **Then** HTTP 200 is returned with a non-empty `access_token`; **Given** wrong password **Then** HTTP 401. |
| **FR-2** | **Service Catalog CRUD** — Change managers can `POST /api/v1/services` (create) and `PATCH /api/v1/services/{id}` (update name, owner_team, tier, active flag). All roles can `GET /api/v1/services` (paginated, filterable by active). | P0 | **Given** a manager token **When** POST with valid body **Then** 201 with new service; **Given** requester token **When** POST **Then** 403; **Given** any authenticated token **When** GET **Then** 200 with paginated list. |
| **FR-3** | **Environment Registry & Blackout Windows** — Managers can create/read environments (`POST /GET /api/v1/environments`) and blackout windows (`POST /GET /api/v1/blackout-windows`). Blackout windows have `start_at`, `end_at`, `reason`, linked to an environment. | P0 | **Given** a manager **When** POST environment with valid body **Then** 201; **Given** any authenticated token **When** GET environments **Then** 200 list; **Given** manager creates blackout for prod 2025-08-01→08-07 **Then** GET blackout-windows?environment_id=prod returns that record. |
| **FR-4** | **Change Request Creation** — Authenticated requesters and managers can `POST /api/v1/change-requests` with required fields (title, description, service_id, target_environment_id, change_type, risk, planned_start, planned_end, rollback_plan). New requests enter `draft` status. Inactive service or environment rejects the request. | P0 | **Given** requester with valid service_id and active environment **When** POST **Then** 201 with status=draft; **Given** inactive service_id **When** POST **Then** 422 with descriptive error; **Given** unauthenticated caller **When** POST **Then** 401. |
| **FR-5** | **Status Lifecycle Transitions** — `PATCH /api/v1/change-requests/{id}/status` enforces the defined graph: draft→submitted (requester/manager), submitted→approved (manager), submitted→rejected (manager, reason required), approved→scheduled (manager, planned window checked against blackouts), scheduled→implementing (implementer assigned to change), implementing→completed (assigned implementer only), completed→closed (manager). Emergency path: change_type=emergency may go approved→implementing (skip scheduled). Invalid transitions return 422. | P0 | **Given** submitted change **When** requester attempts approve **Then** 403; **Given** approved change **When** manager schedules with window overlapping active blackout **Then** 422; **Given** approved emergency change **When** manager transitions to implementing **Then** 201 skipping scheduled; **Given** implementing change **When** unassigned implementer attempts complete **Then** 403; **Given** any invalid transition (e.g. draft→completed) **Then** 422. |
| **FR-6** | **Approval Record** — Each approve/reject transition on a change creates an immutable `approval_records` row capturing `change_id`, `approver_id`, `decision`, `comment`, `decided_at` (TIMESTAMPTZ). | P0 | **Given** manager approves a change **When** GET /api/v1/change-requests/{id} **Then** response includes approval object with all five fields populated; **Given** a second approve attempt on already-approved change **Then** 422 (invalid transition). |
| **FR-7** | **Blackout Overlap Enforcement** — When transitioning a change to `scheduled`, the API checks whether `[planned_start, planned_end]` overlaps any active blackout window for the target environment. Overlap returns 422 with the conflicting blackout window id and reason. | P0 | **Given** environment prod has blackout 2025-08-01 00:00 → 08-07 23:59 **When** scheduling a change with planned_start=2025-08-03 **Then** 422 listing blackout id; **Given** change planned outside blackout **When** scheduling **Then** transition succeeds. |
| **FR-8** | **Append-Only Comments Thread** — `POST /api/v1/change-requests/{id}/comments` allows requesters (own changes), implementers (assigned changes), and managers (any change) to add comments. `GET /api/v1/change-requests/{id}/comments` returns ordered thread. No edit or delete endpoint exists. | P1 | **Given** manager POSTs comment **Then** 201 with comment id and `posted_at`; **Given** requester POSTs on another user's change **Then** 403; **Given** any attempt to DELETE or PATCH a comment **Then** 405/404. |
| **FR-9** | **Append-Only Status History** — Every status transition writes an immutable row to `status_history` (from_status, to_status, actor_id, changed_at, reason). The change detail endpoint includes the full ordered history. No update or delete of history rows is permitted. | P0 | **Given** a change goes draft→submitted→approved **When** GET /api/v1/change-requests/{id} **Then** status_history has ≥ 2 rows in chronological order; **Given** any attempt to PATCH a history row **Then** 405/404. |
| **FR-10** | **Implementer Assignment** — `PATCH /api/v1/change-requests/{id}/assign` allows managers to set or update `implementer_id` on a change. Returns a user list or workload endpoint for selectbox population in Streamlit. | P1 | **Given** manager PATCH assign with valid implementer_id **Then** 200 with updated change; **Given** requester PATCH assign **Then** 403; **Given** invalid user_id **Then** 422. |
| **FR-11** | **Role-Scoped Change List** — `GET /api/v1/change-requests` returns paginated results filtered by role: requesters see only their own changes; implementers see assigned changes; managers see all changes; leadership sees all changes (read-only). Default sort: `created_at` descending. | P0 | **Given** requester A **When** GET /api/v1/change-requests **Then** list contains only changes where requester_id = A; **Given** manager **When** GET **Then** all changes returned; **Given** implementer B **When** GET **Then** only changes assigned to B. |
| **FR-12** | **Leadership Dashboard** — `GET /api/v1/dashboard/summary` (manager + leadership roles) returns: counts by status, counts by risk, count of overdue scheduled changes (planned_end < now AND status not in completed/closed/rejected), changes this month by environment, top-N services by volume, count of active emergency changes. | P0 | **Given** 2 overdue scheduled changes exist in seed data **When** leadership calls GET /api/v1/dashboard/summary **Then** `overdue_scheduled_count` ≥ 2; **Given** requester calls same endpoint **Then** 403. |
| **FR-13** | **Streamlit UI — Requester Journey** | P0 | **Given** logged-in requester **When** Create Change form submitted via UI **Then** POST hits API, success banner shown, my-changes table refreshes (st.rerun); **Given** form missing required field **Then** inline error before API call. |
| **FR-14** | **Streamlit UI — Change Manager Journey** | P0 | **Given** logged-in manager **When** triage table displayed **Then** all changes visible sorted newest-first; approve/reject/schedule actions each call correct PATCH endpoint and table refreshes; catalog CRUD tables callable from same session. |
| **FR-15** | **Streamlit UI — Implementer Journey** | P0 | **Given** logged-in implementer **When** queue page loaded **Then** only assigned scheduled/implementing changes shown; Start and Complete buttons call correct status PATCH; comment box POSTs to comments endpoint. |
| **FR-16** | **Streamlit UI — Leadership Dashboard** | P1 | **Given** logged-in leadership user **When** dashboard page loaded **Then** all six dashboard metrics from FR-12 rendered as Streamlit metrics/tables; no create/edit controls visible; emergency count highlighted separately. |
| **FR-17** | **Health Check** — `GET /health` returns HTTP 200 with `{"status":"ok"}` with no authentication required. | P0 | **Given** unauthenticated GET /health **Then** 200 `{"status":"ok"}` in < 200 ms. |
| **FR-18** | **Seed Data** — Database seed script populates ≥ 6 services (tier1–tier3), 3 environments, 2 blackout windows (1 active), ≥ 10 change requests covering all statuses (including 1 rejected, 1 emergency, 2 overdue scheduled), approval rows on ≥ 5 changes, comments on ≥ 4, status_history on all non-draft changes, and 6 seed users (2 requesters, 2 implementers, 1 manager, 1 leadership) with a single shared dev password documented in a SQL comment. Timestamps span ≥ 90 days. | P0 | **Given** seed script run against empty DB **When** all assertions in tests/test_seed.py execute **Then** all row-count checks pass and each status value appears at least once. |

---

## 6. Non-Functional Requirements

| ID | Category | Target | Measurement / verification | Notes |
|----|----------|--------|---------------------------|-------|
| **NFR-1** | Performance | p95 API response ≤ 300 ms for list endpoints under 50 concurrent users | Load test with Locust or k6 against local Docker stack | (Assumption) — target derived from typical internal tooling SLAs |
| **NFR-2** | Performance | p99 dashboard summary endpoint ≤ 500 ms | Measured via k6 smoke test in CI | (Assumption) — aggregation query may be heavier |
| **NFR-3** | Security / Auth | All non-health endpoints reject unauthenticated requests with HTTP 401 | Automated test suite: hit every protected route without token, assert 401 | JWT Bearer; tokens expire after configurable TTL (default 8 h) |
| **NFR-4** | Security / Authorisation | Role-based access control enforced server-side; Streamlit UI hides controls but API is authoritative | Integration tests: requester→approve returns 403; implementer→assign returns 403 (see FR-5, FR-10, FR-11) | No client-side-only RBAC |
| **NFR-5** | Security / Data | Passwords stored as bcrypt hashes (cost factor ≥ 12); plaintext never logged | Code review + automated test verifying hash prefix `$2b$` in DB | (Assumption) |
| **NFR-6** | Availability | Service available 99.5 % of scheduled hours in local/staging deployment | Uptime monitored via health check polling | (Assumption) — MVP; no HA cluster required in Phase 1 |
| **NFR-7** | Data Integrity | All `*_at` timestamp columns stored as `TIMESTAMPTZ` in PostgreSQL; no naive datetimes persisted | SQLAlchemy model review + migration inspection; pytest checks UTC offset present in response payloads | Specified in brief |
| **NFR-8** | Data Integrity / Immutability | No UPDATE or DELETE SQL issued against `status_history` or `comments` tables after insert | Integration tests confirm 405/404 on edit/delete routes; DB trigger or model-level guard | Append-only requirement from brief |
| **NFR-9** | Scalability | Paginated list endpoints accept `page` and `page_size` params; default `page_size=25`, max `page_size=100` | Unit test: GET /api/v1/change-requests?page=1&page_size=5 returns ≤ 5 items with `total` count | (Assumption) on defaults |
| **NFR-10** | Observability | Structured JSON logs on every API request: method, path, status code, duration_ms, user_id (if authenticated) | Log output inspected in CI; no PII beyond user_id | (Assumption) — using `uvicorn` access log + middleware |
| **NFR-11** | Operability | Local dev startup documented: `uvicorn app.main:app --reload --port 8000` (optionally `--reload-dir app --reload-dir schemas`); README includes seed command and Streamlit start command | Developer onboarding test: clone → follow README → app running in < 10 minutes | From brief |
| **NFR-12** | Compliance / Audit | Status history and approval records must never be deleted or altered via any API or admin path in MVP | Penetration/misuse test: direct DB DELETE attempt blocked by application-layer guard; no exposed admin purge route | Supports change-control audit requirements |

---

## 7. Data & Integrations

### Core Entities

| Entity | Key Fields | Notes |
|--------|-----------|-------|
| `users` | id, email, password_hash, display_name, role (requester\|manager\|implementer\|leadership), active | Seeded; no self-registration in MVP |
| `services` | id, name, owner_team, tier (tier1\|tier2\|tier3), active, created_at, updated_at | Managed by change manager |
| `environments` | id, name (dev\|staging\|prod or custom), sort_order, active, created_at | Managed by change manager |
| `blackout_windows` | id, environment_id (FK), start_at, end_at, reason, created_by, created_at | TIMESTAMPTZ; checked on scheduling |
| `change_requests` | id, title, description, service_id (FK), target_environment_id (FK), change_type, risk, status, requester_id (FK), implementer_id (FK nullable), planned_start, planned_end, rollback_plan, created_at, updated_at, submitted_at, approved_at, scheduled_at, started_at, completed_at, closed_at | All *_at = TIMESTAMPTZ |
| `approval_records` | id, change_id (FK), approver_id (FK), decision (approved\|rejected), comment, decided_at | Immutable after insert |
| `comments` | id, change_id (FK), author_id (FK), body, posted_at | Immutable after insert |
| `status_history` | id, change_id (FK), from_status, to_status, actor_id (FK), changed_at, reason | Append-only |

### External Integrations (MVP)

| System | Type | Notes |
|--------|------|-------|
| PostgreSQL | Primary datastore | TIMESTAMPTZ everywhere; managed via SQLAlchemy + Alembic migrations |
| FastAPI | REST API server | OpenAPI docs at `/docs`; all Streamlit calls go through HTTP |
| Streamlit | Browser UI | Pattern C — HTTP client only; never imports `app/` modules directly |
| JWT (python-jose or equivalent) | Auth token | Signed HS256 or RS256; secret from environment variable |

No external SaaS integrations in MVP scope.

---

## 8. Analytics & Observability

**Application Logging**
- Structured JSON log per request: `timestamp`, `method`, `path`, `status_code`, `duration_ms`, `user_id` (from JWT or `anonymous`).
- Errors (5xx) logged at ERROR level with full stack trace; warnings for 4xx auth failures.
- No PII (email, display_name) in logs beyond `user_id`.

**Dashboard Metrics** (business-layer, served via `/api/v1/dashboard/summary`)
- Change counts grouped by `status` and `risk`.
- Overdue scheduled count: `planned_end < now()` AND `status NOT IN (completed, closed, rejected)`.
- Changes created/scheduled this calendar month, grouped by environment.
- Top 10 services by total change_request count (all-time).
- Active emergency change count (`change_type = emergency AND status NOT IN (completed, closed, rejected)`).

**Infrastructure Observability** *(Assumption — not specified in brief)*
- `GET /health` endpoint for liveness probe.
- Readiness probe may check DB connection (TBD at deployment stage).
- Prometheus metrics endpoint (`/metrics`) considered for Phase 2; not required in MVP.

**Alerting** *(Assumption)*
- Out of scope for MVP; recommend setting external uptime monitor on `/health` post-launch.

---

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Blackout overlap logic has off-by-one or timezone bug, allowing changes to slip through | High — production incident during protected window | Use TIMESTAMPTZ throughout; write dedicated pytest parametrised tests for boundary conditions (starts exactly at blackout end, ends exactly at blackout start) |
| Status lifecycle guard bypassed via direct DB access or missed route | High — untracked changes, audit failure | Centralise all transitions in a single service-layer function; no status field writable via generic PATCH; integration tests cover every invalid transition |
| JWT secret leaked in repo | High — full auth bypass | Secret loaded from env var only; `.env` in `.gitignore`; CI secret scanning enabled |
| Append-only requirement violated by a future migration or admin script | Medium — audit trail integrity | Add DB-level `RULE` or trigger on `status_history` and `comments` disallowing UPDATE/DELETE; document in migrations |
| Seed data not representative, causing demo failures | Medium — poor stakeholder impression | Seed script tested in CI; timestamps spread over 90 days; all statuses and personas exercised |
| Streamlit imports FastAPI `app/` modules directly (Pattern C violation) | Medium — hidden coupling, environment bleed | Enforce via CI lint rule (`grep -r "from app" ui/`); architecture decision record |
| Leadership dashboard slow on large datasets without indexes | Low-Medium — poor UX for leadership persona | Add DB indexes on `change_requests(status)`, `(planned_end)`, `(created_at)`, `(service_id)`, `(target_environment_id)` in initial migration |
| Single shared dev password in seed SQL committed to repo | Low (dev only) — credential hygiene risk | Document clearly as dev-only; README warns against using in staging/prod; password not reused in CI secrets |

---

## 10. Open Questions

| # | Question | Suggested owner |
|---|----------|-----------------|
| 1 | What JWT algorithm and token TTL should be used in production (HS256 with env secret vs RS256 with key pair)? | Tech Lead / Security |
| 2 | Should the `PATCH /api/v1/change-requests/{id}/status` endpoint accept the target status in the body, or should each transition have its own sub-path (e.g. `/approve`, `/reject`, `/schedule`)? | Architect |
| 3 | Is there a maximum number of approval records per change (e.g. re-approval after a re-submitted rejected change)? | Change Manager (Sam) |
| 4 | Should emergency changes require a secondary approval (e.g. senior manager) or is one approval sufficient for MVP? | Sam / Business stakeholder |
| 5 | What is the intended deployment target beyond local dev — Docker Compose, managed PaaS, Kubernetes? Affects readiness probes and secret management. | DevOps / Infra |
| 6 | Should the `GET /api/v1/change-requests` endpoint for leadership return all changes (for drill-down) or only aggregated summary? Brief states read-only dashboard, but a detail view may be needed. | Sam / Leadership stakeholder |
| 7 | Are there data-retention requirements (e.g. closed changes must be kept for N years) that affect the no-delete policy? | Compliance / Sam |
| 8 | Should the manager be able to withdraw a submitted change back to draft (brief implies manager-only), or can the requester also withdraw their own submission? | Sam |
| 9 | Will Streamlit need multi-page routing (st.navigation / st.Page in Streamlit ≥ 1.36) or a single-page tab approach? | Front-end / Tech Lead |
| 10 | Is a workload / capacity endpoint needed (e.g. implementer open change counts for manager assignment selectbox), or is a plain user list sufficient? | Sam / Architect |

---

## 11. Delivery & Client Surface

| Concern | Choice | Implementation notes |
|---------|--------|---------------------|
| Client UI | **Streamlit** | Full role-aware UI: requester create/list, manager triage/catalog, implementer queue, leadership dashboard. All described in FR-13 – FR-16. |
| API | FastAPI under `target-apps/change-request-hub/` | REST + OpenAPI (`/docs`); all business logic server-side |
| UI location | `ui/streamlit_app.py` | HTTP client to API only — never imports `app/` package |
| Auth for UI | JWT Bearer | Streamlit stores token in `st.session_state`; login form on first load; token sent as `Authorization: Bearer <token>` on every API call |
| API versioning | `/api/v1/` prefix on all protected routes | Health check at `/health` (no prefix, no auth) |
| Local dev start (API) | `uvicorn app.main:app --reload --port 8000` | Optionally `--reload-dir app --reload-dir schemas` to avoid reload storms on schema file changes |
| Local dev start (UI) | `streamlit run ui/streamlit_app.py` | Reads `API_BASE_URL` from env (default `http://localhost:8000`) |
| DB migrations | Alembic under `target-apps/change-request-hub/alembic/` | Initial migration includes all indexes from NFR-12 |
| Seed script | `scripts/seed.py` or `seed.sql` | Shared dev password documented in comment; documented in README |
| OpenAPI contract | Auto-generated at `/docs` and `/openapi.json` | Architect must verify all 17 routes from brief are present |

---

## Appendix: Assumptions

- **Password hashing**: bcrypt with cost factor ≥ 12 assumed; library choice (passlib, bcrypt) left to implementer.
- **JWT algorithm**: HS256 with a secret loaded from `JWT_SECRET_KEY` env var assumed for MVP; RS256 deferred to production hardening.
- **Token TTL**: 8 hours assumed; configurable via `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` env var.
- **Pagination defaults**: `page=1`, `page_size=25`, max `page_size=100` assumed; not specified in brief.
- **User self-registration**: Not available in MVP; all users are seeded.
- **Role enum**: `requester | manager | implementer | leadership` derived directly from brief personas; stored as string enum in DB.
- **Single shared dev password**: A single plaintext password (e.g. `ChangeMe123!`) will be used for all seed users in development; bcrypt hash stored in DB; plaintext documented only in seed SQL comment and README dev section.
- **Streamlit version**: ≥ 1.30 assumed; multi-page routing approach (tabs vs st.navigation) left to implementer (see Open Question 9).
- **FastAPI dependency versions**: Python ≥ 3.11, FastAPI ≥ 0.110, SQLAlchemy ≥ 2.0, Alembic ≥ 1.13 assumed.
- **Database**: PostgreSQL ≥ 15 assumed; no support for SQLite in production (TIMESTAMPTZ requirement).
- **Leadership drill-down**: Leadership role can call `GET /api/v1/change-requests/{id}` for detail view; brief states read-only but does not restrict detail access. Flagged as Open Question 6.
- **Workload endpoint**: `GET /api/v1/users` or `GET /api/v1/users?role=implementer` assumed sufficient for manager assignment selectbox; dedicated workload endpoint deferred (Open Question 10).
- **Prometheus / metrics endpoint**: Not required in MVP; deferred to Phase 2.
- **CI/CD pipeline**: Not defined; tests assumed to run via `pytest` locally and in any standard CI runner.
- **Containerisation**: Docker Compose file considered in scope for local dev convenience but not explicitly required by brief; included as a recommended deliverable.
- **Overdue definition**: "Overdue scheduled" means `status = 'scheduled'` AND `planned_end < now()` (i.e. the window has passed without the change being started or completed).
- **Emergency dashboard flag**: "Flags emergencies separately" interpreted as a dedicated `active_emergency_count` field in dashboard summary response, not a separate endpoint.
