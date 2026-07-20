# Team Expense Tracker — Internal API PRD

## 1. Overview

The Finance team requires a lightweight internal REST API that enables employees to log business expenses and gives managers and administrators visibility into spending by team and category. Currently, no standardised system exists for capturing, converting, or approving employee expenses, leading to manual reconciliation effort and a lack of audit accountability.

The proposed solution is a FastAPI service backed by PostgreSQL that covers the full expense lifecycle: submission (with at-submit-time currency conversion using a pre-loaded daily FX snapshot table), admin approval or rejection, manager reporting, and an immutable audit trail. All monetary values are stored and computed using Decimal types to guarantee precision.

The MVP is API-only (no UI, no LLM, no live FX feeds). Authentication uses API keys scoped to manager and admin roles, and per-employee tokens matching the pattern used in existing internal tooling. Receipts, reimbursement disbursement, live exchange rates, and multi-tenancy are explicitly out of scope.

---

## 2. Goals & Success Metrics

| Goal | Metric | Target | Notes |
|------|--------|--------|-------|
| Accurate expense capture | % of submitted expenses with valid USD converted amount stored at submit-time | 100% | Conversion must use snapshot rate valid on the expense date |
| Decimal precision | Count of float-type usages for monetary columns in DB schema and application code | 0 | Enforced via code review and automated lint/test |
| Timely aggregation | P95 latency for monthly-total-per-team query | ≤ 500 ms at 10 k expenses/team/month | Measured under load test |
| Audit completeness | % of status transitions with a corresponding audit log entry | 100% | Verified by integration tests |
| Role-based access control | Unauthorised role actions rejected with HTTP 403 | 100% of cases | Covered by auth test suite |
| Immutability of finalised expenses | Attempts to edit Approved or Rejected expenses return HTTP 409/422 | 100% of cases | Covered by unit + integration tests |

---

## 3. Non-Goals / Out of Scope

- Receipt or file-upload attachment to expenses
- Reimbursement disbursement workflow (only approval status is tracked)
- Live / real-time foreign-exchange rate API integration
- Multi-organisation or multi-tenant isolation
- Any front-end UI (Streamlit, React, or otherwise)
- JWT-based authentication
- Hard deletion of any expense record at any stage
- Email or push notifications for state transitions
- Mobile clients
- Expense policy enforcement (spend limits, category rules) beyond the basic status workflow

---

## 4. Users & Use Cases

| Persona | Need | Primary use case |
|---------|------|------------------|
| Employee | Submit and manage own business expenses before approval | Creates an expense with amount, currency, category, description, and date; can edit or delete (soft) while status is "submitted" |
| Manager | Understand team spending by category and month | Queries the monthly-total endpoint filtered by team ID and month; reads breakdown per category in USD |
| Admin | Govern the expense lifecycle and team structure | Creates / modifies teams; approves or rejects submitted expenses; views audit log for any expense |
| Finance Ops (future) | (Assumption) Export approved expenses for payroll reconciliation | Reads approved expenses list — not in MVP scope but data model must support it |

---

## 5. Functional Requirements

