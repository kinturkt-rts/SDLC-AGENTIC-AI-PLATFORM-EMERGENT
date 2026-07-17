# Inventory Desk — Product Requirements Document

## 1. Overview

Small warehouse teams currently manage stock levels in disconnected spreadsheets, causing stale data and a general lack of trust in the numbers. Sales and restocks are recorded in multiple places, making it impossible for the shop manager to get a reliable picture of on-hand stock or identify items running critically low before a stockout occurs.

The Inventory Desk is a lightweight, role-aware REST API (with Swagger UI for demo use) that gives the shop manager a single authoritative catalog and gives warehouse staff a controlled way to log every stock movement. All changes flow through recorded adjustments rather than direct edits, leaving a complete audit trail of who changed what and when.

The MVP targets internal team use only — no public-facing UI is required in v1. A browser or mobile front-end, email alerts, barcode scanning, and multi-warehouse support are explicitly deferred to future releases.

---

## 2. Goals & Success Metrics

| Goal | Metric | Target | Notes |
|------|--------|--------|-------|
| Single source of truth for stock levels | % of stock adjustments recorded through the system (vs. spreadsheet) | 100 % within 2 weeks of go-live | Baseline is 0 % today |
| Reliable, trusted inventory numbers | Discrepancy rate between system quantity and physical count | < 2 % variance at first physical stocktake | Measured at first audit |
| Low-stock visibility | Time for manager to identify all low-stock items | < 60 seconds via filtered endpoint | Threshold: ≤ 5 units |
| Role-based access enforced | Unauthorised staff attempts to create/edit catalog that are rejected | 100 % rejection rate | Verified by automated tests |
| Demo-ready end-to-end journey | Manager creates category + product → staff records sale → manager views updated quantity and movement history — without error | Completable in < 5 minutes by a new user | Key acceptance scenario |

---

## 3. Non-Goals / Out of Scope

- Customer-facing or public web UI (deferred to a later phase)
- Browser-based or mobile application front-end
- Email or push notifications / alerts
- Barcode or QR-code scanning
- Multi-warehouse / multi-location support
- Supplier management or purchase-order workflows
- Financial reporting, invoicing, or accounting integrations
- User self-registration (accounts are created by an administrator)
- Automated reorder or procurement triggering
- Data import from existing spreadsheets (manual entry only for MVP)

---

## 4. Users & Use Cases

| Persona | Need | Primary use case |
|---------|------|------------------|
| Shop Manager (admin role) | Maintain an accurate, organised product catalog and monitor stock health | Signs in, creates/edits/removes categories and products, reviews low-stock list, views full movement history |
| Warehouse Staff (staff role) | Quickly look up products and record every stock movement accurately | Signs in, searches for a product by SKU or name, records a sale / restock / correction with a reason and optional note |
| Ops / DevOps | Confirm the service is healthy without authenticating | Calls the unauthenticated health-check endpoint from a monitoring tool |

---

## 5. Functional Requirements

