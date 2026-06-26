# Inventory Desk — Product Requirements Document

## 1. Overview

Small warehouse teams currently lack a lightweight, role-aware tool for managing a product catalog and tracking real-time stock levels through a programmable interface. Spreadsheets and ad-hoc scripts introduce inconsistency, unaudited stock mutations, and no separation of concerns between managers and floor staff.

**Inventory Desk** is a minimal full-stack REST API application built with FastAPI and PostgreSQL that gives warehouse teams a single source of truth for categories, products, and stock movements. An **admin** (shop manager) controls the catalog lifecycle while **staff** members can read inventory data and record stock movements (sales, restocks, adjustments) without being able to alter catalog structure. All interaction occurs through a versioned REST API; Swagger UI serves as the demo interface in MVP — no browser front end is required.

The project additionally serves as an end-to-end SDLC showcase across Product → Architect → Database-Agent → Developer-Agent → QA-Agent workflow stages, producing real persisted data, JWT-based authentication, role enforcement, and a full CRUD domain in a single deployable artefact targeting `target-apps/inventory-app/`.

---

## 2. Goals & Success Metrics

| Goal | Metric | Target | Notes |
|------|--------|--------|-------|
| Runnable mini-app demonstrating full auth + CRUD lifecycle | All baseline pytest cases pass on clean checkout | 100 % green | Admin login → browse → staff adjusts stock → admin adds SKU |
| Role-based access enforcement | 403 returned on every unauthorised role action (staff writing catalog) | 100 % of defined role-boundary tests pass | Verified by dedicated pytest suite |
| Transactional stock integrity | `qty_on_hand` never diverges from sum of `stock_movements.delta` for a product | Zero inconsistency detected in QA test runs | Enforced in a single DB transaction per adjust-stock call |
| SDLC artefact completeness | All required output files present and parseable | `db/sql/` DDL, seed SQL, `HANDOFF.md`, `README.md`, `handoff_json` with `deploymentHandoff` all present | Checked by QA-agent |
| API discoverability | Swagger UI loads and documents all endpoints | `/docs` returns HTTP 200 with all 13+ routes visible | Manual demo check |
| Developer on-boarding speed | New developer can run app locally after following README | Time to first successful `GET /health` ≤ 10 minutes | (Assumption) |

---

## 3. Non-Goals / Out of Scope

- Browser-based UI (Streamlit, React, or any SPA)
- OAuth 2.0 / SSO / social login
- Redis or any session-store beyond stateless JWT
- Email-based password reset or user self-registration
- AWS Bedrock, S3, or any cloud-specific managed service integration
- Docker / container orchestration (deferred to devops-agent)
- Multi-tenancy or warehouse-level data partitioning
- Soft-delete for categories or users (only `is_active` flag on users)
- Currency conversion or multi-currency pricing
- Real-time WebSocket or push-notification features
- Audit log beyond `stock_movements` table
- Rate limiting or API gateway concerns

---

## 4. Users & Use Cases

| Persona | Need | Primary use case |
|---------|------|------------------|
| **Admin** (shop manager) | Maintain accurate product catalog and correct stock errors | Signs in via `POST /auth/login`; creates/updates categories and products; deletes zero-stock products; records any type of stock adjustment |
| **Staff** (warehouse operative) | Record daily stock events without risking catalog corruption | Signs in via `POST /auth/login`; browses product list with low-stock filter; posts `adjust-stock` for sales or restocks; reviews movement history |
| **Anonymous / System** | Basic liveness probe | Calls `GET /health` for uptime monitoring without credentials |
| **Developer / Demo viewer** | Explore and test the API | Uses Swagger UI (`/docs`) to exercise all endpoints during development demos and SDLC showcases |

---

## 5. Functional Requirements

