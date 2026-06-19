# IT Asset Lifecycle — Asset Management PRD

## 1. Overview

IT Operations teams routinely lose visibility into hardware and software assets after employee offboarding events, leading to unrecovered laptops, over-allocated license seats, and expired warranties going unnoticed. Finance teams need accurate asset valuation by department but must not be given write access that could corrupt assignment data. The current state relies on manual tracking, which fails at scale.

This product delivers a role-gated IT Asset Lifecycle Management system: a FastAPI backend with a SQLAlchemy data layer, Fernet-encrypted license key storage, and a Streamlit frontend. It covers the full asset lifecycle — procurement intake, assignment to employees, return (with condition capture), retirement, license seat enforcement, and proactive alerting for offboarding gaps, warranty expirations, and license overages. A finance-safe valuation report surfaces department-level asset cost without exposing assignment write operations or raw license keys.

The MVP scope is bounded to a catalog of laptops, monitors, phones, licenses, and miscellaneous assets; single-active-assignment enforcement for non-license assets; seat-limit enforcement for license assets; and a dashboard of actionable alerts. The system is delivered under `target-apps/it-asset-lifecycle/` with seed data included.

---

## 2. Goals & Success Metrics

| Goal | Metric | Target | Notes |
|------|--------|--------|-------|
| Eliminate unrecovered assets after offboarding | Count of inactive employees with active assignments surfaced via alert | 0 unresolved within agreed SLA after offboarding event | Measured via `/alerts/offboarding` response |
| Prevent license over-allocation | Count of license over-allocation violations at assign time | 0 — system rejects assignment at seat limit | Measured by 422 rate on `/assets/{id}/assign` |
| Finance self-service valuation | Finance users can retrieve department valuation without IT involvement | 100% of valuation requests fulfilled via `/reports/valuation-by-department` | No write access granted |
| Warranty visibility | Warranty-expiring assets surfaced proactively | All assets within configurable window (default 30 days) returned in `/alerts/warranty` | Configurable `days` query parameter |
| Audit completeness | Every assign and return event logged | 100% of assignment lifecycle events present in `assignment_history` | Verified via row count parity |
| License key confidentiality | Raw license keys never exposed in API responses | `license_key` field masked to `last4` in all JSON responses | Verified by test suite |

---

## 3. Non-Goals / Out of Scope

- Integration with MDM platforms (Intune, Jamf, or similar)
- Barcode or QR-code scanning for physical check-in/check-out
- Depreciation schedules or book-value calculations
- Procurement purchase-order workflows
- Automated employee deactivation triggers from HR systems
- Multi-tenant or multi-organisation data isolation
- Mobile-native application (iOS/Android)
- Asset image/photo attachments
- Scheduled/automated warranty notification emails or push alerts
- Soft-delete or data anonymisation workflows for GDPR beyond the existing `is_active` flag (see Open Questions)

---

## 4. Users & Use Cases

| Persona | Need | Primary use case |
|---------|------|------------------|
| **Kevin — IT Admin** (`it_admin`) | Full lifecycle control: add assets, assign, return, retire, deactivate employees, view all alerts | Creates a laptop asset, assigns it to a new hire, receives an offboarding alert when the employee is deactivated, marks the asset returned and in-stock |
| **IT Staff** (`it_staff`) | Day-to-day assign/return operations without destructive permissions | Assigns a software license seat to an employee; processes a return with a repair flag; reviews offboarding and warranty alerts |
| **Finance Analyst** (`finance_readonly`) | Read-only access to asset values and department cost roll-up without touching assignments | Pulls valuation-by-department report for quarterly budget review; views asset catalog without seeing full license keys |
| **Anonymous / Monitoring System** (`anonymous`) | Liveness check for load-balancer and CI health probes | Calls `/health` to confirm the service is up and the database is reachable |

---

## 5. Functional Requirements

