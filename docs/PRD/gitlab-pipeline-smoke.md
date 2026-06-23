# Team Notice Board API — PRD

## 1. Overview

Internal teams at many organisations rely on chat tools (e.g. Slack) for announcements, reminders, and wins. These messages are ephemeral and get buried quickly, leaving dashboards, bots, and late-arriving team members with no reliable way to surface "what is active this week." A lightweight, queryable notice board solves this by providing a durable, structured store for short-form team notices.

The **Team Notice Board API** (`gitlab-pipeline-smoke`) is a FastAPI + PostgreSQL service that lets anyone read active notices and lets authorised organisers create, update, and archive them. Authentication is intentionally minimal — a single shared API key loaded from the environment — keeping the surface area small while still enforcing write-access control. The service exposes a full OpenAPI spec at `/docs` and is designed to be embedded in dashboards, Slack bots, or any HTTP client without a bespoke login flow.

This application also serves as the canonical **Pattern B** (Postgres CRUD + API-key auth) smoke-test target for the internal SDLC agent chain (`product-agent → architect-agent → database-agent → developer-agent → gitlab-agent`). It is intentionally scoped so that every agent stage produces real, verifiable artefacts — SQL migrations, Python routes, pytest suites, and a GitLab branch publish — without introducing LLM, vector-search, or UI complexity.

---

## 2. Goals & Success Metrics

| Goal | Metric | Target | Notes |
|------|--------|--------|-------|
| Reliable notice retrieval | `GET /notices` returns only genuinely active notices | Zero stale/expired/archived notices in default response | Verified by `active_only=true` filter tests |
| Organiser write access enforced | Unauthorised write attempts rejected | 100 % of write requests without valid `X-API-Key` return 401 | Covered by pytest auth tests |
| Fast list queries | Median latency for `GET /notices` | < 200 ms at p95 under expected load | Composite index on `(is_archived, starts_at DESC)` |
| Stable API surface for consumers | Swagger UI loads and all routes documented | `/docs` accessible and schema-complete after deploy | Manual smoke test + CI check |
| SDLC pipeline validation | Full agent chain publishes artefacts to GitLab branch | Branch `sdlc/gitlab-pipeline-smoke` contains `target-apps/`, `docs/`, handoff JSON; pytest green | gitlab-agent publish + `--list-branch-files` verification |
| Developer onboarding speed | Time from clone to running service | `uvicorn` + Swagger `/docs` working after `docker compose up` / RDS apply | README curl examples present |

---

## 3. Non-Goals / Out of Scope

- JWT authentication, user login, sessions, bcrypt, or a `users` table
- Bedrock / LLM integration of any kind
- pgvector / RAG / semantic search
- Streamlit, React, or any frontend UI folder
- Email or push notifications
- Redis caching layer
- S3 or file-upload support
- Terraform infrastructure definitions
- Automatic GitLab MR creation from `run-sdlc.ps1` (manual `--open-mr` flag exists if needed)
- Role-based access control beyond the single shared API key
- Notice deletion (rows are never deleted; archiving is the terminal state)
- Multi-tenant or per-team namespacing

---

## 4. Users & Use Cases

| Persona | Need | Primary use case |
|---------|------|------------------|
| **Anonymous Reader** (dashboard, bot, team member) | Browse current team notices without credentials | Calls `GET /notices?active_only=true` (default) or `GET /notices/{id}`; optionally filters by `category_id` or free-text `?q=` |
| **Organiser** (team lead, HR, engineering manager) | Post announcements, schedule future notices, retire stale ones | Authenticates with `X-API-Key`; calls `POST /notices`, `PATCH /notices/{id}`, `POST /notices/{id}/archive`; manages categories via `POST /categories`, `PATCH /categories/{id}` |
| **Integration Consumer** (Slack bot, internal dashboard) | Poll for active notices to surface in other tools | Calls `GET /notices` on a schedule; uses `?category_id=` to scope to relevant channel |
| **Developer / SDLC Agent** | Verify the pipeline produces a working service | Runs pytest suite; hits `/health`; inspects `/docs`; confirms GitLab branch publish |