| ID | Description | Priority | Acceptance criteria (Given / When / Then) |
|----|-------------|----------|-------------------------------------------|
| FR-1 | **Health endpoint** — The system shall expose `GET /health` with no authentication that returns `{"status":"ok","service":"inventory-desk"}`. | P0 | **Given** no `Authorization` header is present, **When** a client calls `GET /health`, **Then** the response is HTTP 200 with body `{"status":"ok","service":"inventory-desk"}`. |
| FR-2 | **User authentication** — The system shall authenticate users via `POST /auth/login` accepting `{username, password}` and returning `{access_token, token_type, role, expires_in}` as a JWT (HS256, signed with `JWT_SECRET_KEY`). | P0 | **Given** seeded credentials `admin / Admin123!`, **When** `POST /auth/login` is called with correct credentials, **Then** HTTP 200 is returned with a non-empty `access_token`, `token_type="bearer"`, correct `role`, and positive `expires_in`; **And** calling with a wrong password returns HTTP 401; **And** calling for an `is_active=false` user returns HTTP 401. |
| FR-3 | **JWT bearer authorisation** — Every protected route shall reject requests missing or presenting an invalid/expired JWT with HTTP 401, and shall reject requests from an authenticated user with insufficient role with HTTP 403. | P0 | **Given** a valid staff JWT, **When** `POST /categories` is called, **Then** HTTP 403 is returned. **Given** no token, **When** `GET /categories` is called, **Then** HTTP 401 is returned. **Given** an expired token, **When** any protected route is called, **Then** HTTP 401 is returned. |
| FR-4 | **Category CRUD** — Admin users shall be able to create (`POST /categories`, HTTP 201), list (`GET /categories`, paginated), retrieve (`GET /categories/{id}` with `product_count`), and update (`PATCH /categories/{id}`) categories. A slug shall be auto-derived from name when omitted. A duplicate slug shall return HTTP 409. A missing category ID shall return HTTP 404. | P1 | **Given** an admin JWT, **When** `POST /categories` is called with `{"name":"Electronics"}` and no `slug`, **Then** HTTP 201 is returned and the response body contains a non-null `slug` derived from the name. **When** the same slug is submitted again, HTTP 409 is returned. **Given** a staff JWT, the same POST returns HTTP 403. |
| FR-5 | **Product CRUD** — Admin users shall be able to create (`POST /products`, HTTP 201), retrieve (`GET /products/{id}`), and update (`PATCH /products/{id}`) products. `qty_on_hand` shall not be settable directly via PATCH. Creating with an unknown `category_id` returns HTTP 404; duplicate `sku` returns HTTP 409. | P1 | **Given** an admin JWT and a valid `category_id`, **When** `POST /products` is called with a unique SKU, **Then** HTTP 201 is returned and the product has `qty_on_hand=0`. **When** the same SKU is submitted again, HTTP 409 is returned. **When** `PATCH /products/{id}` is called with a `qty_on_hand` field, **Then** the field is ignored and the existing quantity is unchanged. |
| FR-6 | **Product list filtering** — `GET /products` shall support query parameters `category_id`, `sku`, and `low_stock=true` (returns only products with `qty_on_hand ≤ 5`). All list endpoints shall return `{items, total, limit, offset}` with `?limit=` and `?offset=` pagination. | P1 | **Given** products with varying stock levels, **When** `GET /products?low_stock=true` is called by an authenticated user, **Then** every item in the response has `qty_on_hand ≤ 5` and `total` reflects the filtered count. **When** `GET /products?category_id=<uuid>` is called, **Then** only products in that category are returned. |
| FR-7 | **Adjust-stock transaction** — Both admin and staff users shall be able to `POST /products/{id}/adjust-stock` with `{delta, reason, note?}`. The operation shall atomically insert a `stock_movements` row and update `qty_on_hand`. A resulting negative `qty_on_hand` shall return HTTP 422 without persisting any change. `performed_by` shall be set to the calling user's ID. | P0 | **Given** a product with `qty_on_hand=3` and a staff JWT, **When** `POST /products/{id}/adjust-stock` is called with `{"delta":-5,"reason":"sale"}`, **Then** HTTP 422 is returned and `qty_on_hand` remains 3 and no movement row is created. **When** called with `{"delta":2,"reason":"restock"}`, **Then** HTTP 200 is returned, `qty_on_hand` becomes 5, and a movement row exists with `performed_by` equal to the staff user ID. |
| FR-8 | **Stock movement history** — `GET /products/{id}/movements` shall return all stock movements for a product, ordered newest-first, with pagination (`{items, total, limit, offset}`). Access requires admin or staff JWT. | P1 | **Given** three adjust-stock calls for a product, **When** `GET /products/{id}/movements?limit=2&offset=0` is called, **Then** exactly 2 items are returned with `total=3` and items are in descending `created_at` order. |
| FR-9 | **Delete product** — Admin users shall be able to `DELETE /products/{id}`. The endpoint shall return HTTP 204 when `qty_on_hand=0` and HTTP 409 when `qty_on_hand > 0`. | P1 | **Given** a product with `qty_on_hand=0` and an admin JWT, **When** `DELETE /products/{id}` is called, **Then** HTTP 204 is returned and subsequent `GET /products/{id}` returns HTTP 404. **Given** `qty_on_hand=5`, **Then** HTTP 409 is returned and the product persists. |
| FR-10 | **Database schema and seeding** — The database-agent shall produce DDL under `target-apps/inventory-app/db/sql/` creating the `inventory_app` schema with tables `users`, `categories`, `products`, and `stock_movements` (with all constraints, FKs, and enum types described in the data model). A separate dev-only seed SQL file shall insert the two seed users with bcrypt-hashed passwords. | P0 | **Given** a clean Postgres instance, **When** the DDL and seed SQL files are executed in order, **Then** `SELECT count(*) FROM inventory_app.users` returns 2; `admin` and `staff` usernames exist; login with `admin / Admin123!` succeeds via the API. |
| FR-11 | **Category ON DELETE RESTRICT / Stock movement CASCADE** — Deleting a category with associated products shall be blocked at the database level. Deleting a product shall cascade-delete its stock_movement rows. | P1 | **Given** a category with one product, **When** the category is deleted directly (or via admin API if exposed), **Then** the operation fails with a constraint error (HTTP 409 or 500 surfaced gracefully). **Given** a product with movements, **When** the product is deleted (qty=0), **Then** its movement rows are also removed. |
| FR-12 | **Configuration via environment variables** — The application shall load all secrets and configuration from environment variables defined in `.env.example`: `DATABASE_URL`, `POSTGRES_SCHEMA`, `JWT_SECRET_KEY`, `JWT_EXPIRE_MINUTES`, `PORT`. The app shall fail to start with a clear error if `DATABASE_URL` or `JWT_SECRET_KEY` are absent. | P0 | **Given** a missing `JWT_SECRET_KEY` env var, **When** the application starts, **Then** it exits with a non-zero code and prints an error identifying the missing variable. **Given** all required vars present, the app binds to `PORT` (default 8000). |
| FR-13 | **SDLC artefact delivery** — The developer-agent shall produce a `README.md` with local-run and AWS-run instructions plus `curl` login examples, and `handoff_json` shall include a `deploymentHandoff` block for the devops-agent. The database-agent shall produce `HANDOFF.md`. | P1 | **Given** the output directory `target-apps/inventory-app/`, **When** QA-agent inspects the file tree, **Then** `README.md`, `db/sql/` (DDL + seed), `HANDOFF.md`, and `handoff_json` with a `deploymentHandoff` key all exist and are non-empty valid files. |