| ID | Description | Priority | Acceptance criteria (Given / When / Then) |
|----|-------------|----------|---------------------------------------------|
| FR-1 | **Asset Catalog CRUD** — `it_admin` can create, read, update, and retire assets. `POST /assets` for `asset_type=license` requires `seats_purchased > 0`; otherwise returns 422. `it_staff` can read all assets but cannot delete or retire. | P0 | **Given** an authenticated `it_admin` sends `POST /assets` with `asset_type=license` and omits `seats_purchased`, **When** the request is processed, **Then** the API returns HTTP 422 with a descriptive validation error. **Given** `it_staff` sends `DELETE /assets/{id}`, **Then** the API returns HTTP 403. |
| FR-2 | **Single Active Assignment Enforcement** — For non-license assets, at most one active assignment may exist at a time. `POST /assets/{id}/assign` returns HTTP 422 with error body `{"detail": "asset already assigned"}` when an active assignment exists. | P0 | **Given** asset A (laptop) has an active assignment, **When** `it_admin` or `it_staff` calls `POST /assets/{id}/assign` with any `employee_id`, **Then** the API returns HTTP 422. **Given** the existing assignment is returned first, **When** the assign endpoint is called again, **Then** it returns HTTP 201 and creates a new active assignment. |
| FR-3 | **License Seat Limit Enforcement** — For `asset_type=license`, `seats_in_use` equals the count of active assignments for that asset. `POST /assets/{id}/assign` returns HTTP 422 with `{"detail": "no seats available"}` when `seats_in_use >= seats_purchased`. | P0 | **Given** a license asset with `seats_purchased=3` and 3 active assignments, **When** a fourth assign request is submitted, **Then** the API returns HTTP 422. **Given** one assignment is returned, reducing `seats_in_use` to 2, **When** a new assign request is submitted, **Then** it returns HTTP 201. |
| FR-4 | **Assign / Return Workflow** — `POST /assets/{id}/assign` records `assigned_at`, `assigned_by`, sets asset `status=assigned`, and appends to `assignment_history`. `POST /assets/{id}/return` sets `returned_at`, updates asset `status` to `in_stock` or `repair` per request body `condition` flag, records `return_condition_note`, and appends to `assignment_history`. | P0 | **Given** a valid `POST /assets/{id}/assign` request, **When** processed, **Then** an `assignments` row exists with `returned_at IS NULL`, asset `status=assigned`, and one new `assignment_history` row. **Given** a valid `POST /assets/{id}/return` with `condition=repair`, **When** processed, **Then** `assignments.returned_at` is set, asset `status=repair`, and one new `assignment_history` row is appended. |
| FR-5 | **Retire Asset Rule** — `POST /assets/{id}/retire` sets `status=retired` only if there is no active assignment and current `status != assigned`. If blocked, returns HTTP 422. | P0 | **Given** an asset with an active assignment, **When** `it_admin` calls `POST /assets/{id}/retire`, **Then** the API returns HTTP 422. **Given** an asset with `status=in_stock` and no active assignments, **When** the retire endpoint is called, **Then** asset `status` becomes `retired` and HTTP 200 is returned. |
| FR-6 | **Employee Deactivation** — `PATCH /employees/{id}/deactivate` sets `is_active=false` and records `deactivated_at`. It does **not** auto-return any active assignments. Deactivated employees with active assignments appear exclusively in `GET /alerts/offboarding`. | P0 | **Given** employee E has an active laptop assignment, **When** `it_admin` calls `PATCH /employees/{id}/deactivate`, **Then** `is_active=false`, `deactivated_at` is set, the assignment row is unchanged, and `GET /alerts/offboarding` includes employee E with the outstanding asset. |
| FR-7 | **Offboarding, Warranty, and License Overage Alerts** — `GET /alerts/offboarding` returns all inactive employees with at least one active assignment. `GET /alerts/warranty?days=N` returns all assets where `warranty_end_date <= today + N` and `status != retired`. `GET /alerts/license-overages` returns license assets where current `seats_in_use > seats_purchased`. | P0 | **Given** seed data includes 2 inactive employees with active assignments, **When** `GET /alerts/offboarding` is called, **Then** exactly those 2 employees (and their assets) are returned. **Given** `days=30`, **When** `GET /alerts/warranty?days=30` is called, **Then** only assets with `warranty_end_date` within 30 calendar days and `status != retired` are returned. |
| FR-8 | **Finance Read-Only & License Key Masking** — `finance_readonly` users can call all `GET` endpoints and `/reports/valuation-by-department` but receive HTTP 403 on any write endpoint (`POST /assets`, `POST /assets/{id}/assign`, `PATCH`, etc.). All API responses mask `license_key_encrypted`; only `license_key_last4` is included in JSON output. | P0 | **Given** an authenticated `finance_readonly` token, **When** `POST /assets/{id}/assign` is called, **Then** HTTP 403 is returned. **Given** any role calls `GET /assets` and the asset has a license key, **Then** the response JSON contains `license_key_last4` and **never** contains the raw `license_key_encrypted` value. |
| FR-9 | **Valuation by Department Report** — `GET /reports/valuation-by-department` returns an array of `{ department, total_cost, asset_count }` summing `purchase_cost` of all assets with active assignments, grouped by the assigned employee's department. Accessible by `it_admin` and `finance_readonly`. | P0 | **Given** seed data with known per-department assignments, **When** `GET /reports/valuation-by-department` is called, **Then** each department entry's `total_cost` matches the expected sum of `purchase_cost` for actively assigned assets in that department, verified by the test suite. |
| FR-10 | **Role-Based JWT Authentication** — `POST /auth/login` accepts `username` + `password`, validates against `users.password_hash`, and returns a signed JWT containing `user_id` and `role`. All protected endpoints reject requests missing a valid Bearer token with HTTP 401. Endpoints respect role restrictions per the API contract table. | P0 | **Given** valid credentials for an `it_staff` user, **When** `POST /auth/login` is called, **Then** a JWT is returned. **Given** that JWT is presented to `POST /assets`, **Then** HTTP 403 is returned (role not permitted). **Given** no token is presented to `GET /assets`, **Then** HTTP 401 is returned. |
| FR-11 | **Asset Catalog Filters** — `GET /assets` supports query parameters: `type` (asset_type enum), `status` (status enum), and `warranty_expiring_within_days` (integer). Results are filtered server-side; unrecognised filter values return HTTP 422. | P1 | **Given** `GET /assets?type=license`, **When** processed, **Then** only assets with `asset_type=license` are returned. **Given** `GET /assets?warranty_expiring_within_days=30`, **Then** only assets whose `warranty_end_date` falls within 30 days are returned. |
| FR-12 | **Audit / Assignment History Log** — Every assign and return event appends an immutable row to `assignment_history`. The table is append-only (no updates or deletes via the API). | P0 | **Given** 20 seed assignment history rows, **When** one assign and one return operation are performed, **Then** `assignment_history` contains 22 rows and none of the original rows have been modified. |
| FR-13 | **Streamlit Frontend — Role-Gated Views** — The Streamlit app implements: Asset Catalog view (all auth roles), Assign/Return workflow (it_admin, it_staff), Alerts dashboard (offboarding, warranty, license overage), and Finance Valuation view (finance_readonly, it_admin). The app communicates with the FastAPI backend exclusively via HTTP; it never imports from `app/` directly. Role-appropriate navigation is shown based on the JWT role stored in session state. | P1 | **Given** a logged-in `finance_readonly` user in the Streamlit app, **When** the app renders the sidebar, **Then** Assign/Return workflow controls are not visible and Valuation view is accessible. **Given** an `it_admin` user, **Then** all four view sections are accessible. |
| FR-14 | **Seed Data** — The application ships with seed data comprising 25 assets (including 5 license assets with defined seat limits), 12 employees (including 2 inactive employees each with at least one active assignment), and at least 20 `assignment_history` rows. | P1 | **Given** a fresh database initialised with migrations and seed script, **When** `GET /assets` is called, **Then** 25 assets are returned. `GET /alerts/offboarding` returns 2 employees. |

