# Team Expense Tracker — Internal API PRD

## 1. Overview

The Finance team requires a lightweight internal REST API that allows employees to log business expenses and enables managers and admins to review, approve, and report on those expenses. Today there is no structured system, which makes monthly consolidation manual and error-prone.

The proposed solution is a FastAPI + PostgreSQL service exposing role-scoped endpoints for three actor types: **employees** (submit and edit their own expenses), **managers** (view monthly aggregations per team), and **admins** (manage teams and action approval workflow). Multi-currency input is supported through a pre-loaded daily-rate snapshot table; conversion to USD is locked in at submission time so historical records remain stable. A tamper-evident audit log records every status transition.

There is no UI (Swagger/OpenAPI docs serve as the developer surface), no LLM, and no JWT — authentication is via per-employee tokens and scoped API keys for managers and admins, consistent with the organisation's existing internal tooling conventions.

---

## 2. Goals & Success Metrics

| Goal | Metric | Target | Notes |
|------|--------|--------|-------|
| Employees can submit expenses quickly and correctly | Median time from API call to persisted record | < 200 ms at p95 | Includes FX conversion lookup |
| Monthly team reports are accurate and fast | Response time for monthly aggregation endpoint | < 500 ms for teams with up to 10 000 expenses/month | DB-level aggregation required |
| Financial data integrity | Incidence of float-based rounding errors | 0 | All money stored as `NUMERIC`/`Decimal` |
| Audit coverage | Percentage of expense status transitions with an audit log entry | 100 % | Enforced at service layer |
| Admin workflow adoption | Ratio of expenses reaching a terminal state (approved/rejected) within 30 days | ≥ 95 % | Proxy for process health |
| API reliability | Monthly uptime | ≥ 99.5 % | (Assumption) |

---

## 3. Non-Goals / Out of Scope

- Receipt or file-upload attachment on expenses
- Reimbursement workflow — approval tracking only, no payment integration
- Live or real-time foreign-exchange rate fetching
- Multi-organisation / multi-tenant isolation
- End-user UI (Streamlit, React, or any browser frontend)
- JWT-based authentication
- Hard deletion of any expense that has progressed beyond "submitted"
- Mobile clients
- Email or push notification on status changes (may be considered post-MVP)
- Role hierarchy beyond the three defined actor types (employee, manager, admin)

---

## 4. Users & Use Cases

| Persona | Need | Primary use case |
|---------|------|------------------|
| **Employee** | Log a reimbursable business expense in their home currency | Calls `POST /expenses` with amount, currency, category, description, date; receives a record with the locked-in USD equivalent |
| **Employee** | Correct a mistake before approval | Calls `PATCH /expenses/{id}` while expense is in `submitted` status |
| **Manager** | Understand monthly spend for their team | Calls `GET /teams/{team_id}/report?year=YYYY&month=MM` and receives totals broken down by category in USD |
| **Admin** | Set up a new team and assign members | Calls `POST /teams` then assigns employee records to the team |
| **Admin** | Action an expense (approve or reject) | Calls `POST /expenses/{id}/approve` or `POST /expenses/{id}/reject`; transition is immutable thereafter |
| **Finance auditor** *(read-only, Assumption)* | Review full history of an expense including state changes | Calls `GET /expenses/{id}/audit-log` to retrieve timestamped transitions with actor |

---

## 5. Functional Requirements