---

## 6. Non-Functional Requirements

| ID | Category | Target | Measurement / verification | Notes |
|----|----------|--------|---------------------------|-------|
| NFR-1 | Security — Password storage | All user passwords stored as bcrypt hashes; plaintext never persisted or logged | Code review: grep for plaintext assignment; pytest checks `password_hash` column never equals raw password | Uses `passlib[bcrypt]`; seed SQL contains pre-hashed values |
| NFR-2 | Security — JWT | Tokens signed HS256 using `JWT_SECRET_KEY` from env; default expiry 60 minutes; secret never hard-coded in source | Code review; unit test verifying expired token returns 401; secret absent from repo scan | `JWT_EXPIRE_MINUTES` configurable via env |
| NFR-3 | Security — Role enforcement | Every role boundary enforced server-side; no client-side trust | Full pytest role-boundary suite (staff→403, anon→401 on all protected routes) | 403 vs 401 distinction required per FR-3 |
| NFR-4 | Performance — API response time | p95 response time ≤ 300 ms for all list endpoints under light load (< 50 concurrent users) | Load test with `httpx` or `locust` during QA stage | (Assumption) — warehouse team is small |
| NFR-5 | Availability | Application process restarts cleanly with `uvicorn` after DB connection loss; graceful 503 returned | Manual/automated test: stop Postgres, call endpoint, verify non-crash response | (Assumption) — no HA/load-balancer in MVP |
| NFR-6 | Data integrity — Stock atomicity | `qty_on_hand` update and `stock_movements` insert occur in a single DB transaction; no partial write possible | pytest: simulate mid-transaction failure (mock); verify rollback leaves qty unchanged | Enforced in `app/services/` layer via SQLAlchemy transaction |
| NFR-7 | Scalability | Schema and ORM layer support ≥ 10,000 products and ≥ 100,000 stock_movement rows without schema changes | Index on `products.category_id`, `products.sku`; `stock_movements.product_id` indexed; verify with `EXPLAIN ANALYZE` on seeded data | (Assumption) — small warehouse; no sharding required in MVP |
| NFR-8 | Observability | Application logs each request (method, path, status, latency) at INFO level to stdout; errors logged at ERROR level with stack trace | pytest + log capture; manual review of uvicorn access log | (Assumption) — structured JSON logging preferred but plain text acceptable for MVP |
| NFR-9 | Operability | App starts from a single `uvicorn app.main:app` command after `pip install -r requirements.txt` and env vars set | QA-agent smoke test on clean virtualenv | README must document exact commands |
| NFR-10 | Compliance / Data retention | Seed user credentials documented in README with a warning to rotate before production; seed SQL scoped to dev-only file | Code review; README contains explicit "change in production" notice | No regulatory regime specified — (Assumption) internal tool only |
| NFR-11 | Testability | pytest suite covers: login (admin + staff), role 403 (staff→create category), adjust-stock qty update, negative-stock 422, delete-blocked 409, pagination shape, 401 without token | `pytest` exits 0 with ≥ the listed test scenarios passing | Prefer Postgres test schema with rollback fixture over SQLite |

