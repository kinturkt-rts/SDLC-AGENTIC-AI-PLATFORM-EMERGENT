# Student Management API — Product Requirements Document

## 1. Overview

Student information is currently maintained across disconnected spreadsheets, requiring manual effort to update and leaving no single authoritative source of truth. Errors, duplication, and stale records are common pain points for administrative staff.

The proposed solution is a lightweight, internal RESTful API that centralises student record management. Staff and authorised internal systems interact with the service exclusively through a documented HTTP API (Swagger/OpenAPI), with no browser UI required in v1. All writes are protected by API-key authentication, while read-only endpoints are available to authorised internal consumers.

The v1 scope covers full CRUD operations on student records, soft-deletion (deactivation), filtering by course or status, and a demo-data seeding endpoint. Persistent storage ensures records survive restarts, and all secrets are kept out of source code.

---

## 2. Goals & Success Metrics

| Goal | Metric | Target | Notes |
|------|--------|--------|-------|
| Centralise student records | % of student data migrated from spreadsheets | 100 % within agreed migration window | Migration timeline TBD |
| Enable reliable CRUD operations | API success rate (2xx) for valid requests | ≥ 99.5 % | Measured over rolling 7-day window |
| Protect write operations | Unauthorised write attempts rejected | 100 % of requests without valid API key return 401 | Verified by automated tests |
| Preserve historical records | Deactivated students retrievable | 100 % of deactivated records visible via history/filter queries | Core business rule |
| Accelerate staff workflows | Time to create or update a student record | < 2 minutes end-to-end (API call + confirmation) | Replaces multi-step spreadsheet process |
| Demonstrate capability | Demo seeding runs without error | Seed endpoint populates ≥ 3 sample records cleanly | Useful for onboarding and demos |

---

## 3. Non-Goals / Out of Scope

- Browser-based or mobile UI (Streamlit, React, or any front-end) — not in v1
- Single Sign-On (SSO) or OAuth2 / student self-service login
- Attendance tracking, grade recording, or class-schedule management
- Customer-facing or public-facing access
- Hard (permanent) deletion of student records
- Bulk import from spreadsheets (migration tooling is a separate concern)
- Role-based access control beyond read vs. write API-key tiers
- Email notifications or integrations with external SIS platforms

---

## 4. Users & Use Cases

| Persona | Need | Primary use case |
|---------|------|------------------|
| Administrative Staff | Create and maintain accurate student records | Calls the API to enrol a new student, update course assignment, or deactivate a student who has withdrawn |
| Authorised Internal System / Integration | Read student data to power downstream processes | Queries the list or individual student endpoint with a read-scoped API key |
| Operations / DevOps | Verify the service is healthy without credentials | Hits the unauthenticated `/health` endpoint from monitoring tooling |
| Developer / QA | Explore and test the API during onboarding or regression | Uses the auto-generated Swagger UI at `/docs` to inspect schemas and run sample calls |

---

## 5. Functional Requirements

