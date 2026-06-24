# Shift Swap Board — PRD

## 1. Overview

Floor leads at this organisation currently coordinate shift coverage through a group chat, which routinely produces double-booking or uncovered slots because there is no single authoritative record of an agreed swap. A staff member offers a shift, a colleague volunteers, a manager assumes the matter is resolved — and the actual roster never changes.

The Shift Swap Board is a small internal web tool that makes the roster the single source of truth. Staff post swap offers for their own upcoming shifts, colleagues claim those offers, and the floor lead assigned to that calendar week approves or denies the claim. Only an approved decision triggers an atomic update to the roster. Every status transition is appended to an audit log that satisfies compliance inquiries without requiring a separate spreadsheet or chat history.

The system is delivered as a FastAPI backend (Pattern C) with a Streamlit front end, hosted on the same RDS instance and using the same JWT-based login pattern as the organisation's other internal FastAPI applications (`inventory-app`, `employee-leave-manager`). MVP scope covers shift offering, claiming, floor-lead sign-off, roster reflection, and audit; notifications, payroll integration, and mobile clients are explicitly out of scope.

---

## 2. Goals & Success Metrics

| Goal | Metric | Target | Notes |
|------|--------|--------|-------|
| Eliminate double-booking caused by chat-based swaps | Count of overlapping roster assignments per week post-launch | 0 | Enforced at API level, not UI only |
| Make the roster the single authoritative schedule | Percentage of approved swaps reflected in `/roster` within the same HTTP transaction | 100 % | Atomic DB transaction on approve |
| Provide auditable change history | Audit rows created per swap lifecycle event | 1 row per action (create / claim / approve / deny / cancel / roster_updated) | Required for compliance review |
| Ensure floor lead sign-off is mandatory | Swaps reaching "approved" state without floor-lead action | 0 | API enforces role + week assignment |
| Pass CI pipeline end-to-end | pytest suite green on `target-apps/shift-swap-board/` | 100 % pass, 0 failures | Includes bcrypt seed verification |
| Developer onboarding | Time from `git clone` to running demo with seeded data | ≤ 15 minutes following README | Two-terminal start: uvicorn + streamlit |

---

## 3. Non-Goals / Out of Scope

- Slack, group-chat, push notification, or email integration of any kind
- Payroll, time-clock, or HR system synchronisation
- Mobile application or Progressive Web App
- OAuth 2.0, SAML, or any corporate/external SSO
- Multi-tenant or multi-organisation support
- AI / ML features or AWS Bedrock integration
- Shift creation or scheduling by staff (roster is seeded/managed by admin only in v1)
- Recurring swap rules or bulk swap operations
- Real-time collaborative UI (WebSockets, polling beyond page reload)
- Approval delegation (floor lead cannot hand off approval to another lead)

---

## 4. Users & Use Cases

| Persona | Need | Primary use case |
|---------|------|------------------|
| **Staff** | Offer a shift they cannot work; pick up an available shift | Post a swap offer for one of their own upcoming shifts; browse open offers and claim one that suits them |
| **Floor Lead** | Maintain correct coverage for their assigned week without managing a chat thread | Review claimed swap requests for their week; approve or deny with an optional note |
| **Admin** | Seed and maintain the roster; assign floor leads; review audit history | Upload/manage roster rows; assign a floor lead to a calendar week; read the full audit log |
| **Anonymous / Health-check** | Uptime monitoring, load-balancer probe | `GET /health` — no credentials required |

---

## 5. Functional Requirements