---

## 6. Non-Functional Requirements

| ID | Category | Target | Measurement / verification | Notes |
|----|----------|--------|---------------------------|-------|
| NFR-1 | Performance | P95 API response time ≤ 300 ms for all list endpoints under nominal load | Load test with 50 concurrent users; measure via API timing middleware | (Assumption) — nominal load defined as ≤ 50 concurrent users |
| NFR-2 | Performance | `POST /assets/{id}/assign` seat-check and insert completes within a single serialisable transaction to prevent race conditions | Integration test with concurrent assign requests; verify no over-allocation occurs | Requires DB-level constraint or `SELECT FOR UPDATE` on assignment count |
| NFR-3 | Security / Privacy | License keys stored encrypted at rest using Fernet symmetric encryption; encryption key sourced exclusively from `ASSET_ENCRYPTION_KEY` environment variable; plaintext key never written to DB or logs | Code review; grep for plaintext key in DB fixtures; verify env-var-only key loading | Fernet key must be rotatable without data loss (migration strategy TBD — see Open Questions) |
| NFR-4 | Security / Privacy | JWT tokens signed with HS256 (minimum); secret sourced from environment variable; tokens expire after a configurable TTL (default 8 hours) | Unit test token decode; verify expiry rejection | (Assumption) default TTL = 8 hours |
| NFR-5 | Security / Privacy | `finance_readonly` role must never receive `license_key_encrypted` in any API response; enforced at serialisation layer | Automated test: call all GET endpoints as `finance_readonly`, assert no response body contains the encrypted key field | Must hold even if new endpoints are added |
| NFR-6 | Availability | Service uptime ≥ 99.5% during business hours | Uptime monitoring via `/health` endpoint polling | (Assumption) deployment environment and SLA not yet defined |
| NFR-7 | Scalability | Data model and queries must support ≥ 10,000 assets and ≥ 5,000 employees without query plan degradation | EXPLAIN ANALYZE on filtered `GET /assets` and valuation report with synthetic large dataset | Indexes on `warranty_end_date`, `status`, `asset_type`, `employees.is_active` are specified in DDL |
| NFR-8 | Observability | All API requests logged with: timestamp, method, path, response status, latency, authenticated `user_id` (no PII beyond ID) | Structured JSON logs emitted to stdout; verifiable in CI test run output | (Assumption) log aggregation platform TBD |
| NFR-9 | Observability | Application exposes a `/health` endpoint returning `{"status": "ok", "db": "reachable"}` or `{"status": "degraded", "db": "unreachable"}` with appropriate HTTP status codes | Automated health check in CI pipeline; load-balancer probe | DB ping must not block > 2 s |
| NFR-10 | Compliance / Data Retention | `assignment_history` is append-only; no API endpoint permits update or deletion of history rows | Integration test: attempt direct `DELETE` or `UPDATE` via API; verify 405 / 403 response; DB-level trigger or policy as backstop | (Assumption) retention period policy TBD — see Open Questions |
| NFR-11 | Operability | DDL migrations managed via versioned scripts under `target-apps/it-asset-lifecycle/db/sql/`; seed script is idempotent (re-runnable without duplicate errors) | CI pipeline runs migration + seed twice sequentially; verify no errors on second run | |
| NFR-12 | Security | Passwords stored as bcrypt hashes (cost factor ≥ 12); plaintext passwords never logged | Code review; grep logs during test run | (Assumption) bcrypt selected; library choice TBD |