| ID | Description | Priority | Acceptance criteria (Given / When / Then) |
|----|-------------|----------|-------------------------------------------|
| FR-1 | **Submit expense** — An authenticated employee can create an expense with fields: `amount` (positive decimal), `currency` (ISO 4217 code), `category` (enum: `travel`, `meals`, `software`, `other`), `description` (free text, max 500 chars), and `expense_date` (past or present date). | P0 | **Given** a valid employee token and a complete, valid request body; **When** `POST /expenses` is called; **Then** HTTP 201 is returned, the expense is persisted with status `submitted`, `original_amount` and `usd_amount` are stored (converted using the snapshot rate for `expense_date`), and no floating-point types appear in the response or database row. |
| FR-2 | **FX conversion at submit-time using snapshot table** — The service looks up the daily rate for `(currency, expense_date)` from an internal `fx_rates` table at the moment of submission. The `usd_amount` is calculated and stored immutably; subsequent updates to `fx_rates` must not alter any existing `usd_amount`. | P0 | **Given** an `fx_rates` row for `(EUR, 2024-06-15)` with rate `1.08`; **When** an employee submits an expense of `EUR 100.00` for `2024-06-15`; **Then** `usd_amount` is stored as `108.00`; **And** if the `fx_rates` row is later updated to `1.09`, a re-fetch of the expense still returns `usd_amount = 108.00`. |
| FR-3 | **Edit expense (submitted only)** — An employee can update `amount`, `currency`, `category`, `description`, or `expense_date` on their own expense while it remains in `submitted` status. Editing recomputes `usd_amount` using the snapshot rate for the (new) `expense_date`. Expenses with status `approved` or `rejected` are immutable. | P0 | **Given** an expense owned by the authenticated employee in `submitted` status; **When** `PATCH /expenses/{id}` is called with valid updated fields; **Then** HTTP 200 is returned with updated values and recomputed `usd_amount`; **And** if the same request is made on an `approved` or `rejected` expense, HTTP 409 (or 422) is returned with an informative error message. |
| FR-4 | **Approve / Reject expense (admin only)** — An admin can transition any `submitted` expense to `approved` or `rejected`. No further status transitions are allowed from either terminal state. | P0 | **Given** an admin API key and an expense in `submitted` status; **When** `POST /expenses/{id}/approve` is called; **Then** the expense status becomes `approved`, HTTP 200 is returned; **And** a subsequent call to approve or reject the same expense returns HTTP 409. **Given** a non-admin credential; **When** the same endpoint is called; **Then** HTTP 403 is returned. |
| FR-5 | **Audit log** — Every transition of an expense's `status` field (including creation as `submitted`) is recorded in an `audit_log` table with: `expense_id`, `from_status` (null on creation), `to_status`, `actor_id`, `actor_role`, and `occurred_at` (UTC timestamp). | P0 | **Given** an expense that has been submitted, then approved; **When** `GET /expenses/{id}/audit-log` is called by an authorized user; **Then** exactly two entries are returned in chronological order — one for creation and one for approval — each with non-null `actor_id`, `actor_role`, and `occurred_at`. |
| FR-6 | **Monthly team aggregation report (manager only)** — A manager can request a monthly report for a team they are associated with, returning the total `usd_amount` per category and an overall team total for the specified year-month. Only `approved` expenses are included. | P0 | **Given** a manager API key scoped to `team_id=5`; **When** `GET /teams/5/report?year=2024&month=6` is called; **Then** HTTP 200 is returned with a breakdown by category (`travel`, `meals`, `software`, `other`) and a `grand_total`, all in USD, computed from approved expenses only; **And** the response time is under 500 ms with 10 000 qualifying rows. |
| FR-7 | **Team and employee management (admin only)** — An admin can create a team (`POST /teams`), list teams (`GET /teams`), and assign an employee to a team (`PUT /employees/{id}/team`). An employee belongs to exactly one team at a time. | P1 | **Given** an admin API key; **When** `POST /teams` is called with a unique `name`; **Then** HTTP 201 is returned and the team is retrievable via `GET /teams`; **And** when `PUT /employees/{id}/team` is called with a valid `team_id`, the employee record reflects the new team; **And** a non-admin credential receives HTTP 403. |
| FR-8 | **Soft delete — never hard-delete a non-submitted expense** — An employee may soft-delete their own expense while in `submitted` status (sets a `deleted_at` timestamp and excludes from normal queries). Approved or rejected expenses must not be deletable by any actor including admin. | P1 | **Given** an expense in `submitted` status; **When** `DELETE /expenses/{id}` is called by the owning employee; **Then** HTTP 204 is returned and the expense is excluded from list queries but remains in the database with a non-null `deleted_at`; **And** the same call on an `approved` or `rejected` expense returns HTTP 409. |
| FR-9 | **Currency validation** — The service rejects expenses submitted in a currency not present in the `fx_rates` snapshot table for the given `expense_date`. | P1 | **Given** no `fx_rates` row for `(XYZ, 2024-06-15)`; **When** `POST /expenses` is called with `currency=XYZ` and `expense_date=2024-06-15`; **Then** HTTP 422 is returned with an error indicating the currency/date pair is unsupported. |
| FR-10 | **Employee expense listing (own only)** — An authenticated employee can list their own expenses with optional filters: `status`, `category`, `year`, `month`. Pagination is supported (`limit`/`offset`). Soft-deleted expenses are excluded by default. | P2 | **Given** a valid employee token; **When** `GET /expenses?status=submitted&month=6&year=2024` is called; **Then** only the calling employee's expenses matching the filter are returned (never another employee's); pagination metadata (`total`, `limit`, `offset`) is included. |