| ID | Description | Priority | Acceptance criteria (Given / When / Then) |
|----|-------------|----------|-------------------------------------------|
| FR-1 | **Create a student record** — Accept `student_id`, `full_name`, `email`, `course`, `enrollment_date`, and `status` (defaults to `active`). `student_id`, `full_name`, `email`, and `course` are required. | P0 | **Given** a valid API key and a payload with all required fields and a non-future `enrollment_date`; **When** `POST /students` is called; **Then** the API returns `201 Created` with the full student object, and the record is persisted. |
| FR-2 | **Enforce uniqueness of `student_id` and `email`** — Reject any create or update request that would duplicate an existing `student_id` or `email` across all records (including inactive). | P0 | **Given** a `student_id` or `email` that already exists in the data store; **When** a `POST /students` or `PUT /students/{id}` is submitted; **Then** the API returns `409 Conflict` with a descriptive error message and no record is created or modified. |
| FR-3 | **Retrieve a single student** — Return the full student object by `student_id`, including inactive records. | P0 | **Given** a valid API key and an existing `student_id`; **When** `GET /students/{student_id}` is called; **Then** the API returns `200 OK` with the full student object. When the ID does not exist, return `404 Not Found`. |
| FR-4 | **List all students with optional filtering** — Return a paginated or full list of students; support query parameters `course` and `status` to filter results. | P0 | **Given** a valid API key; **When** `GET /students` is called (optionally with `?course=<value>` and/or `?status=<value>`); **Then** the API returns `200 OK` with an array of matching student objects. An empty result set returns `200 OK` with an empty array, not a 404. |
| FR-5 | **Update student details** — Allow authorised staff to modify `full_name`, `email`, `course`, `enrollment_date`, and `status` for an existing student. `student_id` is immutable after creation. | P0 | **Given** a valid write API key and an existing `student_id`; **When** `PUT /students/{student_id}` is called with one or more updatable fields; **Then** the API returns `200 OK` with the updated student object, and changes are persisted. Attempts to change `student_id` return `400 Bad Request`. |
| FR-6 | **Deactivate a student (soft delete)** — Set a student's `status` to `inactive` without removing the record from the data store. | P0 | **Given** a valid write API key and an active `student_id`; **When** `PATCH /students/{student_id}/deactivate` is called; **Then** the API returns `200 OK`, the record's `status` is `inactive`, and the record is still retrievable via `GET /students/{student_id}`. |
| FR-7 | **Reject writes without a valid API key** — All state-changing endpoints (`POST`, `PUT`, `PATCH`) must require a valid API key passed in the request header. | P0 | **Given** a request to any write endpoint with a missing, malformed, or invalid API key; **When** the request is processed; **Then** the API returns `401 Unauthorized` and no data is created or modified. |
| FR-8 | **Validate `enrollment_date` is not in the future** — Reject any create or update request where `enrollment_date` is a date after the current server date. | P0 | **Given** a payload where `enrollment_date` is tomorrow or later; **When** `POST /students` or `PUT /students/{student_id}` is called; **Then** the API returns `422 Unprocessable Entity` with a field-level validation error. |
| FR-9 | **Seed demo data** — Provide a dedicated endpoint that inserts a predefined set of ≥ 3 sample student records for demonstration purposes. The endpoint must be idempotent (re-running it should not duplicate existing seed records). | P1 | **Given** a valid write API key; **When** `POST /students/seed` is called; **Then** the API returns `200 OK`, at least 3 sample students exist in the data store, and calling the endpoint a second time does not create duplicate records. |
| FR-10 | **Health check endpoint** — Expose an unauthenticated endpoint that returns service health status and confirms database connectivity. | P0 | **Given** no API key; **When** `GET /health` is called; **Then** the API returns `200 OK` with a JSON body indicating service status (e.g., `{"status": "ok"}`). If the data store is unreachable, return `503 Service Unavailable`. |
| FR-11 | **OpenAPI / Swagger documentation** — The API must auto-generate and serve interactive Swagger documentation at `/docs`. | P0 | **Given** the service is running; **When** a user navigates to `/docs`; **Then** a fully rendered Swagger UI is displayed listing all endpoints, request schemas, and response schemas with no rendering errors. |

---

## 6. Non-Functional Requirements

| ID | Category | Target | Measurement / verification | Notes |
|----|----------|--------|---------------------------|-------|
| NFR-1 | Performance | p95 response latency ≤ 300 ms for all endpoints under normal load | Load test with representative concurrency; monitor via APM or logs | (Assumption) — no load figures provided in brief |
| NFR-2 | Availability | 99.5 % uptime during business hours | Uptime monitoring alert on consecutive failures; reviewed weekly | (Assumption) — internal service, non-critical SLA |
| NFR-3 | Security / Authentication | All write endpoints return `401` for invalid or absent API keys; keys must never appear in source code or logs | Automated auth tests in CI; secret scanning in repo pipeline | API keys stored in environment variables or a secrets manager |
| NFR-4 | Security / Secrets management | No credentials, API keys, or connection strings committed to version control | Pre-commit hooks + CI secret scanning (e.g., `detect-secrets`) | Constraint explicitly stated in brief |
| NFR-5 | Data persistence | Student records survive service restarts and redeployments | Integration test: create record → restart service → verify record exists | Persistent database required (engine TBD — see Open Questions) |
| NFR-6 | Scalability | Service must handle ≥ 50 concurrent internal users without degradation | Verified via load test prior to production rollout | (Assumption) — actual concurrency TBD |
| NFR-7 | Observability | All inbound requests logged with method, path, status code, and latency; errors logged with stack trace | Log aggregation reviewed; alert on sustained 5xx rate > 1 % | (Assumption) — specific log platform TBD |
| NFR-8 | Compliance / Data retention | Deactivated student records are retained indefinitely and never hard-deleted | Automated test confirms deactivated records are retrievable post-deactivation | Stems from business rule in brief |
| NFR-9 | Operability | Service must be startable with a single command and configurable entirely via environment variables | Verified in onboarding runbook; tested in CI | Supports 12-factor app principles |
| NFR-10 | Maintainability | Code must include an automated test suite (unit + integration) covering all P0 FRs | CI pipeline enforces all tests pass before merge; coverage ≥ 80 % | (Assumption) — target coverage threshold |