| ID | Description | Priority | Acceptance criteria (Given / When / Then) |
|----|-------------|----------|-------------------------------------------|
| FR-1 | **JWT Authentication** — `POST /auth/login` accepts `username` + `password`, validates against bcrypt hash, returns a signed HS256 JWT containing `user_id`, `role`, and expiry. All non-public routes reject requests without a valid Bearer token with HTTP 401. | P0 | **Given** a valid username and correct password, **When** `POST /auth/login` is called, **Then** HTTP 200 is returned with a JWT; **Given** an expired or missing token, **When** any protected endpoint is called, **Then** HTTP 401 is returned. |
| FR-2 | **Roster read endpoints** — `GET /roster` (optional `?from=` `?to=` date filters) returns all shift roster rows with staff display names. `GET /roster/mine` returns only the authenticated user's upcoming shifts. Both endpoints reflect the post-approval state immediately. | P0 | **Given** an authenticated user and an approved swap that exchanged shift owners, **When** `GET /roster` is called, **Then** the response lists the accepter on that slot and the offerer absent from it; filter parameters correctly narrow rows by date range. |
| FR-3 | **Create swap offer** — `POST /swaps` (staff role) creates an `open` swap for a shift currently assigned to the authenticated user. Returns 403 if the shift belongs to another user, 422 if the shift date is in the past, and 409 if an active (`open` or `claimed`) swap already exists for that `offered_shift_id`. An audit row `created` is appended atomically. | P0 | **Given** a staff user who owns an upcoming shift with no existing active swap, **When** `POST /swaps` is called with that shift id, **Then** HTTP 201 is returned with status `open` and an audit row `created` exists; **Given** the same shift id is submitted again, **Then** HTTP 409 is returned. |
| FR-4 | **Claim a swap offer** — `POST /swaps/{id}/claim` (staff role) transitions an `open` swap to `claimed`, recording `claimed_by_user_id` and `claimed_at`. Returns 409 if already claimed, 403 if the claimer is the offerer, and 422 with detail if the claimer already holds a shift on the same `shift_date` + `shift_window`. An audit row `claimed` is appended. | P0 | **Given** an open swap and a staff user who does not own the offered shift and has no conflicting slot, **When** `POST /swaps/{id}/claim` is called, **Then** HTTP 200 and status `claimed`; **Given** the claimer already has a shift on the same date/window, **Then** HTTP 422 with overlap detail. |
| FR-5 | **Floor-lead approval with atomic roster update** — `POST /swaps/{id}/approve` (floor_lead role) is permitted only for the user who is `floor_lead_user_id` for the ISO week containing the offered shift's `shift_date`. On success, within a single DB transaction: the offerer's `shift_roster` row is removed, the accepter's row is inserted (or updated), `swap_requests.status` → `approved`, and audit rows for `approved` and `roster_updated` are appended. Returns 403 if the caller is not that week's lead or if the offerer is the approver. Re-validates overlap for the accepter at approve time; 422 if conflict exists. | P0 | **Given** the correct week's floor lead approves a claimed swap with no accepter overlap, **When** `POST /swaps/{id}/approve` is called, **Then** HTTP 200; `GET /roster` shows accepter on slot and offerer absent; two audit rows exist (`approved`, `roster_updated`); **Given** a different week's floor lead calls the same endpoint, **Then** HTTP 403. |
| FR-6 | **Floor-lead denial** — `POST /swaps/{id}/deny` (floor_lead role, same week constraint as approval) transitions a `claimed` swap to `denied` (terminal state). Accepts optional `decision_note` in body. Appends audit row `denied`. Returns 403 if wrong week's lead. | P0 | **Given** the correct week's floor lead denies a claimed swap, **When** `POST /swaps/{id}/deny` is called, **Then** HTTP 200 and status `denied`; audit row `denied` exists; subsequent claim attempts on the same swap return 409. |
| FR-7 | **Cancel swap offer** — `POST /swaps/{id}/cancel` (staff role, offerer only) cancels a swap that is currently `open` or `claimed` but not yet decided. Appends audit row `cancelled`. Returns 403 if the caller is not the offerer; 409 if the swap is already in a terminal state. | P1 | **Given** the offerer of an open or claimed swap calls cancel, **When** `POST /swaps/{id}/cancel`, **Then** HTTP 200 and status `cancelled`; audit row `cancelled` exists; **Given** a non-offerer calls cancel, **Then** HTTP 403. |
| FR-8 | **Swap list and filters** — `GET /swaps` returns swap requests visible to the authenticated user (`?status=` and `?week_start=` optional filters). Staff see offers relevant to them (their own plus open offers from others). Floor leads also see claimed swaps for their assigned week(s). Admins see all. | P1 | **Given** a staff user with one open offer they created and one open offer from another user, **When** `GET /swaps` is called, **Then** both offers are present in the response; **Given** `?status=open`, **Then** only open swaps are returned. |
| FR-9 | **Audit log endpoints** — `GET /swaps/{id}/audit` (admin or floor_lead) returns the append-only action history for one swap, ordered by `created_at` ascending. `GET /audit` (admin only) returns recent audit entries with `?limit=` pagination. | P1 | **Given** a swap that has gone through create → claim → approve, **When** `GET /swaps/{id}/audit` is called by an admin, **Then** at least three ordered rows are returned (created, claimed, approved / roster_updated); **Given** a staff user calls the same endpoint, **Then** HTTP 403. |
| FR-10 | **Floor-lead week management** — `POST /floor-leads` (admin) assigns a `floor_lead_user_id` to a `week_start` (Monday). `GET /floor-leads` (admin) lists all assignments. Duplicate `week_start` returns 409. The referenced user must have role `floor_lead`; otherwise 422. | P1 | **Given** an admin posts a valid floor-lead assignment with a Monday date and a floor_lead-role user, **When** `POST /floor-leads` is called, **Then** HTTP 201 and the assignment appears in `GET /floor-leads`; **Given** the same `week_start` is submitted again, **Then** HTTP 409. |
| FR-11 | **Overlap guard enforced server-side** — the system enforces the `UNIQUE(staff_id, shift_date, shift_window)` constraint in `shift_roster` at the application layer (422 with clear `detail`) before any DB write, so the database unique index acts as a secondary safety net rather than the first signal to the user. | P0 | **Given** a staff member already assigned to an afternoon shift on a given date, **When** any code path attempts to assign them to another afternoon shift on the same date (claim or approve), **Then** HTTP 422 is returned with a human-readable overlap message; no duplicate row exists in `shift_roster`. |
| FR-12 | **Streamlit UI — primary user journeys** — the Streamlit app (port 8501) implements: (1) Login page storing JWT in session state; (2) My Shifts page with upcoming roster rows and an "Offer for swap" button; (3) Open Swaps page listing open/claimed requests with a "Claim" button for eligible offers; (4) Floor Lead Inbox visible when the logged-in user is the current week's lead, showing claimed swaps with Approve/Deny controls and optional note field; (5) Roster View table by date showing who is on each window. All pages display API error detail on 401 / 403 / 422 responses. The Streamlit app communicates with the API exclusively over HTTP; it never imports from `app/`. | P0 | **Given** a logged-in staff user, **When** they navigate to "My Shifts", **Then** their upcoming roster rows are displayed; **Given** they click "Offer for swap" on a valid shift, **Then** a `POST /swaps` call is made and the offer appears in Open Swaps; **Given** a 422 is returned, **Then** the error detail from the API is shown in the UI. |
| FR-13 | **Health endpoint** — `GET /health` (no auth) performs a DB connectivity ping and returns HTTP 200 `{"status":"ok"}` when the database is reachable, or HTTP 503 `{"status":"unavailable"}` when it is not. | P0 | **Given** the database is reachable, **When** `GET /health` is called, **Then** HTTP 200; **Given** the database is unreachable (simulated in tests), **Then** HTTP 503. |
| FR-14 | **Seed data** — the project ships a seed script producing: 6–8 staff users, 1 admin, 2 floor-lead users; `floor_lead_weeks` for the current and next calendar week; ~12 roster rows across the next 7 days (mix of morning/afternoon/full); 3 swap requests (1 open, 1 claimed, 1 approved with full audit history). All passwords are real bcrypt hashes; the pipeline `verify_seed_bcrypt` step confirms this. | P1 | **Given** the seed script is run against a clean schema, **When** `GET /roster?from=<today>&to=<today+7>` is called with admin credentials, **Then** at least 12 rows are returned; the `verify_seed_bcrypt` pipeline step exits 0. |