---

## 7. Data & Integrations

### Core Entities

| Entity | Key Fields | Notes |
|--------|-----------|-------|
| `users` | `id (uuid PK)`, `username`, `password_hash`, `role (enum)`, `is_active` | Roles: `it_admin`, `it_staff`, `finance_readonly` |
| `employees` | `id (uuid PK)`, `full_name`, `email (unique)`, `department varchar(64)`, `manager_id (FK nullable)`, `is_active bool`, `deactivated_at timestamptz` | `deactivated_at` set on PATCH deactivate |
| `assets` | `id (uuid PK)`, `asset_type (enum)`, `manufacturer`, `model`, `serial_number (unique nullable)`, `license_key_encrypted (text nullable)`, `license_key_last4 varchar(4)`, `seats_purchased (int nullable)`, `purchase_date`, `purchase_cost numeric(12,2)`, `warranty_end_date (date nullable)`, `status (enum)`, `created_at`, `updated_at` | `serial_number` not required for licenses; `seats_purchased` required for license type |
| `assignments` | `id (uuid PK)`, `asset_id (FK)`, `employee_id (FK)`, `assigned_at timestamptz`, `returned_at timestamptz nullable`, `assigned_by (FK→users)`, `return_condition_note text nullable`, partial unique index on `(asset_id) WHERE returned_at IS NULL` | Enforces single active assignment at DB level |
| `assignment_history` | Mirrors assign/return event fields; append-only | Audit log; no update/delete via API |

### Indexes (specified in DDL)