---

## 7. Data & Integrations

### Core Entity: `Student`

| Field | Type | Constraints |
|-------|------|-------------|
| `student_id` | String / UUID | Required; unique; immutable after creation |
| `full_name` | String | Required; non-empty |
| `email` | String (email format) | Required; unique across all records |
| `course` | String | Required; non-empty |
| `enrollment_date` | Date | Required; must not be in the future |
| `status` | Enum (`active`, `inactive`) | Defaults to `active` on creation |
| `created_at` | Timestamp | Set by system on record creation |
| `updated_at` | Timestamp | Updated by system on every modification |

### External Systems & Integrations

- **Database**: A persistent relational or document store is required (specific engine TBD — see Open Questions). Connection string supplied via environment variable.
- **Secrets Manager / Environment**: API keys and DB credentials injected at runtime via environment variables (e.g., `.env` file locally; secrets manager in production).
- **CI/CD Pipeline**: Automated test suite runs on each push; secret scanning enforced.
- **Monitoring / Alerting**: Log aggregation platform TBD (see Open Questions); `/health` endpoint consumed by ops monitoring tooling.
- No third-party SIS, LMS, or payment integrations in scope for v1.

---

## 8. Analytics & Observability

- **Request logging**: Every API request logged with timestamp, HTTP method, path, query parameters (PII-scrubbed), response status code, and latency.
- **Error logging**: All 4xx (unexpected) and 5xx responses logged with stack traces and request context for debugging.
- **Health metric**: `/health` endpoint monitored on a regular interval (e.g., every 60 seconds) by ops tooling; alert triggered on consecutive failures or `503` responses.
- **Key operational metrics** (to be wired into APM or log-based dashboards):
  - Request rate and error rate per endpoint
  - p50 / p95 / p99 latency per endpoint
  - Total active vs. inactive student count (queryable via the list API)
- **Audit trail**: `created_at` and `updated_at` timestamps on every record provide a lightweight audit history without a dedicated audit-log service.
- **Seed endpoint usage**: Logged distinctly to avoid skewing production record counts in metrics.

---

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| API key leaked in source code or logs | High — unauthorised write access to all student records | Enforce secrets scanning in CI; never log raw headers; rotate keys immediately if exposure detected |
| Duplicate records created before uniqueness check | Medium — data integrity degraded | Enforce unique constraints at the database level in addition to application-layer validation |
| Future-date enrollment accepted due to timezone mismatch | Low — data quality issue | Normalise all dates to UTC server time; include timezone handling in unit tests |
| Data loss on service restart (no persistence) | High — loss of all student records | Use a persistent database with regular backups; integration test verifies data survives restarts |
| Seed endpoint pollutes production data | Medium — inaccurate record counts | Gate seed endpoint behind write API key; document it as demo-only; consider environment flag to disable in production |
| Uncontrolled growth of inactive records over time | Low — storage cost, query performance | Acceptable in v1 given internal scale; revisit archival strategy in future iteration |
| Lack of rate limiting enables accidental or malicious flooding | Medium — service degradation | Add rate limiting per API key in a near-term follow-up; document as known gap in v1 |

---

## 10. Open Questions