---

## 7. Data & Integrations

### Core Entities

| Entity | Key fields | Constraints / Notes |
|--------|-----------|---------------------|
| `users` | `id` uuid PK, `username` text UNIQUE NOT NULL, `password_hash` text NOT NULL, `role` enum(`admin`\|`staff`) NOT NULL, `is_active` bool DEFAULT true, `created_at` timestamptz | Schema: `inventory_app`; seeded via dev SQL only |
| `categories` | `id` uuid PK, `name` text NOT NULL (1–80 chars), `slug` text UNIQUE NOT NULL, `created_at` timestamptz | Slug auto-derived from name if omitted; no delete if products exist (ON DELETE RESTRICT) |
| `products` | `id` uuid PK, `category_id` uuid FK→categories (RESTRICT), `sku` text UNIQUE NOT NULL, `name` text NOT NULL (1–120 chars), `unit_price` numeric(10,2) ≥ 0, `qty_on_hand` int NOT NULL DEFAULT 0 ≥ 0, `created_at` timestamptz, `updated_at` timestamptz | `qty_on_hand` never updated directly via API; only via adjust-stock |
| `stock_movements` | `id` uuid PK, `product_id` uuid FK→products (CASCADE), `delta` int NOT NULL, `reason` enum(`sale`\|`restock`\|`adjustment`) NOT NULL, `note` text nullable (max 500 chars), `performed_by` uuid FK→users nullable, `created_at` timestamptz | Immutable after creation; represents full audit trail |