---

## 5. Functional Requirements

| ID | Description | Priority | Acceptance criteria (Given / When / Then) |
|----|-------------|----------|-------------------------------------------|
| FR-1 | **Health endpoint** — The service exposes `GET /health` requiring no authentication and returning a fixed JSON payload. | P0 | **Given** the service is running, **When** any client sends `GET /health`, **Then** the response is `200 OK` with body `{"status":"ok","service":"gitlab-pipeline-smoke"}`. |
| FR-2 | **List active notices (default)** — `GET /notices` returns a paginated envelope of notices that are not archived, whose `starts_at` ≤ now, and whose `ends_at` is either null or > now. | P0 | **Given** the DB contains a mix of active, future, expired, and archived notices, **When** a client calls `GET /notices` (or `?active_only=true`), **Then** only notices meeting all three active conditions appear; response shape is `{items, total, limit, offset}`; expired, future, and archived notices are absent. |
| FR-3 | **Notice filtering and search** — `GET /notices` accepts `?category_id=<uuid>`, `?active_only=false`, `?q=<string>`, `?limit=<int>`, `?offset=<int>`. | P0 | **Given** notices exist across categories, **When** a client supplies `?category_id=<valid-id>`, only notices in that category are returned; **When** `?q=test` is supplied, only notices whose title or body contains "test" (case-insensitive) are returned; **When** `?active_only=false`, archived and time-filtered notices are also returned. |
| FR-4 | **Get notice by ID** — `GET /notices/{id}` returns a single notice or 404. | P0 | **Given** a notice with a known UUID exists, **When** `GET /notices/{id}` is called, **Then** `200 OK` with full notice object is returned. **Given** the ID does not exist, **Then** `404 Not Found` is returned. |
| FR-5 | **Create notice (organiser)** — `POST /notices` with a valid API key creates a new notice; `starts_at` defaults to now if omitted; returns `201 Created`. | P0 | **Given** a valid `X-API-Key` header, **When** `POST /notices` is called with valid fields and a known `category_id`, **Then** `201` is returned with the created notice including a server-generated UUID and timestamps. **When** `ends_at` < `starts_at`, **Then** `422 Unprocessable Entity`. **When** `category_id` is unknown, **Then** `404 Not Found`. |
| FR-6 | **Update notice (organiser)** — `PATCH /notices/{id}` with a valid API key updates any supplied fields and bumps `updated_at`. | P0 | **Given** a valid API key and an existing notice, **When** `PATCH /notices/{id}` is called with a subset of fields, **Then** only those fields are changed, `updated_at` is refreshed, and `200 OK` with the updated object is returned. Same `ends_at < starts_at` and unknown `category_id` validations apply. |
| FR-7 | **Archive notice (organiser)** — `POST /notices/{id}/archive` sets `is_archived=true`; operation is idempotent. | P0 | **Given** a valid API key, **When** `POST /notices/{id}/archive` is called on an existing notice (archived or not), **Then** `204 No Content` is returned and the notice no longer appears in `active_only=true` list results. Calling again on an already-archived notice still returns `204`. |
| FR-8 | **API-key enforcement on write routes** — All `POST` and `PATCH` routes (except `/health`) require `X-API-Key` matching the server-side `API_KEY` env var. | P0 | **Given** a write route is called **without** `X-API-Key` (or with a wrong key), **When** the request is processed, **Then** `401 Unauthorized` is returned and no data is modified. **Given** the correct key, the request proceeds normally. |
| FR-9 | **Category management (organiser)** — `POST /categories` creates a category (201); `PATCH /categories/{id}` updates name/description; `GET /categories` lists all sorted by name; `GET /categories/{id}` returns one or 404; duplicate name → 409. | P1 | **Given** a valid API key, **When** `POST /categories` is called with a name not yet in use, **Then** `201` with the new category. **When** the same name (case-sensitive) is submitted again, **Then** `409 Conflict`. **When** `PATCH /categories/{id}` would cause a name collision, **Then** `409`. `GET /categories` requires no auth and returns all categories sorted alphabetically by name. |
| FR-10 | **Pagination envelope** — All list endpoints return `{items: [...], total: <int>, limit: <int>, offset: <int>}`. | P1 | **Given** 10 notices exist and `?limit=3&offset=0` is supplied, **When** `GET /notices` is called, **Then** `items` contains 3 records, `total` reflects the unfiltered-by-page count matching the active filter, `limit=3`, `offset=0`. |
| FR-11 | **Seed data present in dev environment** — The database seed script inserts 3 categories (General, HR, Engineering) and 5 notices (mix of active, future `starts_at`, expired `ends_at`, and archived) using stable UUIDs with `ON CONFLICT DO NOTHING`. | P1 | **Given** the seed script is run against a fresh schema, **When** `GET /notices?active_only=false` is called, **Then** exactly 5 notices are present. **When** run a second time, no duplicates or errors occur. |
| FR-12 | **OpenAPI documentation** — The service exposes Swagger UI at `/docs` and ReDoc at `/redoc` with all routes, request bodies, response models, and error codes documented. | P1 | **Given** the service is running, **When** a browser navigates to `/docs`, **Then** the Swagger UI loads and lists all 10+ route operations with their schemas and authentication requirements. |
| FR-13 | **Environment-based configuration** — All runtime parameters (`DATABASE_URL`, `POSTGRES_SCHEMA`, `API_KEY`, `PORT`) are loaded from environment variables via pydantic-settings; `.env.example` ships with the repository. | P1 | **Given** `.env.example` is copied to `.env` and values filled in, **When** `uvicorn app.main:app --reload --port 8000` is executed, **Then** the service starts and `/health` returns `200` without any code changes. |
| FR-14 | **Pytest suite with SQLite in-memory backend** — The test suite uses FastAPI `TestClient` and SQLite in-memory so no Postgres instance is required for CI. Tests cover all specified scenarios. | P1 | **Given** `pytest` is run with no external services, **When** the suite executes, **Then** all tests pass covering: health, pagination shape, create category/notice with key, write without key → 401, `active_only` filter, archive endpoint, `?q=` search, duplicate category → 409, `ends_at` < `starts_at` → 422. |
| FR-15 | **Cannot create notice referencing non-existent category** — `POST /notices` with an unknown `category_id` returns 404; `PATCH /notices/{id}` changing `category_id` to an unknown value also returns 404. | P1 | **Given** a valid API key, **When** `POST /notices` is called with a `category_id` UUID that does not exist in `categories`, **Then** `404 Not Found` is returned and no notice row is inserted. |