---

## 6. Non-Functional Requirements

| ID | Category | Target | Measurement / verification | Notes |
|----|----------|--------|---------------------------|-------|
| NFR-1 | **Performance** | p95 latency ≤ 200 ms for write endpoints; ≤ 500 ms for aggregation report | Load test via `pytest` + `httpx` or `locust` against staging with 10 000 rows | Aggregation must use DB-level `SUM` with indexed `team_id`, `status`, `expense_date` |
| NFR-2 | **Data Integrity — Decimal** | Zero floating-point types used for monetary values anywhere in the stack | Code review + automated test asserting `isinstance(value, Decimal)` on all money fields; Postgres column type must be `NUMERIC(19,4)` | (Assumption: 4 decimal places sufficient for all supported currencies) |
| NFR-3 | **Security — Authentication** | All endpoints require a valid credential; unauthenticated requests return HTTP 401 | pytest integration tests cover missing, expired, and wrong-scope tokens | Employee per-token auth; manager and admin scoped API keys; no JWT |
| NFR-4 | **Security — Authorisation** | Employees cannot read or mutate other employees' expenses; managers cannot action approvals; role violations return HTTP 403 | Automated tests for each cross-role scenario | Scope enforcement at route/dependency layer in FastAPI |
| NFR-5 | **Availability** | ≥ 99.5 % uptime | Uptime monitoring (e.g., internal health-check endpoint) | (Assumption) |
| NFR-6 | **Scalability** | Monthly aggregation query must perform within SLA at 10 000 expenses/team/month; system should support up to 50 teams and 500 employees without schema changes | Explain-plan review; index on `(team_id, status, expense_date)` verified | (Assumption: upper bound based on internal headcount) |
| NFR-7 | **Observability** | Structured JSON logs for every request (method, path, status code, latency, actor_id); audit log entries counted in application metrics | Log output verified in test and staging; alerting on 5xx rate > 1 % | (Assumption) |
| NFR-8 | **Compliance / Data Retention** | Soft-deleted and terminal-state expenses retained indefinitely (no purge); audit log rows never deleted | Verified by absence of any `DELETE` path for non-submitted records in codebase and tests | Aligns with brief requirement |
| NFR-9 | **Operability** | Database migrations managed via Alembic (or equivalent); rollback scripts provided for each migration | Migration files reviewed in CI; rollback tested in staging | (Assumption) |
| NFR-10 | **Test Coverage** | ≥ 80 % line coverage across `app/` measured by `pytest-cov`; all FR acceptance criteria have corresponding integration tests | CI pipeline enforces coverage gate | (Assumption: 80 % threshold) |

---

## 7. Data & Integrations

### Core Entities

