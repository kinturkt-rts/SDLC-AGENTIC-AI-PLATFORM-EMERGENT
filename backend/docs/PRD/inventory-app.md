# Inventory Desk — Product Requirements Document

## 1. Overview

Inventory Desk is a minimal, production-shaped REST API that enables a small warehouse team to manage a product catalog and track real-time stock levels. The shop manager (admin role) owns the catalog structure — creating categories and products, adjusting prices, and removing zero-stock items — while staff members can browse inventory and record stock movements such as sales and restocks. All interaction is via the documented REST API (Swagger UI) with no browser front-end in the MVP.

The primary purpose of this application is to serve as an end-to-end SDLC showcase, exercising the full pipeline from product definition through database design, backend development, and automated QA. It is deliberately minimal but real: persisted data, JWT-based authentication, role enforcement, and transactional stock logic are all required from day one.

The application is built with Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.x, and Postgres, deployed under `target-apps/inventory-app/`. A seeded admin and staff user enable immediate demo and testing. The final `handoff_json` must include a `deploymentHandoff` block for the downstream devops-agent.

---

## 2. Goals & Success Metrics

| Goal | Metric | Target | Notes |
|------|--------|--------|-------|
| Functional login and role enforcement | Auth tests pass: admin full access, staff restricted, anonymous blocked | 100 % of defined auth test cases green | Verified by pytest suite |
| Complete CRUD for catalog entities | All 13 API contracts return correct status codes and payloads | 0 schema or status-code mismatches in QA run | Verified by TestClient |
| Transactional stock accuracy | `adjust-stock` atomically updates `qty_on_hand` and inserts `stock_movements` row | No qty drift detected across 1 000 sequential calls in load test | Checked via movement-history sum |
| Negative-stock prevention | `adjust-stock` with result < 0 returns HTTP 422 | 100 % of negative-result attempts rejected | pytest negative-stock test |
| Delete guard | `DELETE /products/{id}` returns 409 when `qty_on_hand > 0` | 100 % enforcement; 204 only when qty = 0 | pytest delete-blocked test |
| Pagination shape | Every list endpoint returns `{items, total, limit, offset}` | Schema validation passes for all list responses | Pydantic response model check |
| SDLC artefact completeness | database-agent SQL + seed + HANDOFF.md; developer-agent README + curl examples; handoff_json with deploymentHandoff | All artefacts present and parseable at project close | Manual artefact review |

---

## 3. Non-Goals / Out of Scope

- Streamlit, React, or any browser UI (deferred to a future phase)
- OAuth 2.0, OpenID Connect, or SSO integration
- Redis-backed sessions or token revocation lists
- Password-reset / email notification flows
- AWS Bedrock, S3, or any cloud-managed AI/ML service
- Docker / container orchestration (delegated to devops-agent in a later pipeline stage)
- Multi-tenancy or multi-warehouse support
- Soft-delete or audit log beyond `stock_movements`
- User management endpoints (create/update/deactivate users via API) — users are seeded in dev SQL only

---

## 4. Users & Use Cases

| Persona | Need | Primary use case |
|---------|------|------------------|
| Admin (shop manager) | Maintain accurate product catalog and pricing; remove obsolete SKUs | Signs in → creates/updates categories and products → adjusts stock → deletes zero-qty products |
| Staff (warehouse worker) | See current inventory at a glance; record daily sales and restocks | Signs in → lists products (with low-stock filter) → posts adjust-stock movement → reviews movement history |
| Anonymous / health-check caller | Confirm service is live (load balancer, monitoring agent) | Calls `GET /health` without credentials; expects `{"status":"ok"}` |
| Developer / Demo attendee | Explore the API surface interactively via Swagger UI | Opens `/docs`; authenticates via Authorize button; exercises all endpoints |

---

## 5. Functional Requirements