---

## 6. Non-Functional Requirements

| ID | Category | Target | Measurement / verification | Notes |
|----|----------|--------|---------------------------|-------|
| NFR-1 | Performance | `GET /notices` p95 latency < 200 ms | Load test with representative dataset (500 notices); measure via uvicorn access logs or APM | Composite index on `(is_archived, starts_at DESC)` required; (Assumption) |
| NFR-2 | Performance | Service startup time < 5 s | Timed from `uvicorn` launch to first successful `/health` response | (Assumption) |
| NFR-3 | Security / Auth | Missing or incorrect `X-API-Key` on write routes returns `401` in ≤ 50 ms without leaking key value in response body | Verified by FR-8 pytest test; manual inspection of error response body | API_KEY must not appear in logs or response payloads |
| NFR-4 | Security / Secrets | `API_KEY` and `DATABASE_URL` are never hard-coded in source; loaded exclusively from env | Code review / CI secret-scan lint rule; `.env` in `.gitignore` | `.env.example` ships with placeholder value `dev-api-key-change-me` |
| NFR-5 | Availability | Service returns `200 /health` after restart within 10 s | Verified in CI smoke test after container restart | (Assumption) target for dev/staging; production SLA TBD |
| NFR-6 | Scalability | Schema and query design supports ≥ 10 000 notice rows without query plan degradation | `EXPLAIN ANALYZE` on list query with 10 k rows; index usage confirmed | Composite index + optional future pagination cursor; (Assumption) |
| NFR-7 | Observability | All HTTP requests logged with method, path, status code, and latency | uvicorn access log enabled by default; verify in local run | Structured JSON logging recommended for production; (Assumption) |
| NFR-8 | Compliance / Data retention | Notice rows are never physically deleted; archiving is the only terminal state | Code review confirms absence of `DELETE` route for notices; verified in schema | Categories protected by `ON DELETE RESTRICT` FK |
| NFR-9 | Operability | Service fully configurable via env vars; no config files require editing to change DB URL, schema, port, or key | FR-13 test; `docker compose up` with overridden env confirms | Pydantic-settings validation raises clear error on missing required vars |
| NFR-10 | Compatibility | Python 3.12, FastAPI latest stable, Pydantic v2, SQLAlchemy 2.x sync, psycopg[binary]; no boto3, no pgvector, no JWT libraries in `requirements.txt` | `pip check`; `grep` for prohibited packages in `requirements.txt` | Prohibited packages: boto3, pgvector, python-jose, passlib, bcrypt |
| NFR-11 | Testability | Pytest suite runs to completion with zero external dependencies (SQLite in-memory) | `pytest` passes in a clean CI environment with only `pip install -r requirements.txt` | SQLAlchemy dialect guard in `database.py` required |