---

## 6. Non-Functional Requirements

| ID | Category | Target | Measurement / verification | Notes |
|----|----------|--------|---------------------------|-------|
| NFR-1 | Security | JWT signed HS256 with `JWT_SECRET_KEY`; passwords stored as bcrypt hashes (cost factor ≥ 12); no plaintext credentials in codebase or logs | Code review + `verify_seed_bcrypt` pipeline step; grep codebase for plaintext passwords | `JWT_SECRET_KEY` loaded from env; absent key causes fail-fast at startup |
| NFR-2 | Security / Authorisation | Role and week-assignment checks enforced in API route handlers; no business-rule enforcement in Streamlit alone | Pytest: wrong-role and wrong-week 403 tests must pass | FR-5, FR-6, FR-10 cover specific 403 cases |
| NFR-3 | Performance | `GET /roster` and `GET /swaps` respond within 500 ms at demo scale (≤ 50 roster rows, ≤ 100 swap records) | Manual smoke test or locust single-user run during review | (Assumption) — production load not specified |
| NFR-4 | Availability | Service restart recovers without data loss; all state persisted in Postgres | No in-memory-only state; validated by restart test in dev | (Assumption) — HA / multi-instance out of scope for MVP |
| NFR-5 | Data Integrity | Approved swap roster update is atomic: both offerer removal and accepter insertion either both succeed or both roll back | Pytest: simulate mid-transaction failure; verify no partial state | Enforced via SQLAlchemy transaction block |
| NFR-6 | Observability | Every swap status transition appended to `swap_audit_log` with `actor_user_id` and `created_at`; FastAPI default access logs enabled | Pytest: verify audit row count per test scenario; check log output in CI | Append-only; no delete on audit rows permitted |
| NFR-7 | Operability | `app/startup_checks.py` validates `DATABASE_URL` format and DB reachability on process start; exits non-zero with descriptive message if invalid | Integration test: start app with bad `DATABASE_URL`; assert non-zero exit and error message | Prevents silent misconfiguration |
| NFR-8 | Compliance / Data retention | `swap_audit_log` rows must not be deleted or updated by any application code path; schema has no `DELETE` triggers on audit table | Code review: no `DELETE FROM swap_audit_log` in application layer; confirmed in PRD review | Retention period TBD — see Open Questions |
| NFR-9 | Scalability | Schema uses UUIDs as PKs; indexes defined on `shift_roster(shift_date)`, `swap_requests(status)`, `swap_audit_log(swap_request_id, created_at)` | DDL reviewed against data model spec; EXPLAIN ANALYZE on roster query | (Assumption) current org size fits single Postgres instance |
| NFR-10 | Operability / Developer experience | `.env.example` contains every required key (`DATABASE_URL`, `JWT_SECRET_KEY`, `POSTGRES_SCHEMA`, API/UI ports); README covers venv setup, `.env` copy, RDS migration, seed run, demo logins, and two-terminal start in ≤ 15 minutes | Walkthrough by a developer unfamiliar with the repo | (Assumption) target is internal engineering team |