### Postgres Schema

- Schema name: `inventory_app` (set via `search_path` in SQLAlchemy `sessionmaker` / `_template`)
- DDL files location: `target-apps/inventory-app/db/sql/`
- Seed (dev only): separate SQL file; bcrypt-hashed passwords for `admin / Admin123!` and `staff / Staff123!`

### External Integrations

- **None in MVP.** The application is self-contained (FastAPI + Postgres). Cloud storage, messaging, email, and third-party auth are explicitly out of scope.

### Environment Configuration

| Variable | Purpose | Default |
|----------|---------|---------|
| `DATABASE_URL` | SQLAlchemy Postgres connection string | Required — no default |
| `POSTGRES_SCHEMA` | Postgres schema name for `search_path` | `inventory_app` |
| `JWT_SECRET_KEY` | HMAC-HS256 signing secret | Required — no default |
| `JWT_EXPIRE_MINUTES` | Token lifetime in minutes | `60` |
| `PORT` | uvicorn bind port | `8000` |

---

## 8. Analytics & Observability

### Application Logging
- All HTTP requests logged at **INFO** level to stdout: `{timestamp} {method} {path} {status_code} {latency_ms}`.
- Unhandled exceptions logged at **ERROR** level with full stack trace.
- Authentication failures logged at **WARNING** level (without echoing the submitted password).
- Use uvicorn's built-in access log in development; structured JSON logging recommended for production deployment (devops-agent concern).

### Key Metrics to Surface (Future / Devops-Agent)
- Request rate and error rate per endpoint.
- `adjust-stock` call volume by `reason` (sale vs restock vs adjustment).
- Count of 401/403 responses (potential misconfiguration or abuse signal).
- Products with `qty_on_hand ≤ 5` (low-stock count) — queryable via `GET /products?low_stock=true`.

### Alerts (Future)
- Postgres connection pool exhaustion.
- Sustained p95 latency > 500 ms.
- Any HTTP 5xx error rate > 1 % over a 5-minute window.

### Developer / QA Observability
- `GET /health` serves as the primary liveness probe.
- Swagger UI at `/docs` serves as the interactive API explorer for demo and QA.
- pytest output is the primary quality gate artefact; all test results must be captured in CI logs.

---

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Seed credentials (`Admin123!` / `Staff123!`) used in production | Critical — full admin access with known password | README must include explicit "CHANGE BEFORE PRODUCTION" warning; seed SQL scoped to dev-only file; documented in NFR-10 |
| `JWT_SECRET_KEY` committed to version control | Critical — all tokens forgeable | `.env` in `.gitignore`; only `.env.example` committed; startup validation rejects missing key |
| Negative stock race condition under concurrent adjust-stock calls | High — inventory integrity broken | DB-level `CHECK (qty_on_hand >= 0)` constraint as backstop; single transaction with row-level lock (`SELECT FOR UPDATE`) on product row |
| `ON DELETE RESTRICT` on categories blocks legitimate cleanup | Medium — admin frustration | Document required workflow: move/delete products before deleting category; consider a `product_count` field in `GET /categories/{id}` response to surface dependency (already in FR-4) |
| SQLite incompatibility in test fixture | Medium — tests pass locally but not in CI Postgres | Pytest fixture targets a dedicated `inventory_app_test` Postgres schema with rollback; SQLite fallback explicitly discouraged per developer baseline |
| Slug collision on concurrent category creation | Low — 409 race | Unique index on `categories.slug` enforces at DB level; application surfaces as 409 |
| Token expiry not tested | Low — silent security gap | Dedicated pytest case: forge an expired token, assert 401 returned |
| `performed_by` nullable in stock_movements | Low — incomplete audit trail | Set `performed_by` from JWT subject on every adjust-stock call; nullable only to allow historical/migration rows |