- `assets(warranty_end_date, status)` — warranty alert queries
- `assets(asset_type)` — type filter
- `employees(is_active)` — offboarding alert queries

### External Integrations

- **None in MVP scope.** MDM (Intune/Jamf), HR systems, and procurement systems are explicitly out of scope.
- **Fernet encryption** (`cryptography` library): `license_key_encrypted` field encrypted/decrypted using `ASSET_ENCRYPTION_KEY` environment variable. No external KMS in MVP (see Open Questions for key rotation).

### Environment Variables

| Variable | Purpose |
|----------|---------|
| `ASSET_ENCRYPTION_KEY` | Fernet key for license key encryption |
| `DATABASE_URL` | SQLAlchemy connection string |
| `JWT_SECRET` | HMAC secret for JWT signing |
| `JWT_TTL_HOURS` | Token expiry in hours (default: 8) |

---

## 8. Analytics & Observability

**Structured Logging**
- All API requests emit a structured JSON log line to stdout containing: `timestamp`, `method`, `path`, `status_code`, `latency_ms`, `user_id` (authenticated user UUID or `anonymous`).
- No PII (employee name, email, license keys) in log output.

**Health Endpoint**
- `GET /health` performs a lightweight DB ping (`SELECT 1`). Returns `200 {"status": "ok", "db": "reachable"}` on success; `503 {"status": "degraded", "db": "unreachable"}` on failure. No auth required.

**Key Operational Metrics (Assumption — collection mechanism TBD)**
- Rate of 422 responses on `/assets/{id}/assign` — indicates seat-limit or double-assign attempts.
- Count of rows in `GET /alerts/offboarding` — KPI for IT Ops SLA.
- Count of assets in warranty-expiring window — proactive ops metric.
- `assignment_history` row count — monotonically increasing; regression if it decreases.

**Alerting (Assumption)**
- Alert if `/health` returns non-200 for > 2 consecutive minutes.
- Alert if `GET /alerts/license-overages` returns any rows in production (indicates a bug bypassing seat-check logic).

---

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Race condition on concurrent license seat assignments causes over-allocation | High — regulatory / cost exposure from over-allocated paid licenses | Use `SELECT FOR UPDATE` or serialisable transaction isolation on the seat-count check + insert in `POST /assets/{id}/assign`; DB partial unique index as backstop; add concurrent-assign integration test |
| Fernet encryption key loss renders all license keys unrecoverable | High — loss of operational data | Document key rotation procedure; store `ASSET_ENCRYPTION_KEY` in a secrets manager; consider re-encryption migration script for key rotation |
| `finance_readonly` role inadvertently exposed to sensitive write endpoints after future API expansion | Medium — data integrity and compliance risk | Enforce role guard at a middleware/decorator layer checked on every route; add CI test asserting 403 for all write methods when called with `finance_readonly` token |
| Employee deactivation without auto-return creates long-lived orphaned assignments | Medium — asset loss / cost | `GET /alerts/offboarding` surfaces these; recommend IT Ops process to resolve within N days of deactivation (SLA TBD) |
| Seed data containing realistic-looking employee or license data causes data-privacy concerns if committed to a public repo | Low–Medium | Use clearly synthetic names, placeholder emails, and dummy license keys in seed; never use real keys even encrypted |
| Schema drift between SQLAlchemy models and raw DDL under `db/sql/` | Medium — runtime errors | Enforce single source of truth; CI step compares model-generated schema with migration files |

---

## 10. Open Questions