---

## 7. Data & Integrations

### Core Entities (DDL in `target-apps/shift-swap-board/db/sql/`)

| Entity | Key columns | Notes |
|--------|-------------|-------|
| `users` | `id uuid PK`, `username unique`, `password_hash`, `role enum(staff\|floor_lead\|admin)`, `display_name`, `is_active`, `created_at` | Auth principal for all three roles |
| `staff_profiles` | `id uuid PK`, `user_id FK → users unique`, `employee_code varchar(32) unique nullable` | Extended staff metadata; 1-to-1 with users |
| `shift_roster` | `id uuid PK`, `staff_id FK → staff_profiles`, `shift_date date`, `shift_window enum(morning\|afternoon\|full)`, `UNIQUE(staff_id, shift_date, shift_window)` | Authoritative current schedule |
| `floor_lead_weeks` | `id uuid PK`, `week_start date` (Monday), `floor_lead_user_id FK → users`, `UNIQUE(week_start)` | One lead per ISO week |
| `swap_requests` | `id uuid PK`, `offered_shift_id FK → shift_roster`, `offered_by_user_id FK → users`, `status enum(open\|claimed\|approved\|denied\|cancelled)`, `claimed_by_user_id nullable`, `claimed_at nullable`, `decided_by_user_id nullable`, `decided_at nullable`, `decision_note text nullable`, `created_at`, `updated_at` | Central swap lifecycle record |
| `swap_audit_log` | `id uuid PK`, `swap_request_id FK`, `action varchar(64)`, `actor_user_id FK → users`, `detail jsonb nullable`, `created_at timestamptz DEFAULT now()` | Append-only compliance log |

### Indexes
- `shift_roster(shift_date)` — roster date-range queries
- `swap_requests(status)` — filtered swap list
- `swap_audit_log(swap_request_id, created_at)` — per-swap history retrieval

### External Integrations