| ID | Description | Priority | Acceptance criteria (Given / When / Then) |
|----|-------------|----------|-------------------------------------------|
| FR-1 | **Submit expense** — An authenticated employee can create an expense with fields: `amount` (Decimal), `currency` (ISO 4217 code), `category` (enum: travel, meals, software, other), `description` (free text), and `expense_date` (calendar date). The system must look up the FX snapshot rate for the expense's currency on `expense_date`, compute `amount_usd` (Decimal), and store both values. Status is set to `submitted`. | P0 | **Given** a valid employee token and a populated FX snapshot for the expense currency on `expense_date`; **When** a POST to `/expenses` is made with all required fields; **Then** HTTP 201 is returned, the new expense record contains non-null `amount_usd` (Decimal, rounded to 2 dp), status = `submitted`, and an audit log entry `{actor, action: created, timestamp}` is persisted. |
| FR-2 | **FX snapshot at submit-time immutability** — The stored `amount_usd` must not change if the FX snapshot table is later updated or the row is re-read. | P0 | **Given** an expense already persisted with `amount_usd = X`; **When** the FX snapshot rate for that currency/date is updated to a different value; **Then** the expense's `amount_usd` remains `X` and is not recomputed on any subsequent read or batch job. |
| FR-3 | **Edit expense** — An authenticated employee can update any mutable field (`amount`, `currency`, `category`, `description`, `expense_date`) of their own expense only while its status is `submitted`. On update, `amount_usd` must be recomputed using the snapshot rate for the new `expense_date`. | P1 | **Given** an expense in `submitted` status owned by the requesting employee; **When** a PATCH to `/expenses/{id}` is made with changed fields; **Then** HTTP 200 is returned, fields are updated, `amount_usd` is recomputed, and an audit entry is written. **And** if the expense status is `approved` or `rejected`, the PATCH returns HTTP 409 and no data is modified. |
| FR-4 | **Soft-delete expense** — An employee may soft-delete their own expense only while status is `submitted`. Soft-deleted records must be excluded from aggregation and manager views but retained in the database and audit log. | P1 | **Given** an expense in `submitted` status; **When** DELETE `/expenses/{id}` is called by the owning employee; **Then** HTTP 204 is returned, `deleted_at` timestamp is set, the record is excluded from all list/aggregate endpoints, and an audit entry is written. **And** DELETE on an `approved` or `rejected` expense returns HTTP 409 and no change occurs. |
| FR-5 | **Admin approve / reject expense** — An authenticated admin can transition an expense from `submitted` to `approved` or `rejected`, supplying an optional `reason` string. Once approved or rejected the expense fields and status are immutable. | P0 | **Given** an expense in `submitted` status; **When** POST `/expenses/{id}/approve` or `/expenses/{id}/reject` is called with a valid admin API key; **Then** HTTP 200 is returned, status is updated, `reason` (if supplied) is stored, an audit log entry with `{actor: admin_id, action, timestamp}` is persisted, and any subsequent attempt to change expense fields returns HTTP 409. |
| FR-6 | **Monthly team aggregation** — An authenticated manager can retrieve the total USD spend for a specified team and calendar month, broken down by category. Only non-deleted, approved expenses are included in totals. | P0 | **Given** a valid manager API key and an existing team with ≥1 approved expense in the requested month; **When** GET `/teams/{team_id}/expenses/summary?year=YYYY&month=MM` is called; **Then** HTTP 200 is returned with a payload containing `{team_id, year, month, categories: [{category, total_usd}], grand_total_usd}` where all values are Decimal strings; and P95 response time is ≤ 500 ms for 10 k qualifying expenses. |
| FR-7 | **Admin team management** — An authenticated admin can create a team (name, optional description) and assign or remove employees from a team. Each employee belongs to exactly one team at a time. | P1 | **Given** a valid admin API key; **When** POST `/teams` with `{name}` is called; **Then** HTTP 201 is returned and the team is retrievable. **And** when PATCH `/teams/{team_id}/members` is called to assign an employee, the employee's `team_id` is updated and any prior team assignment is replaced. |
| FR-8 | **Audit log retrieval** — An authenticated admin can retrieve the full audit trail for a specific expense, ordered by timestamp ascending. Each entry records `expense_id`, `actor_id`, `actor_role`, `action` (created, updated, status_changed, soft_deleted), `from_status`, `to_status`, `timestamp`. | P1 | **Given** a valid admin API key; **When** GET `/expenses/{id}/audit` is called; **Then** HTTP 200 is returned with an ordered list of audit entries; every state transition that occurred on that expense appears exactly once with a non-null timestamp and actor. |
| FR-9 | **Role-based access enforcement** — Employees must not be able to access other employees' expenses, manager aggregation endpoints, or admin actions. Managers must not be able to approve/reject expenses or manage teams. Mismatched roles return HTTP 403. | P0 | **Given** a request authenticated with a role that lacks permission for the target endpoint; **When** that endpoint is called; **Then** HTTP 403 is returned and no data is read or mutated. Covered by a dedicated auth test matrix in the pytest suite. |
| FR-10 | **FX snapshot management** — An admin (or a privileged script) can insert or update daily FX snapshot rows (`currency`, `date`, `rate_to_usd` as Decimal) in the snapshot table. The API must return HTTP 422 with an error message if an expense is submitted for a currency/date combination with no snapshot row. | P1 | **Given** no FX snapshot row exists for `currency=X` on `expense_date=D`; **When** POST `/expenses` is called with that currency and date; **Then** HTTP 422 is returned with `{"detail": "No FX rate available for <X> on <D>"}` and no expense record is created. |