| Entity | Key fields | Notes |
|--------|-----------|-------|
| `teams` | `id`, `name`, `created_at` | Soft-delete via `deleted_at` (Assumption) |
| `employees` | `id`, `name`, `team_id` (FK), `token_hash`, `created_at` | One team at a time; token stored hashed |
| `expenses` | `id`, `employee_id` (FK), `team_id` (denormalised for query performance), `original_amount NUMERIC(19,4)`, `currency CHAR(3)`, `usd_amount NUMERIC(19,4)`, `category ENUM`, `description VARCHAR(500)`, `expense_date DATE`, `status ENUM(submitted,approved,rejected)`, `deleted_at`, `created_at`, `updated_at` | `usd_amount` immutable after set |
| `fx_rates` | `currency CHAR(3)`, `rate_date DATE`, `usd_rate NUMERIC(19,6)`, `loaded_at` | Composite PK `(currency, rate_date)`; populated by admin tooling or script (out of scope for MVP) |
| `audit_log` | `id`, `expense_id` (FK), `from_status`, `to_status`, `actor_id`, `actor_role`, `occurred_at TIMESTAMPTZ` | Append-only; no updates or deletes |
| `api_keys` | `id`, `key_hash`, `role ENUM(manager,admin)`, `owner_label`, `created_at`, `revoked_at` | Manager keys scoped to one or more teams (Assumption) |

### External Integrations

- **None in MVP.** The `fx_rates` table is populated by a manual or scripted bulk-load process (mechanism TBD — see Open Questions).
- No live FX API, no email service, no message broker in scope.

### API Surface

- **FastAPI** application located at `target-apps/expense-tracker/`
- OpenAPI/Swagger docs auto-generated and served at `/docs`
- Versioning prefix: `/api/v1/` (Assumption)

---

## 8. Analytics & Observability

- **Structured request logs**: every inbound request logged as JSON with `request_id`, `method`, `path`, `status_code`, `latency_ms`, `actor_id`, `actor_role`. Emitted to stdout for log aggregation by the host platform.
- **Audit log** (see FR-5) acts as the primary business event log; queryable via API and directly in Postgres for finance auditors.
- **Health endpoint**: `GET /health` returns 200 + `{"status": "ok", "db": "ok"}` — used by load balancer and uptime monitoring.
- **Application metrics** (Assumption): Prometheus-compatible `/metrics` endpoint exposing request count, latency histograms, and `audit_log` row count. Actual scraping setup is out of scope for MVP.
- **Alerts** (Assumption): Operator-defined alert if HTTP 5xx rate exceeds 1 % over a 5-minute window; alert if aggregation query exceeds 1 second.
- **Slow-query logging**: Postgres `log_min_duration_statement` set to 500 ms in all non-development environments.

---

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| FX snapshot missing for a submitted expense's currency/date | Employee cannot submit expense; blocker | Validate at submission time (FR-9); provide admin endpoint or script to bulk-load `fx_rates`; document gap |
| Decimal precision loss through ORM or serialisation | Silent financial inaccuracy | Enforce `NUMERIC(19,4)` at DB; use Python `Decimal` throughout; Pydantic validators reject `float`; automated test (NFR-2) |
| Race condition on status transitions (duplicate approve calls) | Expense moves to terminal state twice, inconsistent audit log | Use DB-level row locking (`SELECT FOR UPDATE`) or optimistic concurrency check (`expected_status` param) before update |
| Manager API key scoped incorrectly — sees other teams' data | Data confidentiality breach | API key record stores allowed `team_id` list; enforced at query layer; integration tests cover cross-team access |
| Aggregation performance degrades as expenses scale | SLA breach on report endpoint | Composite index on `(team_id, status, expense_date)`; query uses DB-level `SUM`; monitor with `EXPLAIN ANALYZE` in CI |
| `fx_rates` table updated retroactively, expectation of updated `usd_amount` | Finance confusion | Document and enforce immutability of `usd_amount` at service layer; admin tooling shows original rate used (stored or derivable from original/usd amounts) |
| Token or API key leaked | Unauthorised access | Keys stored hashed; short token rotation policy recommended (Assumption); revocation endpoint for admin |

---

## 10. Open Questions