| System | Integration type | Notes |
|--------|-----------------|-------|
| AWS RDS (PostgreSQL) | SQLAlchemy 2.x sync + psycopg\[binary\]; `POSTGRES_SCHEMA=shift_swap_board` | Shares RDS instance with other target-apps; separate schema namespace |
| Other internal apps (`inventory-app`, `employee-leave-manager`) | Shared JWT pattern only (same `JWT_SECRET_KEY` env var convention) | No cross-app API calls; auth pattern reuse only |
| Streamlit UI | HTTP client to FastAPI on port 8000; no direct DB access from UI | Pattern C; UI imports nothing from `app/` |

---

## 8. Analytics & Observability

**Application Logs**
- FastAPI default access log (method, path, status, duration) written to stdout; captured by host process manager or container runtime.
- Startup check results logged at `INFO` / `ERROR` level from `app/startup_checks.py`.
- No PII (passwords, JWT secrets) written to logs at any level.

**Audit Log (business events)**
- `swap_audit_log` table is the primary compliance and operational record.
- Actions recorded: `created`, `claimed`, `approved`, `denied`, `cancelled`, `roster_updated`.
- Each row includes `actor_user_id`, `detail` (jsonb, e.g., `{"from_status":"claimed","to_status":"approved"}`), and `created_at`.
- `GET /audit` (admin) and `GET /swaps/{id}/audit` (admin or floor_lead) expose this log via API.

**Key Metrics to Monitor** *(Assumption — no APM tool specified)*
- HTTP 4xx/5xx rate by endpoint (alerting threshold TBD with ops team).
- Swap approval latency: time from `claimed_at` to `decided_at` (business KPI, queryable from `swap_requests`).
- Health endpoint availability: external probe on `GET /health` every 60 s.

**Alerts**
- `GET /health` returns 503 → page on-call (implementation via existing monitoring tooling — TBD).
- Swap stuck in `claimed` state > 48 h without decision → dashboarding query; no automated notification in v1 (out of scope).

---

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Race condition: two staff claim the same open swap simultaneously | One claim succeeds, other receives inconsistent state | `swap_requests.status` checked and updated inside a serialisable/row-locked transaction; 409 returned to second claimer |
| Floor lead not assigned for a given week at approve time | Claimed swaps cannot be approved; coverage uncertainty persists | `POST /swaps/{id}/approve` returns 403 with clear message "no floor lead assigned for this week"; admin notified via ops process (no automated alert in v1) |
| Offerer's roster row deleted at approve but accepter insert fails | Offerer loses shift, accepter not assigned — gap in coverage | Atomic transaction with rollback on any error; FR-5 / NFR-5 enforce this; tested in pytest |
| JWT secret misconfiguration (weak or missing) | Tokens forgeable; unauthorised roster changes | `startup_checks.py` fails fast if `JWT_SECRET_KEY` is absent; secret rotation process TBD |
| Seed bcrypt hashes generated with wrong cost or plaintext | Compliance failure; passwords exposed | `verify_seed_bcrypt` pipeline step validates all seed hashes before deployment |
| Streamlit calling API on wrong host/port in production | UI silently broken | `API_BASE_URL` from env; `.env.example` documents it; startup log prints resolved URL |
| Audit rows accidentally deleted (e.g., cascade delete on `swap_requests`) | Compliance gap | No `ON DELETE CASCADE` on `swap_audit_log`; application code has no `DELETE` path for audit rows; reviewed in code review checklist |
| DB schema collision with other target-apps on shared RDS | Data corruption across apps | `POSTGRES_SCHEMA=shift_swap_board` isolates all tables in a dedicated schema; no cross-schema FKs |

---

## 10. Open Questions

| # | Question | Suggested owner |
|---|----------|-----------------|
| 1 | What is the required JWT expiry duration? (e.g., 8 h shift-length aligned, 24 h, or configurable?) | Backend lead / Security |
| 2 | What is the data retention policy for `swap_audit_log`? (Compliance said "will ask" but no period specified.) | Compliance / Legal |
| 3 | Should a denied swap allow the same offerer to immediately re-offer the same shift, or is there a cooldown? (Current design: denied is terminal; new offer allowed immediately.) | Product / Floor Lead stakeholder |
| 4 | When an offerer cancels a claimed swap, should the claimer receive any in-app notification, or is a status change alone sufficient? (v1: status only, per brief.) | Product |
| 5 | Can a roster row be manually edited or deleted by admin after an approved swap (e.g., scheduled day off)? No admin roster-edit endpoint is specified in MVP. | Product / Admin stakeholder |
| 6 | What is the monitoring / alerting toolchain already in use? (Needed to wire up `GET /health` probe and 5xx alerts.) | Infrastructure / Ops |
| 7 | Should `GET /swaps` for a floor lead show *all* claimed swaps for their week(s), or only those pending decision? | Product / Floor Lead stakeholder |
| 8 | Is there a maximum number of open swap offers a single staff member may hold simultaneously? (No limit stated in brief.) | Product |
| 9 | Should the `shift_roster` table be writable only by admin (seed/import), or will there be a future admin UI for roster management beyond seed data? | Product / Admin stakeholder |
| 10 | Are `morning`, `afternoon`, and `full` shift windows fixed for all locations, or should the enum be extensible? | Product / Operations |