---

## 6. Non-Functional Requirements

| ID | Category | Target | Measurement / verification | Notes |
|----|----------|--------|---------------------------|-------|
| NFR-1 | Security / Auth | Every endpoint requires a valid credential; unauthenticated requests return HTTP 401 | Pytest auth test suite; manual penetration spot-check | API keys and employee tokens must be stored hashed (bcrypt or similar) — never in plaintext (Assumption: hashing algorithm TBD with security review) |
| NFR-2 | Security / Scope isolation | Manager API keys carry only read + aggregation scopes; admin keys carry approve/reject + team management scopes; employee tokens carry only own-expense CRUD | Automated role-matrix tests covering all endpoint × role combinations | Key scopes encoded in DB, not in the key string itself |
| NFR-3 | Data Integrity / Precision | All monetary columns (`amount`, `amount_usd`, `rate_to_usd`, category totals) stored as `NUMERIC(19,4)` in Postgres; all application-layer arithmetic uses Python `Decimal` | Linting rule banning `float` for money fields; schema migration tests; unit tests asserting Decimal types round-trip | (Assumption) precision scale set to 4 dp internally, rounded to 2 dp in API responses |
| NFR-4 | Performance | P95 latency ≤ 500 ms for monthly team aggregation at 10 k expenses/team/month; P95 ≤ 200 ms for single-expense read/write | Locust or pytest-benchmark load test in CI at defined data volume | Composite DB index on `(team_id, expense_date, status, deleted_at)` assumed necessary (Assumption) |
| NFR-5 | Availability | 99.5% uptime during business hours (Assumption: internal SLA, no formal SLA defined in brief) | Uptime monitoring via health-check endpoint `GET /health`; alerting TBD | Single-region deployment assumed for MVP (Assumption) |
| NFR-6 | Scalability | Horizontal scaling must be possible without application-layer state (stateless API processes) | Architecture review; no in-process caching of mutable data | DB connection pooling via PgBouncer or equivalent (Assumption) |
| NFR-7 | Observability | Structured JSON logs for every request (method, path, status, latency, actor_id); separate audit log table in DB | Log aggregation tool TBD; log schema reviewed in code review | No PII (full names, email addresses) in application logs unless required (Assumption) |
| NFR-8 | Compliance / Data retention | Soft-deleted and approved/rejected records retained indefinitely unless a retention policy is later defined; no hard deletes permitted at the application layer | DB-level constraint or trigger preventing DELETE on `expenses` table; integration test asserting absence of hard-delete endpoint | Retention policy owner TBD (Open Question) |
| NFR-9 | Operability | Database schema managed via versioned Alembic migrations; rollback migration must exist for every forward migration | Migration smoke-test in CI pipeline | (Assumption) |
| NFR-10 | Testability | ≥ 80% line coverage across `app/` measured by pytest-cov; all critical paths (submit, approve, aggregate) at 100% branch coverage | Coverage report gate in CI; PR merge blocked below threshold | (Assumption: threshold agreed with engineering lead) |

---

## 7. Data & Integrations

### Core Entities

| Entity | Key fields | Notes |
|--------|-----------|-------|
| `teams` | `id`, `name`, `description`, `created_at` | Soft-delete via `deleted_at` (Assumption) |
| `users` | `id`, `email` (or username), `role` (employee/manager/admin), `team_id` (FK → teams), `token_hash`, `created_at` | Employees belong to exactly one team |
| `api_keys` | `id`, `key_hash`, `role` (manager/admin), `description`, `created_at`, `revoked_at` | Separate table from employee tokens |
| `fx_snapshots` | `id`, `currency` (ISO 4217), `date`, `rate_to_usd` (NUMERIC(19,4)) | Unique constraint on `(currency, date)` |
| `expenses` | `id`, `user_id` (FK), `team_id` (FK, denormalised at submit-time), `amount` (NUMERIC(19,4)), `currency`, `amount_usd` (NUMERIC(19,4)), `category` (enum), `description`, `expense_date`, `status` (enum: submitted/approved/rejected), `reason`, `created_at`, `updated_at`, `deleted_at` | `team_id` denormalised to preserve historical team at time of submission |
| `audit_log` | `id`, `expense_id` (FK), `actor_id`, `actor_role`, `action`, `from_status`, `to_status`, `metadata` (JSONB), `created_at` | Append-only; no updates or deletes |