| # | Question | Suggested owner |
|---|----------|-----------------|
| 1 | How are `fx_rates` rows loaded into the snapshot table? Manual CSV upload by admin, a scheduled script, or a one-time seed? What is the refresh cadence? | Finance team + Backend lead |
| 2 | What happens when an employee submits an expense for a past date where no FX rate exists (e.g., weekend, holiday)? Should the service fall back to the nearest available rate, or hard-reject? | Finance team |
| 3 | Are manager API keys scoped to a specific team, or can a manager see all teams? | Finance team / Security owner |
| 4 | Should employees be able to view the status of their own expenses after submission (FR-10 covers listing, but is a single `GET /expenses/{id}` also needed)? | Product owner |
| 5 | Is there a required retention period or archival policy for audit logs and approved expenses (e.g., 7-year accounting rule)? | Legal / Compliance |
| 6 | What is the onboarding path for new employees — who creates their token, and what is the rotation/revocation process? | IT / Security owner |
| 7 | Should the admin be able to list or search all expenses across all teams, or only within specific team scopes? | Finance team |
| 8 | Is a `reason` field required when rejecting an expense, and should it be surfaced to the employee? | Finance team |
| 9 | Are there maximum or minimum expense amount limits enforced by business policy? | Finance team |
| 10 | What PostgreSQL version and hosting environment will be used (managed cloud, on-prem)? Affects migration tooling and `NUMERIC` dialect. | DevOps / Backend lead |

---

## 11. Delivery & Client Surface

| Concern | Choice | Implementation notes |
|---------|--------|---------------------|
| Client UI | **API-only (Swagger / OpenAPI)** | Brief explicitly states no UI. `/docs` and `/redoc` served by FastAPI for developer use |
| API framework | **FastAPI** under `target-apps/expense-tracker/` | REST + OpenAPI 3.x auto-generated |
| Database | **PostgreSQL** | All monetary columns `NUMERIC(19,4)`; migrations via Alembic (Assumption) |
| Auth — employees | **Per-employee bearer token** | Stored as hashed value in `employees` table; passed as `Authorization: Bearer <token>` header |
| Auth — managers | **Scoped API key** | Passed as `X-Api-Key` header; role=`manager` enforced at dependency layer |
| Auth — admins | **Scoped API key** | Passed as `X-Api-Key` header; role=`admin`; higher privilege scope than manager |
| JWT | **Not used** | Explicitly out of scope per brief |
| Testing | **pytest** | Integration tests via `httpx` + FastAPI `TestClient`; `pytest-cov` coverage gate ≥ 80 % |
| No LLM | Confirmed | No AI/ML components anywhere in the stack |

---

## Appendix: Assumptions

- ISO 4217 three-letter codes are used for all currencies; the `fx_rates` table defines the authoritative list of supported currencies.
- `NUMERIC(19,4)` is sufficient precision for all supported currencies; `fx_rates.usd_rate` uses `NUMERIC(19,6)` to preserve rate precision before rounding to 4 d.p. on the stored `usd_amount`.
- `usd_amount` is rounded using `ROUND_HALF_UP` (banker's rounding variant TBD — to be confirmed with Finance).
- The API versioning prefix is `/api/v1/`; breaking changes will increment the version.
- Manager API keys are scoped to one or more specific teams; a manager cannot access another team's data.
- Employees belong to exactly one team at a time; historical team membership is not tracked (no SCDs).
- An admin creating a team or reassigning an employee is also recorded in the audit log under a generic `team_management` category (separate from expense audit log).
- Token rotation and revocation for employee tokens is handled outside this service (existing internal tooling).
- Prometheus-compatible `/metrics` endpoint is desirable but not required for MVP launch.
- Database hosting environment, PostgreSQL version, and Alembic as migration tool are assumed; to be confirmed with DevOps.
- 80 % pytest line coverage is the CI gate threshold.
- 99.5 % monthly uptime is the availability target.
- Upper bound of ~50 teams and ~500 employees is assumed based on typical internal headcount for this type of organisation.
- `expense_date` must not be a future date (enforced by validator) — assumption based on business-expense conventions; to be confirmed.
- Soft-delete on the `teams` entity follows the same pattern as expenses (no hard deletes) — assumption for consistency.
