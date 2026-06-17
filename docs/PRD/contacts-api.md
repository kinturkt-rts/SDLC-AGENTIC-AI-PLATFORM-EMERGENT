# Contact Directory API — Product Requirements Document

## 1. Overview

Internal teams frequently need a lightweight, authoritative place to look up colleague contact cards without standing up a full identity platform. Today that information lives in spreadsheets or wiki pages that quickly go stale, have no consistent structure, and cannot be queried programmatically. The Contact Directory API solves this by providing a small, durable REST service backed by PostgreSQL that any internal tool or script can call to browse colleagues by department, name, or email.

The solution is intentionally minimal: a FastAPI application exposing read-only endpoints to all callers and write endpoints protected by a single shared API key loaded from the environment. There is no login UI, no JWT stack, and no external dependencies beyond FastAPI, SQLAlchemy 2.x, and PostgreSQL. Swagger at `/docs` serves as the interactive demo surface.

This project also serves a secondary engineering purpose: validating the end-to-end SDLC automation chain for Pattern B (Postgres CRUD) — spanning product → architect → database-agent → developer-agent → qa-agent — in a scope that is richer than an in-memory toy but simpler than a full inventory application.

---

## 2. Goals & Success Metrics

| Goal | Metric | Target | Notes |
|------|--------|--------|-------|
| Runnable API delivered by developer-agent | `pytest` suite passes with zero failures | 100 % green on first clean run | SQLite in-memory used for unit tests |
| Schema & seed delivered by database-agent | Numbered SQL migrations + seed file present; `HANDOFF.md` committed | All artefacts present in `target-apps/contacts-api/db/sql/` | Stable UUIDs; `ON CONFLICT DO NOTHING` in seed |
| Auth correctness | Write routes reject missing/wrong key | 401 returned for every unauthenticated write attempt in test suite | No false positives on read routes |
| Core read flows | List, filter, search, and fetch-by-id work end-to-end | Manual smoke sequence completes without error (health → list → create → fetch) | Documented in README curl examples |
| Pagination shape | List responses include `items`, `total`, `limit`, `offset` | Verified by at least one pagination shape test | Defaults TBD in Open Questions |
| Soft-delete preserves data | DELETE sets `is_active=false`; record remains in DB | Confirmed by qa-agent test post-delete fetch | No hard deletes in MVP |
| SDLC chain validation | Pattern B pipeline executes without manual intervention | All agents produce artefacts on first run | Primary non-functional goal of the project |

---

## 3. Non-Goals / Out of Scope

- JWT authentication, OAuth, sessions, bcrypt, or any users table
- Bedrock / LLM integration of any kind
- pgvector, RAG, or semantic search
- Streamlit, React, or any browser-rendered UI (Swagger `/docs` is the only UI surface)
- Redis caching or S3 storage
- Docker / container orchestration (deferred to devops-agent)
- Hard deletion of contact records in MVP
- Role-based access control beyond the single shared API key
- Email delivery or notification system
- External directory sync (LDAP, Google Workspace, etc.)

---

## 4. Users & Use Cases

| Persona | Need | Primary use case |
|---------|------|------------------|
| Anonymous caller (internal script / browser) | Browse the contact directory without credentials | `GET /contacts?q=alice&department_id=<uuid>` to find a colleague's phone and email |
| Integrator (service account or developer with API key) | Programmatically maintain the directory | `POST /contacts`, `PATCH /contacts/{id}`, `DELETE /contacts/{id}` using `X-API-Key` header |
| Demo viewer (engineer, PM, stakeholder) | Explore available endpoints interactively | Navigate Swagger UI at `/docs`; execute GET and write calls via the built-in form |
| QA agent / developer | Verify correct behaviour of every route and edge case | Run `pytest` suite; issue curl commands from README |
| Database agent | Own schema lifecycle | Apply numbered SQL migrations; run seed script; publish `HANDOFF.md` |

---

## 5. Functional Requirements