---

## 7. Data & Integrations

### Core Entities

**`categories`**
| Column | Type | Constraints |
|--------|------|-------------|
| `id` | `uuid` | PK, default `gen_random_uuid()` |
| `name` | `text` | NOT NULL, UNIQUE, 1–60 chars |
| `description` | `text` | nullable, max 240 chars |
| `created_at` | `timestamptz` | NOT NULL, DEFAULT now() |

**`notices`**
| Column | Type | Constraints |
|--------|------|-------------|
| `id` | `uuid` | PK, default `gen_random_uuid()` |
| `category_id` | `uuid` | FK → `categories.id` ON DELETE RESTRICT |
| `title` | `text` | NOT NULL, 1–120 chars |
| `body` | `text` | NOT NULL, 1–4 000 chars (markdown plain text) |
| `author_name` | `text` | NOT NULL, 1–80 chars |
| `starts_at` | `timestamptz` | nullable; defaults to `now()` on create if omitted |
| `ends_at` | `timestamptz` | nullable |
| `is_archived` | `bool` | NOT NULL, DEFAULT false |
| `created_at` | `timestamptz` | NOT NULL, DEFAULT now() |
| `updated_at` | `timestamptz` | NOT NULL, DEFAULT now(); bumped on every PATCH |

**Index:** `CREATE INDEX ON notices (is_archived, starts_at DESC);`

**Schema:** All tables live in `POSTGRES_SCHEMA=gitlab_pipeline_smoke`.

### External Integrations

| System | Role | Notes |
|--------|------|-------|
| PostgreSQL (RDS or local) | Primary data store | Connection via `DATABASE_URL` env var; `postgresql+psycopg://` with `?sslmode=require` for non-local |
| SQLite (in-memory) | Test-only data store | Activated by SQLAlchemy dialect guard in `database.py` when `DATABASE_URL` starts with `sqlite` |
| GitLab monorepo | Artefact publish target | Branch `sdlc/gitlab-pipeline-smoke`; paths published by gitlab-agent |

### File Layout

```
target-apps/gitlab-pipeline-smoke/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── dependencies.py
│   ├── database.py
│   ├── models/
│   ├── schemas/
│   └── routers/
│       ├── health.py
│       ├── categories.py
│       └── notices.py
├── db/
│   └── sql/
│       ├── 001_schema.sql
│       └── 002_seed.sql
├── tests/
├── .env.example
├── requirements.txt
└── README.md
```