---

## 11. Delivery & Client Surface

| Concern | Choice | Implementation notes |
|---------|--------|---------------------|
| Client UI | **Streamlit** (port 8501) | `ui/streamlit_app.py` + `ui/requirements.txt`; implements all five primary journeys per FR-12 |
| API | **FastAPI** under `target-apps/shift-swap-board/` | REST + OpenAPI (auto-generated `/docs`); port 8000 |
| UI location | `ui/streamlit_app.py` | HTTP client (`requests` or `httpx`) to `API_BASE_URL` only; never imports from `app/` |
| Auth for UI | JWT Bearer (HS256) | Streamlit stores token and `role` in `st.session_state`; included as `Authorization: Bearer <token>` on every protected API call |
| Auth for API | `POST /auth/login` → JWT | Same pattern as `inventory-app` / `employee-leave-manager`; `JWT_SECRET_KEY` from env |
| DB connection | SQLAlchemy 2.x sync + psycopg\[binary\] | `POSTGRES_SCHEMA=shift_swap_board`; schema set via `search_path` or table metadata |
| Startup validation | `app/startup_checks.py` | Fails fast with non-zero exit if `DATABASE_URL` is missing, malformed, or DB unreachable |
| Environment config | `.env` (from `.env.example`) | Required keys: `DATABASE_URL`, `JWT_SECRET_KEY`, `POSTGRES_SCHEMA`, `API_PORT` (8000), `STREAMLIT_PORT` (8501) |
| Run command — API | `uvicorn app.main:app --reload --port 8000` | From `target-apps/shift-swap-board/` virtualenv |
| Run command — UI | `streamlit run ui/streamlit_app.py --server.port 8501` | Separate terminal; reads `API_BASE_URL` from env |
| Output directory | `target-apps/shift-swap-board/` | Follows monorepo slug convention |

---

## Appendix: Assumptions

- **JWT expiry** is not specified in the brief; assumed to default to 8 hours (one shift length) unless overridden by a `JWT_EXPIRY_HOURS` env variable.
- **Admin cannot approve swaps** — no brief text grants admin the approve/deny capability; only `floor_lead` role can approve. Admin can seed and manage roster data and read audit logs.
- **Roster rows are created/managed by admin only** in v1; there is no staff-facing shift-creation endpoint.
- **`floor_lead` role users are also schedulable as staff** (they appear in `shift_roster`) but the brief does not explicitly confirm this; assumed true for demo data consistency.
- **Cost factor for bcrypt hashes** is assumed to be ≥ 12, consistent with the organisation's other apps.
- **Performance targets** (500 ms p95) are assumption-based; no load figures were provided.
- **No soft-delete** on `users` or `shift_roster`; `is_active=false` on users is the deactivation mechanism.
- **`week_start` is always a Monday** (ISO week convention); the API should validate this and return 422 if a non-Monday date is supplied to `POST /floor-leads`.
- **Pagination** on `GET /audit` uses `?limit=` as stated; default limit assumed to be 50 if not supplied.
- **`GET /swaps` for staff** returns: all swaps where `offered_by_user_id = me` OR `claimed_by_user_id = me` OR `status = open` (i.e., claimable by anyone). Exact filter semantics to be confirmed (Open Question 7).
- **No email or in-app notification system** exists in v1; status changes are visible only on next page load in Streamlit.
- **Monitoring toolchain** is not specified; `GET /health` is implemented but wiring to an alerting system is deferred (Open Question 6).
- **`decision_note`** on deny is optional (nullable); no minimum length enforced.
- **`shift_roster` row for offerer** is deleted (not soft-deleted) on approval; the swap audit log preserves the historical record.