| ID | Description | Priority | Acceptance criteria (Given / When / Then) |
|----|-------------|----------|-------------------------------------------|
| FR-1 | **Health endpoint** — `GET /health` returns service status with no authentication required | P0 | **Given** the API is running; **When** any caller sends `GET /health`; **Then** the response is HTTP 200 with body `{"status":"ok","service":"contacts-api"}` and no `X-API-Key` header is required |
| FR-2 | **API-key guard on write routes** — all `POST`, `PATCH`, and `DELETE` routes require a valid `X-API-Key` header matching the value in `settings.API_KEY` | P0 | **Given** a write route exists; **When** the request omits `X-API-Key` or supplies an incorrect value; **Then** the response is HTTP 401 with body `{"detail":"Invalid or missing API key"}`; **And** when the correct key is supplied the request proceeds normally |
| FR-3 | **Create department** — `POST /departments` creates a new department record with a unique code | P0 | **Given** an integrator supplies a valid name and unique uppercase code (2–10 chars) with a valid API key; **When** the request is submitted; **Then** HTTP 201 is returned with the created department object including its generated UUID and `created_at`; **And** submitting a duplicate code returns HTTP 409 |
| FR-4 | **List departments** — `GET /departments` returns all departments sorted by name; `GET /departments/{id}` returns a single department with a `contact_count` field | P0 | **Given** at least one department exists; **When** `GET /departments` is called (no auth); **Then** HTTP 200 is returned with an array sorted ascending by `name`; **And** `GET /departments/{id}` returns HTTP 200 with `contact_count` equal to the number of contacts associated with that department, or HTTP 404 if the ID is unknown |
| FR-5 | **Update department** — `PATCH /departments/{id}` allows updating `name` and/or `code` with API-key auth | P1 | **Given** a valid API key and an existing department ID; **When** a partial update payload is submitted; **Then** HTTP 200 is returned with the updated fields reflected; **And** a code value already held by a different department returns HTTP 409 |
| FR-6 | **Create contact** — `POST /contacts` creates a new contact associated with an existing department | P0 | **Given** a valid API key and a payload with `full_name`, `email`, and a valid `department_id`; **When** the request is submitted; **Then** HTTP 201 is returned with the created contact; **And** an unknown `department_id` returns HTTP 404; **And** a duplicate `email` (active or inactive) returns HTTP 409 |
| FR-7 | **List contacts with filtering, search, and pagination** — `GET /contacts` supports `?department_id=`, `?is_active=`, `?q=`, `?limit=`, `?offset=` | P0 | **Given** contacts exist in the database; **When** `GET /contacts` is called with any combination of query parameters; **Then** HTTP 200 is returned with body shape `{"items":[…],"total":<int>,"limit":<int>,"offset":<int>}`; **And** `?q=alice` performs a case-insensitive partial match on `full_name` and `email`; **And** `?is_active=false` includes only inactive contacts; **And** `total` reflects the filtered count, not the overall table size |
| FR-8 | **Fetch single contact** — `GET /contacts/{id}` returns a contact or 404 | P0 | **Given** a contact ID; **When** `GET /contacts/{id}` is called (no auth); **Then** HTTP 200 is returned with the full contact object if the ID exists; **And** HTTP 404 is returned if the ID is unknown |
| FR-9 | **Update contact** — `PATCH /contacts/{id}` updates one or more mutable fields and bumps `updated_at` | P1 | **Given** a valid API key and an existing contact ID; **When** a partial update is submitted with at least one changed field; **Then** HTTP 200 is returned with updated values and `updated_at` set to the current timestamp; **And** supplying an email already used by another contact returns HTTP 409 |
| FR-10 | **Soft-delete contact** — `DELETE /contacts/{id}` sets `is_active=false` and returns 204; the record is not removed from the database | P0 | **Given** a valid API key and an existing contact ID; **When** `DELETE /contacts/{id}` is called; **Then** HTTP 204 is returned; **And** a subsequent `GET /contacts/{id}` still returns the record with `is_active=false`; **And** the row remains in the `contacts` table |
| FR-11 | **Seed data present on first migration** — the database seed provides 3 departments and 6–8 contacts with stable UUIDs, including at least one `is_active=false` contact | P0 | **Given** migrations and seed are applied to a fresh database; **When** `GET /contacts?is_active=false` is called; **Then** at least one contact is returned; **And** `GET /departments` returns exactly Engineering (ENG), Sales (SALES), and HR (HR) |
| FR-12 | **Swagger UI available at /docs** — the interactive API documentation is accessible with no authentication | P1 | **Given** the service is running; **When** a browser navigates to `/docs`; **Then** HTTP 200 is returned and the Swagger UI renders all defined routes |

---

## 6. Non-Functional Requirements