---

## 10. Open Questions

| # | Question | Suggested owner |
|---|----------|-----------------|
| 1 | Should `DELETE /categories/{id}` be exposed in MVP, or is category deletion handled only at the DB level? The API contract table does not include it. | Product / Admin |
| 2 | Should admin be able to deactivate/reactivate users via API, or is `is_active` management DB-only in MVP? | Product |
| 3 | Is `unit_price` required to be non-zero, or can zero-price (free/gifted) items be valid? The brief states `>= 0`; confirming zero is intentional. | Product |
| 4 | What Postgres version is the target environment? Affects UUID generation strategy (`gen_random_uuid()` vs `uuid_generate_v4()`). | Architect / Devops-agent |
| 5 | Should pagination `limit` have a server-enforced maximum (e.g. 200) to prevent unbounded queries? | Architect |
| 6 | Is `GET /categories` available to anonymous users (health-check model) or strictly admin + staff only as stated? | Product |
| 7 | What is the expected token refresh strategy? Current design has no `POST /auth/refresh` — clients must re-login after expiry. | Product / Architect |
| 8 | Should `stock_movements` be soft-deleted or are they immutable forever? The current design implies immutability, but no explicit constraint is stated. | Product |
| 9 | Are there any data-retention requirements (e.g. purge movements older than N years) relevant to the compliance posture? | Product / Legal |
| 10 | Does the `handoff_json` format follow a project-wide schema? Where is the canonical schema for `deploymentHandoff`? | Architect / Devops-agent |

---

## Appendix: Assumptions

- **No browser UI** is required at any point during MVP; Swagger (`/docs`) is the sole UI surface.
- The application runs as a **single-process** uvicorn server with no worker scaling in MVP; horizontal scaling is deferred to the devops-agent.
- **Slug generation** derives a URL-safe lowercase slug from the category name (e.g. replacing spaces with hyphens, stripping special characters); exact algorithm is an implementation detail for the developer-agent.
- **`updated_at` on products** is maintained via an application-level update or a Postgres trigger; the developer-agent shall choose the approach and document it.
- **Token refresh** is not supported in MVP; clients must re-authenticate after `JWT_EXPIRE_MINUTES`.
- **`performed_by` is always set** from the JWT subject when a logged-in user calls adjust-stock; the column is nullable only to accommodate potential future migration rows.
- **p95 latency target of 300 ms** assumes a co-located Postgres instance and a small warehouse team (< 50 concurrent users).
- **Availability target** assumes a single-node deployment; no SLA is defined for MVP.
- **Structured JSON logging** is a recommendation, not a hard requirement for MVP; plain uvicorn access log is acceptable.
- **`SELECT FOR UPDATE`** or equivalent row-level locking is assumed necessary on the products row during adjust-stock to prevent race conditions; implementation is the developer-agent's responsibility.
- **UUID primary keys** use `gen_random_uuid()` (requires Postgres 13+ or `pgcrypto` extension); if an older Postgres version is targeted, `uuid_generate_v4()` with `CREATE EXTENSION IF NOT EXISTS "uuid-ossp"` is the fallback.
- **The `reason` enum** for stock_movements accepts exactly `sale | restock | adjustment`; no other values are valid.
- **Seed users are the only users** in MVP; there is no user-registration endpoint.
- **Soft-delete for products and categories is not implemented**; only the `is_active` flag exists on `users`.
- **`GET /categories/{id}` returning `product_count`** is computed as a SQL aggregate at query time, not stored as a column.
- **`PATCH` semantics** follow partial update (only supplied fields are modified); full replacement (`PUT`) is not implemented.
- **`note` on stock_movements** is capped at 500 characters; validation enforced at the Pydantic schema layer.
- The **devops-agent Docker/deployment** artefacts are out of scope for this PRD and will be addressed in a subsequent PRD or handoff document.