| ID | Description | Priority | Acceptance criteria (Given / When / Then) |
|----|-------------|----------|-------------------------------------------|
| FR-1 | **User authentication** — Users sign in with username and password and receive a bearer token. Only active accounts may authenticate. | P0 | **Given** a seeded active manager account; **When** correct credentials are posted to `POST /auth/token`; **Then** the response is HTTP 200 with a valid JWT. **Given** an inactive account; **When** credentials are submitted; **Then** the response is HTTP 401 and no token is issued. |
| FR-2 | **Role-based access control** — The system enforces two roles: `manager` and `staff`. Staff may not create, update, or delete categories or products. | P0 | **Given** a staff-role token; **When** a `POST /categories` or `POST /products` request is made; **Then** the response is HTTP 403. **Given** a manager-role token; **When** the same requests are made with valid payloads; **Then** the response is HTTP 201. |
| FR-3 | **Category management** — Managers can create, rename, and delete product categories (e.g. Beverages, Snacks, Supplies). | P0 | **Given** a manager token; **When** `POST /categories` is called with a unique name; **Then** HTTP 201 is returned and the category appears in `GET /categories`. **When** `DELETE /categories/{id}` is called for a category that still has products; **Then** HTTP 409 is returned and the category is not deleted. |
| FR-4 | **Product management** — Managers can create, edit, and delete products. Each product must have a name, SKU (unique), price, category, and current quantity on hand. A product may only be deleted when its quantity is exactly zero. | P0 | **Given** a manager token; **When** `POST /products` is called with a duplicate SKU; **Then** HTTP 409 is returned. **When** `DELETE /products/{id}` is called on a product with quantity > 0; **Then** HTTP 409 is returned. **When** called on a product with quantity = 0; **Then** HTTP 200 (or 204) and the product no longer appears in `GET /products`. |
| FR-5 | **Stock adjustment** — Both managers and staff can submit stock adjustments with a reason (`sale`, `restock`, or `manual_adjustment`) and an optional free-text note. Quantity must never drop below zero; the API must reject any adjustment that would cause a negative quantity. | P0 | **Given** a staff token and a product with quantity 3; **When** `POST /products/{id}/adjustments` is called with `delta: -5`; **Then** HTTP 422 is returned and quantity remains 3. **When** called with `delta: -2`; **Then** HTTP 201 is returned and quantity is now 1. |
| FR-6 | **Audit trail** — Every stock adjustment is persisted with: the acting user's ID, timestamp (UTC), reason, delta, resulting quantity, and optional note. The audit log is immutable (no delete or edit of adjustment records). | P0 | **Given** a recorded adjustment; **When** `GET /products/{id}/adjustments` is called; **Then** the response includes `user_id`, `timestamp`, `reason`, `delta`, `quantity_after`, and `note` for every adjustment in ascending time order. **When** a `DELETE` or `PATCH` on an adjustment endpoint is attempted; **Then** HTTP 405 is returned. |
| FR-7 | **Product search and browse** — Users can list products filtered by category, SKU (exact), or name (partial, case-insensitive). Results flag items with quantity ≤ 5 as low-stock. | P1 | **Given** products with names "Cola 330ml" and "Cola 500ml"; **When** `GET /products?name=cola` is called; **Then** both products are returned. **Given** a product with quantity 4; **Then** its response payload includes `"low_stock": true`. **Given** a product with quantity 6; **Then** `"low_stock": false`. |
| FR-8 | **Low-stock summary endpoint** — A dedicated endpoint returns only products at or below the low-stock threshold (≤ 5 units) to support the manager's daily review. | P1 | **Given** mixed-quantity products; **When** `GET /products?low_stock=true` is called with a valid token; **Then** only products with quantity ≤ 5 are returned and all returned products have `"low_stock": true`. |
| FR-9 | **Seed data** — On first startup the system seeds at least one active manager account and one active staff account with known demo credentials documented in the README. Seed data must not be re-applied if the records already exist. | P0 | **Given** a fresh database; **When** the application starts; **Then** `GET /users` (manager token) returns at least one manager and one staff user. **When** the application is restarted; **Then** no duplicate seed records are created. |
| FR-10 | **Health-check endpoint** — An unauthenticated endpoint reports service and database liveness for operations monitoring. | P1 | **Given** no authentication header; **When** `GET /health` is called; **Then** HTTP 200 is returned with a payload indicating service status. **Given** the database is unreachable; **Then** HTTP 503 is returned. |

---

## 6. Non-Functional Requirements

| ID | Category | Target | Measurement / verification | Notes |
|----|----------|--------|---------------------------|-------|
| NFR-1 | Security — Authentication | Passwords stored as salted hashes (bcrypt or Argon2); plaintext passwords never persisted or logged | Code review + automated test asserting raw password is not present in DB | (Assumption: bcrypt minimum cost factor 12) |
| NFR-2 | Security — Secrets | All secrets (JWT secret key, DB credentials) read from environment variables or a `.env` file excluded from source control; no hardcoded credentials in code | CI lint step (e.g. `detect-secrets`) fails the build on secret literals | Stated constraint in brief |
| NFR-3 | Security — Transport | All API traffic served over HTTPS in any non-local environment | TLS certificate present; HTTP requests redirect to HTTPS | (Assumption) |
| NFR-4 | Performance — Latency | p95 response time ≤ 300 ms for all list/search endpoints under typical internal load | Load test with realistic concurrent users (assumption: ≤ 20 simultaneous) | (Assumption: internal team ≤ 20 users) |
| NFR-5 | Availability | Service uptime ≥ 99.5 % during warehouse operating hours | Uptime measured by health-check monitor | (Assumption: single-instance deployment acceptable for MVP) |
| NFR-6 | Data Integrity | Quantity can never be persisted below zero; enforced at both application and database constraint levels | Integration test attempting negative-balance adjustment; DB check constraint verified | Stated business rule |
| NFR-7 | Scalability | Application is stateless (JWT-based auth) so horizontal scaling requires only adding instances and a shared DB | Architecture review; no server-side session storage | (Assumption: relational DB such as PostgreSQL or SQLite for MVP) |
| NFR-8 | Observability | Structured logs (JSON) emitted for every request (method, path, status, latency) and every stock adjustment event | Log output verified in staging; no plaintext credential leakage in logs | (Assumption) |
| NFR-9 | Compliance / Data Retention | Audit-trail records retained indefinitely (no auto-purge) for MVP; retention policy to be reviewed before production rollout | DB schema has no TTL/cascade-delete on adjustment records; verified by schema inspection | Based on audit-trail requirement |
| NFR-10 | Operability | Service starts with a single command (`docker compose up` or equivalent); README documents all env vars and demo credentials | Verified by a new team member following README from a clean clone | (Assumption: Docker-based local setup) |