| ID | Description | Priority | Acceptance criteria (Given / When / Then) |
|----|-------------|----------|-------------------------------------------|
| FR-1 | **Health endpoint** — `GET /health` returns service status with no authentication required. | P0 | **Given** no `Authorization` header, **When** `GET /health` is called, **Then** HTTP 200 with body `{"status":"ok","service":"inventory-desk"}` is returned within 500 ms. |
| FR-2 | **JWT login** — `POST /auth/login` validates username + password and issues a signed JWT. | P0 | **Given** valid seeded credentials `{username, password}`, **When** `POST /auth/login` is called, **Then** HTTP 200 with `{access_token, token_type:"bearer", role, expires_in}` is returned; token is HS256-signed with `JWT_SECRET_KEY`; wrong password returns 401; `is_active=false` user returns 401. |
| FR-3 | **Role-based access control** — protected routes enforce admin vs. staff permissions. | P0 | **Given** a staff JWT, **When** `POST /categories` is called, **Then** HTTP 403 is returned. **Given** no token, **When** any protected route is called, **Then** HTTP 401 is returned. **Given** an admin JWT, **When** the same admin-only route is called, **Then** the request succeeds. |
| FR-4 | **Category CRUD** — admin can create, read, update categories; staff can read only. | P0 | **Given** an admin JWT, **When** `POST /categories` with `{name}` is called, **Then** HTTP 201 is returned with a new category including auto-generated slug (if omitted) and UUID. **When** `PATCH /categories/{id}` uses a slug already in use, **Then** HTTP 409 is returned. `GET /categories/{id}` returns `product_count`. |
| FR-5 | **Product CRUD** — admin can create, read, update, and delete products; staff can read only. | P0 | **Given** an admin JWT, **When** `POST /products` references an unknown `category_id`, **Then** HTTP 404. **When** `POST /products` uses a duplicate `sku`, **Then** HTTP 409. `PATCH /products/{id}` may update `name`, `price`, `category_id` but never `qty_on_hand` directly. `DELETE /products/{id}` returns 204 when `qty_on_hand=0`, 409 otherwise. |
| FR-6 | **Adjust-stock transaction** — `POST /products/{id}/adjust-stock` atomically updates `qty_on_hand` and inserts a `stock_movements` row; available to admin and staff. | P0 | **Given** a valid JWT (admin or staff), **When** `POST /products/{id}/adjust-stock` with `{delta, reason, note?}` is called, **Then** `qty_on_hand` is incremented by `delta` and a `stock_movements` row is inserted with `performed_by` set to the caller's user ID, both in one transaction. **When** the resulting `qty_on_hand` would be < 0, **Then** HTTP 422 is returned and neither the product row nor the movement row is modified. |
| FR-7 | **Stock movement history** — `GET /products/{id}/movements` returns paginated history newest-first for admin and staff. | P1 | **Given** a valid JWT, **When** `GET /products/{id}/movements` is called, **Then** HTTP 200 with `{items, total, limit, offset}` where items are ordered by `created_at DESC`. Pagination honours `?limit=` and `?offset=` query params. |
| FR-8 | **Product list filtering** — `GET /products` supports filtering by `category_id`, `sku`, and `low_stock=true` (qty ≤ 5). | P1 | **Given** a valid JWT, **When** `GET /products?low_stock=true` is called, **Then** only products with `qty_on_hand <= 5` are returned in the `items` array. Combining filters is additive (AND). Response shape is `{items, total, limit, offset}`. |
| FR-9 | **Pagination on all list endpoints** — `/categories` and `/products` support `?limit=` and `?offset=` and return the standard envelope. | P1 | **Given** a valid JWT, **When** any list endpoint is called with `?limit=5&offset=10`, **Then** at most 5 items are returned and `total` reflects the full unfiltered (or filtered) count, not just the page size. |
| FR-10 | **Seeded users and dev documentation** — database-agent provides DDL, seed SQL with hashed passwords, and HANDOFF.md; developer-agent provides README with curl login examples and local/AWS run sections. | P0 | **Given** a fresh Postgres schema `inventory_app`, **When** DDL + seed SQL are applied, **Then** the two seed users (`admin/Admin123!`, `staff/Staff123!`) can authenticate via `POST /auth/login`. README curl examples execute successfully against a locally running instance. `handoff_json` contains a `deploymentHandoff` key. |
| FR-11 | **Password hashing** — passwords are never stored in plaintext; bcrypt via passlib is used. | P0 | **Given** the `users` table, **When** inspected directly in Postgres, **Then** no row's `password_hash` column contains a plaintext password; all values are valid bcrypt hashes verifiable by passlib `verify()`. |
| FR-12 | **Inactive user block** — a user with `is_active=false` cannot authenticate. | P1 | **Given** a user row with `is_active=false`, **When** `POST /auth/login` is called with correct credentials, **Then** HTTP 401 is returned. |