---

## 8. Analytics & Observability

| Concern | Approach | Notes |
|---------|----------|-------|
| Access logging | uvicorn built-in access log (method, path, status, latency) | Enabled by default; no additional middleware required for MVP |
| Error logging | Python `logging` module; unhandled exceptions logged at ERROR level with traceback | FastAPI exception handlers should log before returning HTTP error response |
| Health monitoring | `GET /health` polled by uptime monitor or CI smoke test | Returns `{"status":"ok","service":"gitlab-pipeline-smoke"}`; no DB ping in MVP health check (Assumption) |
| Query observability | SQLAlchemy `echo=False` in production; set `echo=True` via env flag for local debugging | (Assumption) `SQL_ECHO=false` env var |
| Key metrics to track (future) | Notice create/archive rate, active notice count by category, 4xx/5xx rates | Out of scope for MVP; noted for Phase 2 instrumentation |
| GitLab pipeline artefact | `agents/pipeline/gitlab-pipeline-smoke.gitlab-handoff.json` with `pathsPublished` list | Published by gitlab-agent as pipeline completion evidence |

---

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| API key exposed in logs or version control | High — unauthorised organiser writes | `.env` in `.gitignore`; `verify_api_key` dependency never logs key value; `.env.example` uses obvious placeholder |
| SQLite ↔ Postgres dialect mismatch causes silent test failures | Medium — tests pass locally but fail on Postgres | `database.py` dialect guard explicitly tested; CI should also run a Postgres integration job (Phase 2) |
| `ends_at` timezone handling inconsistency | Medium — notices shown after they expire, or hidden early | All timestamps stored as `timestamptz`; server always compares against `now()` in UTC; Pydantic schemas enforce timezone-aware datetimes |
| `ON DELETE RESTRICT` on `category_id` FK prevents category cleanup | Low — organiser frustration | Document constraint in README; add PATCH to reassign notices before category deletion if needed (Phase 2) |
| Agent chain produces non-compiling code artefacts | High for pipeline validation goal | Developer-agent must run `pytest` and confirm green before gitlab-agent publishes; handoff JSON records test result |
| GitLab branch publish MCP content errors | Medium — pipeline smoke test fails | gitlab-agent validates `pathsPublished` list against actual branch tree; `--list-branch-files` verification step documented in README |
| Large `body` field (4 000 chars) causes slow `?q=` search at scale | Low for MVP dataset | Case-insensitive `ILIKE` on indexed columns acceptable for small tables; full-text search (tsvector) noted as Phase 2 option |

---

## 10. Open Questions

| # | Question | Suggested owner |
|---|----------|-----------------|
| 1 | Should `GET /health` perform a DB connectivity check (ping), or remain a static response only? A DB ping adds reliability signal but introduces a dependency that could mask app vs. DB failure modes. | Tech Lead / Architect-agent |
| 2 | Is `ON CONFLICT DO NOTHING` in seed sufficient, or should the seed script be idempotent via upsert (to refresh body text of seed notices in dev)? | Database-agent |
| 3 | What is the expected maximum number of concurrent organiser writers? Determines whether row-level locking on PATCH is needed. | Product / Architect-agent |
| 4 | Should `PATCH /notices/{id}` allow changing `is_archived` back to `false` (un-archiving), or is archive a one-way operation? | Product owner |
| 5 | Is `category_id` mandatory on `GET /notices` filter, or should a future endpoint support "notices without a category"? | Product owner |
| 6 | Should `author_name` be free-text (current design) or eventually validated against a team directory? | Product owner |
| 7 | What is the retention policy for archived notices — should they be purged after N days in production? | Platform / Compliance |
| 8 | Is `?active_only=false` intended to be restricted to organisers, or remain public? | Product owner |
| 9 | Should the GitLab CI pipeline for this repo include a Postgres service container for integration tests, or remain SQLite-only? | DevOps / gitlab-agent |
| 10 | Does `sslmode=require` apply in all environments including local Docker Compose, or only when connecting to RDS? | Infrastructure / Developer-agent |