| # | Question | Suggested owner |
|---|----------|-----------------|
| 1 | Which database engine should be used (e.g., PostgreSQL, SQLite for local dev / PostgreSQL for production, MongoDB)? | Engineering Lead |
| 2 | How are API keys issued, rotated, and revoked? Is a simple env-var key sufficient for v1, or is a key management service required? | Engineering Lead / Security |
| 3 | Should read endpoints also require an API key, or are they open to any internal network caller? Brief implies read access is "authorised" but does not specify a mechanism. | Product Owner / Security |
| 4 | What is the target hosting environment (container on internal cluster, managed cloud service, on-premise VM)? | DevOps / Infrastructure |
| 5 | What is the expected initial data volume and anticipated growth rate of student records? (Affects DB sizing and pagination defaults.) | Product Owner / Data |
| 6 | Which log aggregation and monitoring platform is in use internally (e.g., Datadog, ELK, Grafana)? | DevOps |
| 7 | Is there a data-retention or privacy policy that governs how long inactive student records must be kept? | Legal / Compliance |
| 8 | Should the seed endpoint be disabled or removed in the production environment, and if so, via what mechanism? | Engineering Lead |
| 9 | What is the agreed migration plan for moving existing spreadsheet data into the new system? | Product Owner / Admin Staff |
| 10 | Are there any internal API gateway or network-perimeter controls that should be applied in addition to API-key auth? | Security / DevOps |

---

## 11. Delivery & Client Surface

| Concern | Choice | Implementation notes |
|---------|--------|---------------------|
| Client UI | API-only (Swagger / OpenAPI) | No browser app in v1 — explicitly stated in brief. Swagger UI at `/docs` serves as the interactive exploration surface. |
| API framework | FastAPI under `target-apps/student-management/` | REST + OpenAPI auto-generated; Pydantic models for request/response validation |
| API versioning | `/api/v1/` prefix on all resource routes | Allows non-breaking future versions; `/health` remains at root |
| Auth mechanism | API key via `X-API-Key` request header | Keys loaded from environment variables; never hard-coded in source |
| Data layer | SQLAlchemy ORM (or equivalent) + persistent DB | Async-compatible if high concurrency is anticipated; migrations via Alembic |
| Configuration | All secrets and config via environment variables (`.env` locally, secrets manager in production) | No credentials in `settings.py` or any tracked file |
| Testing | `pytest` with `httpx` / `TestClient` for integration tests | Run in CI on every push; coverage gate ≥ 80 % |
| Documentation | Auto-generated OpenAPI schema at `/openapi.json`; Swagger UI at `/docs`; ReDoc at `/redoc` | No additional manual docs required for v1 |

---

## Appendix: Assumptions

- **Database engine**: PostgreSQL is assumed for production persistence; SQLite may be used for local development and testing. Not confirmed in brief.
- **API key mechanism**: A single shared write API key and optionally a separate read API key, both supplied via environment variables, are assumed sufficient for v1. No key management service assumed.
- **Read endpoint auth**: Read endpoints (`GET`) are assumed to require at minimum a valid API key (read-scoped) unless a network-perimeter control already restricts access to internal callers only.
- **Pagination**: List endpoints are assumed to return all records by default in v1 given expected small data volumes; cursor or offset pagination can be added in a future iteration.
- **`status` field values**: Only `active` and `inactive` are in scope for v1. Additional statuses (e.g., `suspended`, `graduated`) are out of scope.
- **`student_id` format**: Free-form string accepted (e.g., `STU-001`); UUID generation by the client or server is not mandated, but uniqueness is enforced.
- **Timezone**: All date/time values stored and returned in UTC.
- **Deployment environment**: Containerised deployment (Docker) is assumed as the standard packaging approach; specific orchestration platform TBD.
- **Concurrency target of 50 users**: Assumed based on "internal use only" scope; actual figure not provided.
- **Test coverage target of 80 %**: Industry-standard baseline assumed; not specified in brief.
- **Seed data idempotency**: Seed records identified by a fixed `student_id` or `email` so re-running the seed does not create duplicates.
- **No rate limiting in v1**: Noted as a risk; assumed acceptable given internal-only usage and small team.
- **`created_at` / `updated_at` fields**: Assumed to be system-managed timestamps added to every record for basic auditability.