---

## 6. Non-Functional Requirements

| ID | Category | Target | Measurement / verification | Notes |
|----|----------|--------|---------------------------|-------|
| NFR-1 | Security | Passwords stored as bcrypt hashes; JWT signed HS256 with secret from env; secret never hardcoded | Code review + passlib verify in test; `JWT_SECRET_KEY` absent from source files (grep CI check) | `JWT_SECRET_KEY` loaded via pydantic-settings from env / `.env` |
| NFR-2 | Security | 401 on missing/invalid/expired token; 403 on insufficient role; no sensitive data in error bodies | pytest auth suite covering all negative paths | Token expiry default 60 min (configurable via `JWT_EXPIRE_MINUTES`) |
| NFR-3 | Performance | `GET /products` (≤ 1 000 rows) responds in < 300 ms p95 on local Postgres | Manual timing or pytest-benchmark run during QA | (Assumption) — no explicit SLA in brief |
| NFR-4 | Availability | Service restarts within 30 s on crash (process supervisor or platform restart policy) | Observed during devops-agent phase | (Assumption) — target availability ≥ 99 % in production |
| NFR-5 | Scalability | Schema and ORM designed for single-instance Postgres with connection pooling via SQLAlchemy; no shared mutable state in application layer | Code review: no module-level mutable caches | Horizontal scaling deferred; foundation must not preclude it |
| NFR-6 | Observability | All unhandled exceptions logged with stack trace at ERROR level; all requests logged at INFO with method, path, status code, and latency | Log output visible in stdout during pytest run; spot-check during demo | (Assumption) — structured JSON logging preferred but not mandated in brief |
| NFR-7 | Compliance / Data retention | `stock_movements` rows are append-only (no DELETE or UPDATE exposed via API); DDL should not include a delete route for movements | Verified by absence of any `DELETE /movements` endpoint; FK `ON DELETE CASCADE` from products reviewed | Movements cascade-delete only when parent product is deleted (qty must be 0 first) |
| NFR-8 | Operability | `.env.example` present with all required keys; README documents local setup in ≤ 5 commands | Reviewer can stand up app from README alone on a clean machine | Keys: `DATABASE_URL`, `POSTGRES_SCHEMA`, `JWT_SECRET_KEY`, `JWT_EXPIRE_MINUTES`, `PORT` |
| NFR-9 | Testability | pytest suite covers: login (admin + staff), role 403, adjust-stock qty update, negative-stock 422, delete blocked (qty > 0), pagination shape, 401 without token | `pytest` exits 0 with all test cases passing; coverage ≥ 80 % of `app/` lines | (Assumption) on coverage threshold |
| NFR-10 | Data integrity | `qty_on_hand` never goes negative; `adjust-stock` uses a database transaction (SELECT FOR UPDATE or equivalent) | Concurrent test: two simultaneous depleting adjusts on qty=1 → exactly one succeeds, one returns 422 | (Assumption) — serialisation strategy left to developer-agent |

---

## 7. Data & Integrations

### Core Entities (Postgres schema `inventory_app`)

| Entity | Key columns | Notes |
|--------|-------------|-------|
| `users` | `id uuid PK`, `username text UNIQUE`, `password_hash text`, `role enum(admin,staff)`, `is_active bool`, `created_at timestamptz` | Seeded in dev SQL only; no user-management API in MVP |
| `categories` | `id uuid PK`, `name text(1–80)`, `slug text UNIQUE`, `created_at timestamptz` | Slug auto-generated from name if not supplied |
| `products` | `id uuid PK`, `category_id uuid FK→categories ON DELETE RESTRICT`, `sku text UNIQUE`, `name text(1–120)`, `unit_price numeric(10,2) ≥ 0`, `qty_on_hand int ≥ 0 DEFAULT 0`, `created_at/updated_at timestamptz` | `qty_on_hand` mutated only via adjust-stock |
| `stock_movements` | `id uuid PK`, `product_id uuid FK→products ON DELETE CASCADE`, `delta int`, `reason enum(sale,restock,adjustment)`, `note text(max 500) nullable`, `performed_by uuid FK→users nullable`, `created_at timestamptz` | Append-only; no update/delete API |