---

## 11. Delivery & Client Surface

| Concern | Choice | Implementation notes |
|---------|--------|---------------------|
| Client UI | **API-only (Swagger at `/docs`)** | No Streamlit, no React, no HTML templates; UI is the OpenAPI explorer only |
| API framework | **FastAPI** under `target-apps/gitlab-pipeline-smoke/` | REST + full OpenAPI 3.1 schema auto-generated |
| API docs URL | `/docs` (Swagger UI), `/redoc` (ReDoc) | Both enabled by default in FastAPI; no auth required to view |
| Auth for write routes | **API key via `X-API-Key` header** | `verify_api_key` dependency injected on all POST/PATCH routers; loaded from `API_KEY` env via pydantic-settings |
| Auth for read routes | **None** | Anonymous access to all GET routes and `/health` |
| Database driver | `psycopg[binary]` with `postgresql+psycopg://` URL | `?sslmode=require` appended for non-local connections |
| ORM | SQLAlchemy 2.x sync | Dialect guard in `database.py` switches to SQLite for pytest |
| Schema isolation | `POSTGRES_SCHEMA=gitlab_pipeline_smoke` | Set via `search_path` on connection or SQLAlchemy `schema=` argument |
| Configuration | pydantic-settings loading `.env` | `.env.example` ships with `DATABASE_URL`, `POSTGRES_SCHEMA`, `API_KEY=dev-api-key-change-me`, `PORT=8000` |
| Test runner | pytest + `TestClient` + SQLite in-memory | No external services required in CI for unit tests |
| Target output directory | `target-apps/gitlab-pipeline-smoke/` | All app, DB, and test files rooted here in the monorepo |
| GitLab publish branch | `sdlc/gitlab-pipeline-smoke` | gitlab-agent publishes `docs/`, `target-apps/`, `agents/pipeline/` paths |
| Handoff artefact | `agents/pipeline/gitlab-pipeline-smoke.gitlab-handoff.json` | Contains `pathsPublished` list; authored by gitlab-agent at pipeline completion |

---

## Appendix: Assumptions

- The `GET /health` endpoint returns a static JSON response and does **not** ping the database; this keeps the health check fast and decoupled (Open Question 1).
- `starts_at` is set to the server's `now()` on notice creation when omitted by the caller; the server time zone is UTC.
- All timestamp comparisons for `active_only` filtering are performed in the database query using `now()` (server-side), not in application code.
- `PATCH` on notices is a partial update (only supplied fields are changed); missing fields in the request body are left unchanged.
- Archiving a notice is a one-way operation in MVP; un-archiving is not supported unless the product owner confirms otherwise (Open Question 4).
- `?active_only=false` is publicly accessible (no API key required) in MVP, consistent with the stated anonymous read permissions.
- The composite index `(is_archived, starts_at DESC)` is the only explicit performance index required for MVP dataset sizes.
- `updated_at` is bumped by the application layer (not a DB trigger) to maintain SQLite compatibility in tests.
- The service runs on `PORT=8000` by default; `uvicorn` is invoked with `--port ${PORT}`.
- p95 latency target of 200 ms and availability restart target of 10 s are reasonable defaults for an internal tool; production SLAs are not yet defined.
- `SQL_ECHO` env var (default `false`) controls SQLAlchemy query logging in the local development environment.
- No rate limiting is implemented in MVP; the service is intended for internal use with low concurrency.
- The `.env` file is added to `.gitignore` by default; `.env.example` is committed.
- Full-text search (PostgreSQL `tsvector`) is deferred to Phase 2; MVP uses `ILIKE` for `?q=` matching.
- The developer-agent must confirm `pytest` passes before the gitlab-agent publishes artefacts; this is enforced by the handoff JSON contract between agents.