### External Integrations

- **None in MVP.** FX rates are loaded into `fx_snapshots` via an admin endpoint or database seed script — no third-party FX API is called at runtime.
- Future integration point for payroll/reimbursement system via read-only export endpoint (out of scope for MVP).

### Indexes (Assumed)

- `expenses(team_id, expense_date, status, deleted_at)` — composite index for monthly aggregation query
- `expenses(user_id, status)` — for employee own-expense listing
- `audit_log(expense_id, created_at)` — for audit trail retrieval
- `fx_snapshots(currency, date)` — unique index

---

## 8. Analytics & Observability

**Application Logging**
- Structured JSON logs emitted to stdout on every HTTP request: `{timestamp, request_id, method, path, status_code, latency_ms, actor_id, actor_role}`.
- Errors logged at `ERROR` level with full stack trace and `request_id` for correlation.
- No monetary amounts or PII logged at `INFO` level (Assumption).

**Database Audit Log**
- The `audit_log` table (see §7) serves as the primary audit trail. Every expense state transition triggers an insert.
- The audit log is write-once and must never be pruned by application code.

**Health & Readiness**
- `GET /health` returns `{"status": "ok", "db": "ok/error"}` — used by load balancer and uptime monitors.
- `GET /ready` checks DB connectivity and returns 200 only when the service is fully initialised (Assumption).

**Key Metrics to Instrument** *(log-derived or via Prometheus if adopted later)*
- Expense submission rate (per hour)
- Approval/rejection rate and lag (time from submitted → decision)
- FX-lookup miss rate (HTTP 422 on missing snapshot)
- Monthly aggregation query latency histogram
- Auth failure rate (401/403 per hour)

**Alerting** *(thresholds TBD with engineering/ops)*
- Error rate > 1% of requests over a 5-minute window
- DB query P95 latency > 1 s
- Health check failure for > 2 consecutive minutes

---

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Missing FX snapshot for a currency/date causes expense submission failures | High — employees unable to log expenses | Pre-load snapshots for all expected currencies daily via an automated seed script; FR-10 returns clear 422 with actionable message; admin dashboard (future) to monitor gaps |
| Float arithmetic accidentally introduced for monetary fields | High — silent rounding errors corrupt financial data | Lint rule banning `float` in money context; NUMERIC type enforced in DB schema; PR checklist item; NFR-3 test coverage |
| Incorrect team_id captured at submit-time vs. later team reassignment | Medium — historical reports show wrong team attribution | Denormalise `team_id` onto the expense row at submit-time (FR-1 data model); manager reports query `expenses.team_id`, not current `users.team_id` |
| Aggregation query performance degrades with data growth | Medium — slow reports erode manager trust | Composite index (§7); consider DB-level materialised view or monthly rollup table for future scale; NFR-4 load test gates in CI |
| API key leakage (keys in logs, error messages, or version control) | High — unauthorised access to financial data | Keys stored hashed; log sanitisation; secret scanning in CI pipeline; key rotation endpoint (Assumption) |
| Race condition on concurrent approve + edit of same expense | Medium — data integrity violation | Database-level row locking (`SELECT … FOR UPDATE`) during status transition; optimistic-lock version field (Assumption) |
| Soft-delete bypass via direct DB access | Low — audit circumvention | DB user for application has no DELETE privilege on `expenses` or `audit_log` tables (Assumption) |

---

## 10. Open Questions

| # | Question | Suggested owner |
|---|----------|-----------------|
| 1 | What is the authoritative list of supported currencies for MVP? Is it all ISO 4217 codes or a curated subset? | Finance team / PM |
| 2 | Who is responsible for loading and maintaining the daily FX snapshot table? Is there an internal data pipeline or will admins update it manually? | Finance Ops / Engineering |
| 3 | What is the employee token format and issuance mechanism? ("per-employee token like in our other internal tools" — needs specification for compatibility.) | Platform / Auth team |
| 4 | Are manager API keys scoped to a single team or can a manager key access multiple teams? | Finance team / PM |
| 5 | What data-retention policy applies to audit logs and soft-deleted expenses? Is there a regulatory or internal compliance requirement? | Legal / Finance Ops |
| 6 | Is there a maximum description length or any content-filtering requirement for the `description` field? | PM / Legal |
| 7 | Should the monthly aggregation include expenses in `submitted` (pending) status or only `approved`? The brief implies approved only, but Finance may want a "pending" subtotal. | Finance team |
| 8 | Is key rotation (admin ability to revoke and reissue API keys / employee tokens) required in MVP? | Security / Engineering |
| 9 | What deployment target is assumed — containerised (Docker/K8s), bare VM, internal PaaS? This affects NFR-5 and NFR-6 implementation. | Engineering / DevOps |
| 10 | Should the `reason` field on approval/rejection be mandatory or optional? | PM / Finance team |