---

## 7. Data & Integrations

### Core Entities

| Entity | Key Attributes | Notes |
|--------|---------------|-------|
| `User` | `id`, `username`, `hashed_password`, `role` (`manager`\|`staff`), `is_active`, `created_at` | Roles drive all access decisions |
| `Category` | `id`, `name` (unique), `created_at`, `updated_at` | Cannot be deleted while products are assigned |
| `Product` | `id`, `name`, `sku` (unique), `price`, `quantity_on_hand`, `category_id`, `is_active`, `created_at`, `updated_at` | `quantity_on_hand` is read-only except via Adjustment; deletable only when quantity = 0 |
| `Adjustment` | `id`, `product_id`, `user_id`, `delta` (positive or negative integer), `reason` (enum: `sale`, `restock`, `manual_adjustment`), `note` (nullable text), `quantity_after`, `created_at` | Immutable after creation |

### Computed / Derived
- `low_stock` flag: `quantity_on_hand ≤ 5` (threshold configurable via env var in later versions).

### External Integrations
- **None for MVP.** The system is standalone; no third-party APIs, ERPs, or spreadsheet connectors are required in v1.

### API Surface
- RESTful API built with FastAPI under `target-apps/inventory-desk/`
- OpenAPI / Swagger UI enabled at `/docs` for demo purposes
- Auth via JWT Bearer tokens (`Authorization: Bearer <token>`)

---

## 8. Analytics & Observability

| Concern | Approach |
|---------|----------|
| **Request logging** | Every HTTP request logged with: timestamp (UTC), method, path, response status, latency (ms), and authenticated user ID (if present). No request bodies logged to avoid credential leakage. |
| **Adjustment events** | Each stock adjustment written to the `Adjustment` table serves as the primary event log. No separate event bus needed for MVP. |
| **Error logging** | Unhandled exceptions logged at `ERROR` level with stack trace; 4xx errors logged at `WARNING` level. |
| **Health metrics** | `/health` endpoint exposes DB connectivity status; can be polled by any uptime monitor (e.g. UptimeRobot, internal Prometheus scrape). |
| **Low-stock alerts** | Out of scope for v1; low-stock endpoint provides the data needed for a human-initiated daily review. |
| **Log format** | Structured JSON to stdout; compatible with log aggregation tools (e.g. Loki, CloudWatch) for future wiring. |

---

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Staff bypass the API and edit DB directly, breaking the audit trail | High — invalidates audit integrity | Document DB access policy; restrict DB credentials to application service account only; consider DB-level triggers as a future hardening step |
| Incorrect delta sign (e.g. staff enters positive delta for a sale) | Medium — incorrect stock level | API validates `reason` + `delta` sign pairing (e.g. `sale` must have negative delta); clear Swagger examples included |
| Demo seed credentials left active in production | High — unauthorised access | README instructs operators to rotate seed passwords before any production promotion; seed passwords read from env vars |
| Concurrent adjustments on the same product create race conditions | Medium — incorrect final quantity | DB-level row locking or optimistic concurrency (e.g. version column) on `Product.quantity_on_hand` during adjustment write |
| SQLite (if chosen for MVP) not suitable for concurrent writes at scale | Low for internal MVP, medium if usage grows | Abstract DB layer so migration to PostgreSQL requires only a connection-string change; (Assumption: MVP may start with SQLite) |
| Secrets accidentally committed to source control | High — credential exposure | Pre-commit hook using `detect-secrets`; `.env` in `.gitignore`; CI secret-scan gate |

---

## 10. Open Questions