| # | Question | Suggested owner |
|---|----------|-----------------|
| 1 | What is the target deployment environment (Docker Compose, Kubernetes, cloud PaaS)? This affects availability SLA, secrets management, and migration strategy. | IT Ops / DevOps lead |
| 2 | What is the password reset / user management workflow for `users` table? Is there a self-service flow or admin-only creation? | IT Admin / Product owner |
| 3 | Is a Fernet key rotation procedure required at MVP, or is it a post-MVP operational runbook item? | IT Admin / Security |
| 4 | Should `PATCH /employees/{id}/deactivate` send any notification (email, Slack) to the employee's manager or IT Ops team? | Product owner |
| 5 | What data retention policy applies to `assignment_history`? Is there a legal or compliance requirement to retain records for N years? | Legal / Compliance |
| 6 | Are there GDPR or equivalent privacy obligations (e.g., right to erasure for employee records)? The current model has no hard-delete path for employees. | Legal / Compliance |
| 7 | Should the valuation report include assets in `repair` or `retired` status, or only `assigned`? The brief says "assigned assets" — confirming this excludes in-stock and repair. | Finance / Product owner |
| 8 | Is pagination required on `GET /assets` and `GET /employees` for MVP, given a potential 10,000+ asset catalog? | Engineering lead |
| 9 | What is the acceptable SLA for IT Ops to resolve offboarding alerts (inactive employee with active assignment)? This drives alert urgency design. | IT Ops / Kevin |
| 10 | Should `it_staff` be able to view the finance valuation report, or is it strictly `finance_readonly` and `it_admin`? The brief grants `it_admin` access but is silent on `it_staff`. | Product owner |

---

## 11. Delivery & Client Surface

| Concern | Choice | Implementation notes |
|---------|--------|---------------------|
| Client UI | **Streamlit** | Four role-gated sections: Asset Catalog, Assign/Return, Alerts Dashboard, Finance Valuation. Navigation items rendered conditionally based on `role` stored in Streamlit session state. |
| API | **FastAPI** under `target-apps/it-asset-lifecycle/` | Full REST + OpenAPI (Swagger UI at `/docs`). All endpoints per the API contract table in the brief. |
| UI location | `target-apps/it-asset-lifecycle/ui/streamlit_app.py` | Communicates with FastAPI via HTTP client (`httpx` or `requests`). **Never imports** from `app/` directly. |
| Auth for UI | JWT Bearer — same tokens issued by `POST /auth/login` | Streamlit stores JWT in `st.session_state["token"]` and `st.session_state["role"]`. Token is passed as `Authorization: Bearer <token>` header on every API call from the UI. Login form shown when session state has no valid token. |
| API structure | `target-apps/it-asset-lifecycle/app/` | Routers: `auth`, `assets`, `employees`, `alerts`, `reports`. Shared deps: JWT decode middleware, role-permission guard, DB session factory. |
| DB migrations | `target-apps/it-asset-lifecycle/db/sql/` | Versioned SQL DDL scripts; seed script separate and idempotent. |
| Encryption | Fernet via `cryptography` library | `ASSET_ENCRYPTION_KEY` env var; encrypt on write, decrypt on read in service layer; serialisation layer always outputs `license_key_last4` only. |
| Output directory | `target-apps/it-asset-lifecycle/` | All source, migrations, seed, and tests colocated under this path. |

---

## Appendix: Assumptions

- **Deployment environment** is not specified; NFR targets (latency, availability) are set to reasonable defaults and marked accordingly.
- **bcrypt** is assumed as the password hashing algorithm (cost factor ≥ 12). Library not specified in the brief.
- **JWT algorithm** assumed to be HS256 with secret from environment variable; RS256 or asymmetric keys not required for MVP.
- **Default JWT TTL** of 8 hours assumed; configurable via `JWT_TTL_HOURS` env var.
- **Pagination** on list endpoints is not addressed in the brief; assumed not required for MVP but flagged as an open question.
- **Valuation report** covers only assets with `status=assigned` (active assignments), consistent with the phrase "assigned assets" in the brief.
- **`it_staff` cannot access the valuation report** — the brief grants access to `finance_readonly` and `it_admin` only; this is flagged as an open question.
- **`assignment_history`** is populated by the application service layer (not DB triggers) unless a trigger approach is selected by the engineering team.
- **Fernet key rotation** is a post-MVP concern; MVP requires only that the key is env-var-sourced and never hardcoded.
- **Seed data** uses fully synthetic names, emails, and dummy license key values — no real credentials.
- **`DELETE /assets`** is not listed in the API contract; asset removal is handled via the `retire` workflow only. Hard-delete is not supported in MVP.
- **`ASSET_ENCRYPTION_KEY` absence** at startup should cause the application to fail fast with a clear error rather than silently storing plaintext keys.
- **Log aggregation** platform (e.g., CloudWatch, Datadog, ELK) is TBD and not part of the MVP deliverable.
- **Streamlit** runs as a separate process from FastAPI, connecting to the API over localhost or a configured `API_BASE_URL` environment variable.