---

## 11. Delivery & Client Surface

| Concern | Choice | Implementation notes |
|---------|--------|---------------------|
| Client UI | **API-only (Swagger / OpenAPI)** | Explicitly requested — no UI in MVP; interactive docs served at `/docs` (Swagger UI) and `/redoc` |
| API framework | **FastAPI** under `target-apps/expense-tracker/` | REST + OpenAPI 3.1 auto-generated from route decorators; Pydantic v2 models enforce Decimal types |
| Auth mechanism | **API keys** (manager, admin scopes) + **per-employee tokens** | No JWT; keys and token hashes stored in Postgres; FastAPI dependency injection handles extraction and scope check |
| Database | **PostgreSQL** | All monetary columns as `NUMERIC(19,4)`; Alembic for migrations; async driver (asyncpg) assumed |
| Testing | **pytest** + pytest-asyncio + httpx (async test client) | Coverage gate ≥ 80%; auth matrix tests mandatory; load/benchmark tests for NFR-4 |
| Decimal handling | Python `decimal.Decimal` throughout; **no `float`** for money | Pydantic fields typed as `Decimal`; serialised as strings in JSON responses to avoid client float precision loss |
| Project structure | `app/` — domain logic; `app/routers/` — FastAPI routers; `app/models/` — ORM models; `app/schemas/` — Pydantic schemas; `app/services/` — business logic; `migrations/` — Alembic | UI layer absent by design |
| FX conversion | Implemented as a pure service function in `app/services/fx.py`; no external HTTP call | Reads from `fx_snapshots` table; raises `FXRateNotFound` mapped to HTTP 422 |

---

## Appendix: Assumptions

- **Employee token format** is an opaque bearer token (not JWT) consistent with other internal services; the exact issuance and validation mechanism will be provided by the platform team.
- **Manager keys are team-scoped by default**; if a manager needs cross-team visibility, a separate key or admin role is required. This is unconfirmed — see Open Question 4.
- **Approved-only expenses** are included in monthly aggregation totals; submitted (pending) and rejected expenses are excluded unless the Finance team requests otherwise (Open Question 7).
- **team_id is denormalised onto the expense row** at submit-time so historical reports are unaffected by future team reassignments.
- **Soft-delete applies to teams and users as well** as expenses, via `deleted_at` timestamp columns.
- **NUMERIC(19,4)** precision is sufficient for all expected currency amounts and rates; this covers values up to 999 trillion with 4 decimal places.
- **Alembic** is used for schema migration management with both upgrade and downgrade scripts per migration.
- **asyncpg** is used as the async Postgres driver; SQLAlchemy async session is the ORM layer.
- **No email or webhook notifications** are sent on status transitions in MVP.
- **Single-region, single-instance deployment** assumed for MVP; horizontal scaling design (stateless API) is required but active multi-instance deployment is not a Day 1 requirement.
- **API key rotation / revocation** endpoint is desirable but not confirmed as MVP scope; the data model (`revoked_at` column) must support it.
- **Description field** has a maximum length of 1 000 characters (enforced at API layer) pending confirmation.
- **Row-level locking** (`SELECT FOR UPDATE`) is used during status transitions to prevent race conditions on concurrent approve + edit.
- **The application DB user** is granted only SELECT/INSERT/UPDATE on `expenses` and `audit_log` — no DELETE privilege — to enforce soft-delete at the infrastructure level.
- **Expense `category`** is a Postgres enum or a constrained `VARCHAR` with a check constraint; values are: `travel`, `meals`, `software`, `other`.
- **`/health` and `/ready` endpoints** are unauthenticated to support load-balancer health checks.