| # | Question | Suggested owner |
|---|----------|-----------------|
| 1 | Which database engine should be used for v1 — SQLite (zero-infra) or PostgreSQL (production-grade)? | Engineering lead |
| 2 | What is the exact low-stock threshold — is 5 units fixed or should it be configurable per product or category? | Shop manager |
| 3 | Should the manager be able to create and deactivate user accounts through the API, or is user management handled out-of-band (e.g. CLI / DB seed scripts only)? | Shop manager + Engineering |
| 4 | Are there any data-retention or audit-log compliance requirements (e.g. legal hold, minimum retention period) beyond "keep everything"? | Business / legal stakeholder |
| 5 | What are the expected operating hours and acceptable maintenance windows for the service? | Ops / warehouse manager |
| 6 | Should `price` support decimal values (e.g. £1.99) and which currency/locale should be used for display? | Shop manager |
| 7 | Is a soft-delete (deactivation) required for products, or is hard-delete (quantity = 0 guard) sufficient? | Shop manager |
| 8 | What deployment environment is targeted for v1 — local Docker, a cloud VM, a PaaS? This affects HTTPS, secrets management, and HA requirements. | Engineering lead / IT ops |
| 9 | Should the `manual_adjustment` reason require manager approval, or can staff submit corrections freely? | Shop manager |
| 10 | Will demo/seed credentials be rotated before go-live, and who is responsible for initial user provisioning in production? | Shop manager + IT ops |

---

## 11. Delivery & Client Surface

| Concern | Choice | Implementation notes |
|---------|--------|---------------------|
| Client UI | API-only (Swagger / OpenAPI) — no web UI required for v1 | Brief explicitly states "Swagger is fine; no customer-facing web UI required yet" |
| API framework | FastAPI under `target-apps/inventory-desk/` | REST + OpenAPI; Swagger UI auto-enabled at `/docs`, ReDoc at `/redoc` |
| Auth mechanism | JWT Bearer tokens | `POST /auth/token` issues token; all protected routes require `Authorization: Bearer <token>` header |
| Secrets management | Environment variables / `.env` file (excluded from source control) | Document all required vars in README; provide `.env.example` template |
| Seed data | Startup script / Alembic seed migration | At least one `manager` and one `staff` account; credentials documented in README and sourced from env vars |
| Database migrations | Alembic (or equivalent) | Schema versioned; reproducible from scratch with one command |
| Local dev startup | `docker compose up` (Assumption) | Single command brings up API + DB; README documents full setup |
| Future UI | Browser / mobile UI noted as nice-to-have | FastAPI CORS settings pre-configured to allow future front-end origin; no Streamlit needed for this project |

---

## Appendix: Assumptions

- **Database:** SQLite is assumed acceptable for the MVP due to zero-infrastructure overhead; the data layer will be abstracted to allow migration to PostgreSQL without application-logic changes.
- **JWT expiry:** Access tokens expire after 8 hours by default (one working shift); no refresh-token flow is required for MVP.
- **Low-stock threshold:** Fixed at ≤ 5 units for MVP as stated in the brief; making it configurable per product is deferred.
- **Price precision:** `price` is stored as a decimal with two decimal places (e.g. `NUMERIC(10,2)`); currency is assumed to be a single locale (not multi-currency).
- **User management:** No self-registration; user accounts are created via seed scripts or a CLI helper by the manager/admin. A future CRUD `/users` endpoint for the manager role is desirable but not scoped for MVP.
- **Deployment environment:** A single-instance Docker-based deployment on an internal server or local machine is assumed for v1; no high-availability or auto-scaling infrastructure is required yet.
- **HTTPS:** Assumed required for any deployment beyond a developer's local machine; TLS termination may be handled by a reverse proxy (e.g. Nginx, Caddy).
- **Concurrency control:** Optimistic locking (version/ETag) or a `SELECT FOR UPDATE` pattern will be applied to prevent race conditions on `quantity_on_hand` during concurrent adjustments.
- **Adjustment sign convention:** A `sale` reason must carry a negative delta; a `restock` must carry a positive delta; `manual_adjustment` may be either sign. The API will validate this pairing.
- **Inactive user check:** `is_active` flag is checked at login time only; existing tokens are not revoked immediately when a user is deactivated (token expiry provides eventual revocation for MVP).
- **Category deletion guard:** Deleting a category with associated products returns HTTP 409; products must be reassigned or deleted first.
- **Audit log immutability:** No `UPDATE` or `DELETE` operations are exposed on `Adjustment` records at the API or database level.
- **Demo seed passwords:** Sourced from environment variables (not hardcoded) and documented in `.env.example`; operators must rotate them before promoting to any production environment.