### File Layout

| Path | Owner | Contents |
|------|-------|----------|
| `target-apps/inventory-app/db/sql/` | database-agent | DDL migrations, seed SQL (dev only) |
| `target-apps/inventory-app/db/HANDOFF.md` | database-agent | Schema notes, seed instructions, open items for developer-agent |
| `target-apps/inventory-app/app/routers/` | developer-agent | `auth.py`, `health.py`, `categories.py`, `products.py` |
| `target-apps/inventory-app/app/models/` | developer-agent | SQLAlchemy ORM models |
| `target-apps/inventory-app/app/schemas/` | developer-agent | Pydantic v2 request/response models |
| `target-apps/inventory-app/app/services/auth.py` | developer-agent | JWT encode/decode, password verify |
| `target-apps/inventory-app/app/dependencies.py` | developer-agent | `get_current_user`, `require_admin` FastAPI dependencies |
| `target-apps/inventory-app/.env.example` | developer-agent | All required env keys with placeholder values |
| `target-apps/inventory-app/README.md` | developer-agent | Setup, curl examples, local + AWS sections |

### External Integrations

- **Postgres** — sole external dependency; connection via `DATABASE_URL` env var using SQLAlchemy 2.x sync engine + psycopg driver; `search_path` set to `inventory_app` schema.
- No third-party APIs, message queues, object storage, or caching layers in MVP.

---

## 8. Analytics & Observability

| Concern | Approach |
|---------|----------|
| Request logging | FastAPI middleware logs method, path, status code, and elapsed ms to stdout on every request |
| Error logging | Unhandled exceptions caught by global exception handler; logged at ERROR with full traceback; safe error message returned to client (no stack trace in response body) |
| Auth events | Failed login attempts (401/403) logged at WARNING with username (not password) and remote IP |
| Stock movement audit | `stock_movements` table itself is the audit log; `performed_by` links action to user; `GET /products/{id}/movements` surfaces history |
| Health signal | `GET /health` usable as liveness probe by load balancer or uptime monitor |
| Test observability | pytest output captures log lines; failing tests surface log context for diagnosis |
| Future (out of scope now) | Structured JSON logs, distributed tracing, Prometheus metrics — recommended for devops-agent phase |

---

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Race condition on `adjust-stock` causes qty to go negative | Data integrity violation; business loss | Use `SELECT … FOR UPDATE` or atomic `UPDATE products SET qty_on_hand = qty_on_hand + $delta WHERE id=$id AND qty_on_hand + $delta >= 0` with row-count check; wrap in explicit transaction |
| Seed credentials left in production database | Security breach | Document prominently in README and HANDOFF.md that seed SQL is dev-only; seed file excluded from production migration path; warn in `.env.example` |
| `JWT_SECRET_KEY` accidentally committed to source control | Token forgery; full account takeover | `.env` in `.gitignore`; `.env.example` uses placeholder; CI grep check for hardcoded secrets |
| Slug collision on category rename/create | 409 errors confusing users | Auto-slugify is deterministic; PATCH validates uniqueness before write; 409 response includes conflicting slug |
| `ON DELETE RESTRICT` on `category_id` blocks category deletion | Admin confusion | Document in README and Swagger description; expose `product_count` on `GET /categories/{id}` so admin can see dependency before attempting delete |
| SQLAlchemy session leaks under test | Flaky tests; connection pool exhaustion | Use per-test transaction rollback fixture; close session in `finally` block |
| pytest targeting production DB | Data loss in shared environment | `DATABASE_URL` for tests points to a separate test schema or local Postgres; documented in README |

---

## 10. Open Questions