| ID | Category | Target | Measurement / verification | Notes |
|----|----------|--------|---------------------------|-------|
| NFR-1 | Security | `X-API-Key` header is compared using a constant-time or equivalent safe comparison; key is never logged or echoed in responses | Code review of `verify_api_key` dependency; confirm no key appears in structured logs | API key loaded exclusively from env via pydantic-settings |
| NFR-2 | Security / Secrets | `API_KEY` and `DATABASE_URL` must not be hard-coded in source; `.env.example` uses placeholder `dev-api-key-change-me` | Automated scan / grep confirms no real secrets committed to repo | `.env` must be in `.gitignore` |
| NFR-3 | Performance | `GET /contacts` (unfiltered, default page size) responds in < 300 ms at p95 under light load (≤ 10 concurrent requests) | Timed locally via `pytest-benchmark` or `httpx` timing logs | (Assumption) — no load-test tooling specified; target is indicative |
| NFR-4 | Availability | Service starts successfully and passes health check within 10 s of process launch | `pytest` startup fixture confirms `GET /health` returns 200 before tests run | (Assumption) |
| NFR-5 | Scalability | Data model and query patterns must support up to 10 000 contact rows without schema changes | Index on `contacts.email` (unique), `contacts.department_id`, and `contacts.is_active` declared in DDL | (Assumption) — index requirements inferred from query patterns |
| NFR-6 | Observability | All unhandled exceptions produce a structured log entry (level ERROR) including route, HTTP method, and status code | Manual verification and review of exception handler in FastAPI app | (Assumption) — specific logging library not mandated |
| NFR-7 | Operability | Application must start with `uvicorn app.main:app --port $PORT` using only values from `.env`; a `README.md` provides Windows and bash setup steps | Developer-agent delivers README; manual walkthrough confirms startup | PORT defaults to 8000 per `.env.example` |
| NFR-8 | Compliance / Data retention | No hard deletes in MVP; soft-delete pattern (`is_active=false`) is the only supported removal mechanism | `pytest` test confirms row presence after `DELETE /contacts/{id}` | Aligns with FR-10 |
| NFR-9 | Testability | `pytest` suite runs against SQLite in-memory (via dialect-guarded `database.py`); no live Postgres instance required for CI | `pytest` completes with zero failures in a clean virtualenv with no Postgres connection | SQLite used for unit tests; psycopg binary only needed for integration against real Postgres |
| NFR-10 | Compatibility | Application must run on Python 3.12; no boto3, Bedrock, pgvector, Streamlit, or JWT libraries may appear in `requirements.txt` or `pyproject.toml` | Dependency file audit; `pip check` passes | Mandated by Pattern B constraints |

---

## 7. Data & Integrations

### Core Entities

**`departments`**
| Column | Type | Constraints |
|--------|------|-------------|
| `id` | `uuid` | PK, default `gen_random_uuid()` |
| `name` | `text` | NOT NULL, 1–80 chars |
| `code` | `text` | UNIQUE NOT NULL, 2–10 uppercase chars |
| `created_at` | `timestamptz` | NOT NULL, DEFAULT `now()` |

**`contacts`**
| Column | Type | Constraints |
|--------|------|-------------|
| `id` | `uuid` | PK, default `gen_random_uuid()` |
| `department_id` | `uuid` | FK → `departments.id` ON DELETE RESTRICT |
| `full_name` | `text` | NOT NULL, 1–120 chars |
| `email` | `text` | UNIQUE NOT NULL, valid email format |
| `phone` | `text` | nullable, max 30 chars |
| `title` | `text` | nullable, max 80 chars |
| `is_active` | `bool` | NOT NULL, DEFAULT `true` |
| `created_at` | `timestamptz` | NOT NULL, DEFAULT `now()` |
| `updated_at` | `timestamptz` | NOT NULL, DEFAULT `now()` |

### Schema & DDL Ownership
- Postgres schema: `contacts_api`
- DDL path: `target-apps/contacts-api/db/sql/` — numbered migration files owned by the database-agent
- Seed file uses stable UUIDs and `ON CONFLICT DO NOTHING` for idempotent re-runs

### External Integrations
- **PostgreSQL** (version TBD — see Open Questions): primary data store; connection via `postgresql+psycopg://` with `?sslmode=require`
- **SQLite** (in-memory, Python stdlib): test-time replacement controlled by dialect guard in `database.py`
- No external APIs, message queues, object storage, or identity providers in scope

### Environment Variables
| Variable | Required | Example / Default |
|----------|----------|-------------------|
| `DATABASE_URL` | Yes | `postgresql+psycopg://user:pass@host:5432/dbname?sslmode=require` |
| `POSTGRES_SCHEMA` | Yes | `contacts_api` |
| `API_KEY` | Yes | `dev-api-key-change-me` |
| `PORT` | No | `8000` |

---

## 8. Analytics & Observability

**Logging**
- Structured logs (JSON preferred) emitted to stdout so the deployment layer can capture them without file-path assumptions.
- Minimum log events: application startup (including resolved `PORT` and schema name, never the API key value), each inbound request (method, path, status code, duration), and all unhandled exceptions.
- API key value must never appear in any log line.

**Health check**
- `GET /health` is the primary liveness probe; it must return within 1 s and not require database connectivity (liveness vs. readiness separation is a future concern — see Open Questions).

**pytest coverage**
- The developer-agent should aim for coverage of all route handlers; a coverage report (`pytest --cov`) is recommended but a hard threshold is not mandated in MVP.

**Alerts** *(Assumption)*
- No alerting infrastructure is in scope for MVP; observability tooling (e.g., Prometheus, Datadog) is deferred to the devops-agent phase.