| # | Question | Suggested owner |
|---|----------|-----------------|
| 1 | What is the default page size (`limit`) for list endpoints when the query param is omitted — e.g. 20 or 50? | PM / developer-agent |
| 2 | Should slug auto-generation handle Unicode/accented characters (transliteration) or reject non-ASCII names? | PM |
| 3 | Is `performed_by` nullable to support system-generated movements (e.g. bulk import), or should it always be required when an API caller is present? | PM / developer-agent |
| 4 | What token expiry should be used in production, and will refresh tokens be needed before the devops-agent phase? | PM / security reviewer |
| 5 | Should `DELETE /products/{id}` also cascade-delete the product's `stock_movements` (currently yes via FK) — is losing movement history acceptable on product removal? | PM |
| 6 | Is there a maximum `delta` value (positive or negative) that should be validated on adjust-stock, or is any integer valid as long as qty_on_hand ≥ 0 after the operation? | PM |
| 7 | Should the `GET /products` list include `qty_on_hand` in the summary item, or only in the detail endpoint? | PM / developer-agent |
| 8 | What Postgres version is targeted in the production environment (relevant for UUID generation strategy and `timestamptz` defaults)? | devops-agent |
| 9 | Are there any data-retention requirements for `stock_movements` (e.g. purge after N months)? | PM / compliance |
| 10 | Should the `handoff_json` `deploymentHandoff` block include a specific cloud target (e.g. AWS ECS, EC2, Lambda) or remain cloud-agnostic? | PM / devops-agent |

---

## 11. Delivery & Client Surface

| Concern | Choice | Implementation notes |
|---------|--------|---------------------|
| Client UI | API-only (Swagger / OpenAPI) | MVP explicitly excludes any browser UI; Swagger UI at `/docs` is the demo surface; ReDoc available at `/redoc` |
| API framework | FastAPI under `target-apps/inventory-app/` | Auto-generates OpenAPI 3.x spec; Swagger UI enabled in dev/demo; should be disabled or restricted in production |
| API base path | `/` (no version prefix in MVP) | Version prefix (`/v1/`) recommended for production but out of scope |
| Auth for API | JWT Bearer — `Authorization: Bearer <token>` | HS256 signed; `JWT_SECRET_KEY` from env; `JWT_EXPIRE_MINUTES` configurable (default 60) |
| DB access | SQLAlchemy 2.x sync engine + psycopg; SessionLocal from `_template` pattern | `search_path` set to `inventory_app`; connection string from `DATABASE_URL` env var |
| Schema location | `target-apps/inventory-app/db/sql/` | database-agent owns DDL and seed files |
| Server | uvicorn on `PORT` (default 8000) | Single worker in dev; worker count and process management deferred to devops-agent |
| Test runner | pytest + FastAPI `TestClient` | Prefer Postgres test schema with rollback fixture; SQLite fallback only if Postgres unavailable in CI |
| Artefact handoff | `handoff_json` with `deploymentHandoff` key | Required for devops-agent pipeline stage; developer-agent must populate before closing ticket |

---

## Appendix: Assumptions

- Default pagination `limit` is assumed to be **20** unless PM specifies otherwise (Open Question 1).
- The `GET /categories` list endpoint returns a `product_count` field per item, consistent with `GET /categories/{id}` — this is inferred from the spirit of the brief but not explicitly stated for the list response.
- Slug auto-generation uses ASCII-safe lowercasing and hyphenation (e.g. `"Fresh Produce"` → `"fresh-produce"`); handling of non-ASCII characters is deferred (Open Question 2).
- `performed_by` is populated from the authenticated user's ID on every API-initiated adjust-stock call; it is nullable in the DDL to support future non-API movements (Open Question 3).
- Concurrent adjust-stock calls are serialised at the row level using a database-level atomic update; the specific locking strategy (`SELECT FOR UPDATE` vs. conditional `UPDATE`) is left to the developer-agent.
- Test database is a separate Postgres schema (`inventory_app_test`) or the same Postgres instance with transaction rollback per test; SQLite is a last resort.
- Swagger UI is enabled in all environments for the purpose of this SDLC showcase; production hardening (disabling docs, rate limiting) is out of scope.
- No maximum `delta` constraint is applied beyond the `qty_on_hand >= 0` post-condition (Open Question 6).
- `unit_price` of `0.00` is valid (free/sample items); the constraint is `>= 0` as stated.
- `updated_at` on `products` is automatically maintained via an application-layer or DB trigger `ON UPDATE`; implementation detail left to developer-agent.
- The `handoff_json` structure and schema follow the existing pipeline convention established by the `_template` project; developer-agent must conform to that schema.
- Production deployment target is assumed to be an AWS environment (inferred from README "local/AWS sections" mention) but remains cloud-agnostic until devops-agent confirms (Open Question 10).