---

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| SQLite dialect differences cause false-green tests that hide Postgres-specific bugs (e.g., UUID type, `timestamptz`, `ILIKE`) | Medium — bugs surface only in integration | Dialect guard in `database.py` maps types correctly; integration smoke test against real Postgres is part of the manual acceptance checklist |
| Shared API key leaked via logs, error responses, or version control | High — unauthorized writes to directory | pydantic-settings loads key from env only; log sanitisation rule; `.env` in `.gitignore`; `.env.example` uses placeholder value |
| `ON DELETE RESTRICT` on `contacts.department_id` prevents department deletion while contacts exist | Low — expected behaviour, but may surprise callers | Document in API error response and README; deleting a department with associated contacts returns a clear 409/422 |
| Duplicate-email constraint covers inactive records, which may surprise integrators re-using a former employee's email | Medium — unexpected 409 on `POST /contacts` | Explicitly documented in API contract notes and Swagger description; considered a correct business rule in MVP |
| SQLite in-memory tests do not exercise `POSTGRES_SCHEMA` search path | Low — schema routing untested in CI | Manual smoke test against Postgres is required before any production deployment; schema routing covered in integration checklist |
| Scope creep pressure to add JWT or user table during development | Medium — complexity increase mid-sprint | PRD explicitly marks JWT/auth expansion as out of scope; change requires new PRD revision |

---

## 10. Open Questions

| # | Question | Suggested owner |
|---|----------|-----------------|
| 1 | Which PostgreSQL version (e.g., 14, 15, 16) is the target deployment environment? Affects `gen_random_uuid()` vs. `uuid_generate_v4()` and `GENERATED ALWAYS` syntax. | Database agent / infrastructure |
| 2 | What are the default values for `?limit=` and maximum allowable `?limit=` on paginated list endpoints? | PM / developer-agent |
| 3 | Should `GET /health` perform a database connectivity check (readiness probe) or remain a pure liveness probe? | Architect |
| 4 | Is there a requirement for `updated_at` auto-bump on `PATCH /departments/{id}`? The current data model defines `updated_at` only on `contacts`. | Architect / database-agent |
| 5 | What is the expected deployment environment for the Postgres instance (managed cloud RDS/Cloud SQL, local, CI service container)? Affects `sslmode` requirements in CI. | Infrastructure / devops-agent |
| 6 | Should `DELETE /departments/{id}` be exposed in MVP? The brief defines `POST` and `PATCH` but not `DELETE` for departments. | PM |
| 7 | Is there a requirement to return `contact_count` filtered by `is_active=true` only, or all contacts regardless of status, in `GET /departments/{id}`? | PM / developer-agent |
| 8 | What content-type encoding is expected for `phone` validation — E.164, free-text, or simply max-30-chars with no format check? | PM |
| 9 | Should the qa-agent's additional edge-case tests live in the same `pytest` suite or a separate test directory? | QA agent / developer-agent |
| 10 | Is there a desired sort order for `GET /contacts` when no explicit sort parameter is provided? | PM / developer-agent |

---

## Appendix: Assumptions

- The `updated_at` column on `contacts` is bumped server-side (in the SQLAlchemy model's `onupdate` or equivalent) rather than requiring the caller to supply a timestamp.
- The `contact_count` field returned by `GET /departments/{id}` counts all contacts for that department regardless of `is_active` status, unless clarified (see Open Question 7).
- Default pagination `limit` is assumed to be 20 and maximum `limit` is assumed to be 100; these values should be confirmed with PM (Open Question 2).
- Email format validation is performed by Pydantic v2's `EmailStr` type; no external email-verification service is used.
- The `code` field on departments is stored and validated as uppercase; the API should reject or normalise lowercase input (implementation detail left to developer-agent).
- `GET /contacts` with no filters returns all contacts regardless of `is_active` status by default; callers must explicitly pass `?is_active=true` to restrict to active only. This assumption should be confirmed.
- No rate limiting is applied in MVP; all endpoints are equally available to any caller.
- The service runs as a single process (no worker concurrency configuration beyond uvicorn defaults) in MVP.
- A `HANDOFF.md` from the database-agent documents migration order, seed data UUIDs, and any manual steps required for the developer-agent to proceed.
- The `POSTGRES_SCHEMA` env variable is used as the SQLAlchemy `search_path` / schema argument; the dialect guard defaults to the default SQLite schema for test runs.
- Swagger UI (`/docs`) and ReDoc (`/redoc`) are both enabled by FastAPI defaults; neither requires authentication.
- No soft-delete endpoint exists for departments in MVP; `departments` records are considered permanent unless explicitly scoped in a future revision.
- `sslmode=require` in `DATABASE_URL` is expected for any non-local Postgres instance; local development may use `sslmode=disable` by overriding `.env`.
- The three seed departments (Engineering/ENG, Sales/SALES, HR/HR) use stable, pre-generated UUIDs to make filter-by-department tests deterministic without dynamic lookups.
