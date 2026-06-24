# Platform Runbook Vector Desk — PRD

## 1. Overview

Platform SRE teams supporting dozens of microservices face a recurring pain point during incidents: runbooks exist but are scattered, inconsistently structured, and difficult to search under pressure. When a PagerDuty alert fires, on-call engineers waste critical minutes grepping Confluence pages and Slack history for relevant procedures. The result is slower mean-time-to-resolution, tribal knowledge dependency, and no durable record of which runbooks actually close incidents.

The Runbook Vector Desk solves this by ingesting structured runbooks (decomposed into discrete, ordered steps), embedding them using meaning-based vector search, and exposing a purpose-built on-call console. Engineers paste an alert snippet or symptom description and receive ranked *steps* — not whole pages — with service context and excerpts. The system also supports editorial governance (draft → active → retired lifecycle), a similar-runbook duplication check, and a lightweight incident touch log so teams can observe which runbooks are actually relied upon.

This is strictly an operations runbook desk. It is not a generic wiki, ITSM platform, or auto-remediation engine. The MVP delivers a Streamlit-based role-gated UI backed by a FastAPI service, with a vector store enabling semantic search over step body text.

---

## 2. Goals & Success Metrics

| Goal | Metric | Target | Notes |
|------|--------|--------|-------|
| Reduce time-to-find relevant runbook step during incidents | Median time from alert paste to relevant step displayed | ≤ 5 seconds end-to-end | Measured via search response-time analytics |
| Ensure search surfaces useful results | Percentage of queries returning at least one result with a confidence score above threshold | ≥ 80 % of queries | Low-confidence queries tracked in admin analytics |
| Drive adoption of incident touch log | Percentage of search sessions that result in a logged incident touch | ≥ 40 % within 60 days of go-live | Baseline to be established at launch |
| Reduce duplicate/overlapping runbooks entering active state | Number of newly activated runbooks flagged by similar-runbook check | Tracked; target < 10 % proceed without editorial review | Advisory metric; editors may still activate |
| Provide admin visibility into runbook reliance | Monthly admin report on service-to-runbook usage populated with real data | 100 % of services with active runbooks appear in report | Data available within 30 days of launch |
| Maintain catalog data quality | Percentage of active runbooks linked to a catalogued service | 100 % — enforced by data model | Hard constraint |

---

## 3. Non-Goals / Out of Scope

- PagerDuty, OpsGenie, or any webhook/alert-ingestion integration; no auto-remediation or SSH access to production hosts
- Full ITSM capabilities: SLA timers, assignment routing, workflow engines, escalation policies
- PDF upload, Confluence sync, or any external wiki import
- SSO, LDAP, or OAuth integration beyond simple development-role authentication
- Public internet exposure or multi-tenant deployment
- AI-generated runbook authoring or step suggestion (beyond the optional one-liner summary on search results)
- Mobile-native application; the Streamlit UI is browser-based only
- Real-time collaborative editing or comment threads on runbook steps
- Versioned history of individual step edits (lifecycle status history is retained; field-level diff is out of scope for MVP)

---

## 4. Users & Use Cases

| Persona | Need | Primary use case |
|---------|------|-----------------|
| **Viewer (On-Call Engineer)** | Find the right remediation step fast under incident pressure; log what was used | Paste alert text → get ranked steps with excerpts → optionally filter by service → log incident touch with ticket ref |
| **Editor (Runbook Author / Senior SRE)** | Create, structure, and govern runbooks without polluting on-call search with drafts | Create draft runbook + steps → check similar-runbook panel → activate when ready → retire obsolete runbooks |
| **Admin (Platform Engineering Lead)** | Maintain service catalog integrity; monitor search health and runbook coverage | Add/edit services and catalog metadata → view search analytics (frequent queries, weak-match queries, response times) → trigger index refresh after bulk changes |
| **Public / Unauthenticated** | Verify service liveness (e.g. load balancer health probe) | Call `/health` endpoint; receive 200 OK |

---

## 5. Functional Requirements

| ID | Description | Priority | Acceptance criteria (Given / When / Then) |
|----|-------------|----------|-------------------------------------------|
| **FR-1** | **Service Catalog — CRUD** Admin can create, read, update, and delete microservice records with fields: `name` (unique), `owning_team`, `criticality_tier` (1, 2, or 3), and `active_support` (boolean). | P0 | **Given** an Admin is authenticated; **When** they submit a valid new service record; **Then** the service appears in the catalog list with all submitted fields persisted, and a 201 response is returned. **Given** a duplicate `name` is submitted; **When** the request is processed; **Then** a 409 conflict is returned and no duplicate is created. |
| **FR-2** | **Runbook Lifecycle Management** Editors can create runbooks in `draft` status, transition them to `active`, and transition `active` runbooks to `retired`. Runbooks carry: `title`, `linked_service` (must reference a catalogued service), `default_severity` (low / medium / high / critical), `short_summary`, `author`, and `lifecycle_status`. | P0 | **Given** an Editor creates a runbook; **When** saved; **Then** status defaults to `draft` and the runbook does not appear in on-call search or default browse. **Given** an Editor attempts to activate a draft with zero steps; **When** the activation request is submitted; **Then** a 422 is returned with a message stating the runbook must have at least one step. **Given** a runbook is activated; **When** status is checked; **Then** it appears in search and default browse. |
| **FR-3** | **Uniqueness Constraint — Active Runbooks per Service** The system must prevent two runbooks with identical titles from both being in `active` status for the same linked service. | P0 | **Given** an active runbook titled "Redis Connection Pool Recovery" exists for `payments-api`; **When** an Editor attempts to activate a second runbook with the same title for `payments-api`; **Then** a 409 is returned and the second runbook remains in `draft` status. |
| **FR-4** | **Runbook Step Management** Editors can create, reorder, update, and delete steps within a runbook. Each step has: `step_number` (ordered), `title`, `body_text`, `estimated_minutes` (optional integer), and `warning_callout` (optional text). | P0 | **Given** an Editor adds three steps to a draft runbook; **When** they reorder step 3 to position 1; **Then** the API returns steps in the new order and `step_number` values reflect the updated sequence. **Given** a step with no `estimated_minutes` is created; **When** retrieved; **Then** the field is null/absent and no validation error is raised. |
| **FR-5** | **Semantic Symptom Search** Authenticated Viewers (and Editors/Admins) can submit natural-language alert text and receive ranked runbook steps. Results include: `service_name`, `runbook_title`, `step_number`, `step_title`, a short body excerpt, and an optional confidence-aware one-liner summary. Only `active` runbook steps are searchable. At most one result per runbook is returned (the highest-scoring step). | P0 | **Given** active runbooks with embedded steps exist; **When** a user submits the query "Redis connection pool exhausted"; **Then** the response returns ≥ 1 result within 5 seconds, each result contains `service_name`, `runbook_title`, `step_number`, and a non-empty excerpt; no step from a `draft` or `retired` runbook appears. **Given** multiple steps from the same runbook match; **When** results are returned; **Then** only the highest-scoring step from that runbook is included. |
| **FR-6** | **Service Filter on Search** When a Viewer supplies an optional `service_id` filter alongside the query, search results are scoped to steps belonging to runbooks linked to that service only. | P1 | **Given** a service filter for `auth-gateway` is applied; **When** a symptom search is executed; **Then** all returned steps belong only to runbooks linked to `auth-gateway`; steps from other services are absent. |
| **FR-7** | **Retirement Removes Steps from Search Immediately** When an Editor retires an active runbook, that runbook's steps are removed from the search index synchronously (or within the same request/transaction) so subsequent searches do not surface them. | P0 | **Given** an active runbook is returned in a search for "Kafka consumer lag"; **When** an Editor retires that runbook; **Then** an immediately subsequent search for the same query does not return any step from that runbook. Incident touch history for that runbook is preserved and retrievable by Admins. |
| **FR-8** | **Similar-Runbook Check (Advisory)** When an Editor requests activation of a draft runbook, the API returns up to five semantically similar active runbooks (title + short summary + similarity score). The Editor may proceed with activation regardless of suggestions. | P1 | **Given** a draft runbook about "Database connection pool exhaustion" exists and two active runbooks on similar topics exist; **When** the Editor requests the similarity check endpoint; **Then** the response includes ≤ 5 similar active runbooks with `runbook_id`, `title`, and a similarity score, and includes a flag indicating whether matches were found. The Editor can then call the activation endpoint independently and it succeeds. |
| **FR-9** | **Incident Touch Log** A Viewer can record an incident touch with: `ticket_reference` (required, free text), `runbook_id` (required), `step_number` (optional), and `notes` (optional). Submission without a `ticket_reference` is rejected. | P0 | **Given** a Viewer selects a runbook from search results; **When** they submit a touch with a valid `ticket_reference`; **Then** a 201 is returned and the touch is persisted with a timestamp. **Given** a touch is submitted without `ticket_reference`; **When** processed; **Then** a 422 is returned and no record is created. |
| **FR-10** | **Admin — Service Reliance Report** Admins can query a report showing, for each service, the count of incident touches that referenced runbooks linked to that service, scoped to the past 30 days. Report is aggregated; no individual user identifiers are exposed. | P1 | **Given** incident touches exist across multiple runbooks and services; **When** an Admin requests the reliance report; **Then** the response lists each service with a `touch_count` for the rolling 30-day window; no `user_id` or personal identifier appears in the payload. |
| **FR-11** | **Admin — Search Analytics** Admins can view: (a) the most frequent search queries (top N, configurable), (b) queries that returned zero results or results below a confidence threshold (weak/no-match queries), and (c) typical search response time (median and 95th percentile). All views are aggregated; no individual attribution. | P1 | **Given** at least 20 search events have been recorded; **When** an Admin requests the analytics endpoint; **Then** the response includes a `top_queries` list with query text and frequency, a `weak_match_queries` list, and `response_time_stats` with `median_ms` and `p95_ms` fields. |
| **FR-12** | **Admin — Search Index Refresh** Admins can trigger a full re-indexing of all active runbook steps via a dedicated API action. The endpoint returns a job status; the system reports completion or error. | P1 | **Given** an Admin triggers the index refresh endpoint; **When** re-indexing completes successfully; **Then** the endpoint returns a payload indicating success and the count of steps indexed; **And** a subsequent search reflects the current active step corpus. |
| **FR-13** | **Role-Gated Streamlit UI** The Streamlit application presents role-based views: Viewer sees search, browse, and incident-touch logging; Editor additionally sees draft management, step editor, similar-runbook panel, and activate/retire controls; Admin additionally sees service catalog management, search analytics dashboard, and index refresh action. Unauthenticated users cannot access any view beyond a login screen. | P0 | **Given** a user logs in with Viewer credentials; **When** the UI loads; **Then** the Editor and Admin tabs/sections are absent or disabled. **Given** a user logs in with Editor credentials; **When** they attempt to access service catalog management; **Then** the action is unavailable in the UI and the API returns 403 if called directly. |
| **FR-14** | **Browse Active Runbooks and Steps** Viewers can browse the full list of active runbooks, filter by service, and expand a runbook to read its ordered steps (title, body, estimated minutes, warning callout). Draft and retired runbooks are not visible in this view. | P1 | **Given** a Viewer browses the runbook list filtered by `payments-api`; **When** the list loads; **Then** only active runbooks linked to `payments-api` appear; each can be expanded to show steps in correct order; no draft or retired runbook is displayed. |
| **FR-15** | **Low-Confidence Search Summary Disclosure** When the top search result's similarity score is below a defined threshold, the optional one-liner summary field is replaced with a standard low-confidence disclosure message rather than a generated interpretation. | P1 | **Given** a query is submitted for which all matching step scores are below the confidence threshold; **When** results are returned; **Then** the `summary` field contains a disclosure string (e.g., "Confidence is low — review steps carefully") rather than an inferred description; no fabricated content is returned. |

---

## 6. Non-Functional Requirements

| ID | Category | Target | Measurement / verification | Notes |
|----|----------|--------|---------------------------|-------|
| **NFR-1** | Performance — Search Latency | p95 end-to-end search response ≤ 3 s; p50 ≤ 1 s under normal load | Measured via search analytics (FR-11); verified in load test with realistic corpus (60+ steps) | (Assumption) target derived from on-call urgency context |
| **NFR-2** | Performance — Write Operations | Runbook/step create, update, retire API calls complete in ≤ 500 ms p95 | API response-time logging; verified in integration tests | (Assumption) |
| **NFR-3** | Availability | Service available ≥ 99.5 % during business and on-call hours (24 × 7 for MVP internal deployment) | Uptime tracked via `/health` endpoint polling; alerting on consecutive failures | (Assumption) internal SLA; formal SLA TBD with stakeholders |
| **NFR-4** | Security — Authentication | All endpoints except `/health` require a valid bearer token or API key; 401 returned for missing/invalid credentials | Automated test: unauthenticated request to each protected endpoint returns 401; verified in CI | (Assumption) JWT bearer for MVP; specific token lifetime TBD |
| **NFR-5** | Security — Authorization | Role enforcement: Viewer actions return 403 when attempting Editor/Admin endpoints; Editor actions return 403 on Admin-only endpoints | Automated RBAC test matrix covering each role × each protected endpoint | |
| **NFR-6** | Security — Data Privacy | Search analytics and reliance reports must never expose individual user identifiers | Code review + automated test asserting no `user_id`/`email` field present in analytics API responses | |
| **NFR-7** | Scalability | System handles corpus of up to 500 runbooks / 5,000 steps without degrading search latency beyond NFR-1 targets | Load test with synthetic corpus at 500 runbooks / 5,000 steps; measure p95 search latency | (Assumption) upper bound for MVP internal use |
| **NFR-8** | Observability | All API requests logged with: timestamp, endpoint, HTTP method, status code, response time ms, role (not user identity) | Log inspection in integration tests; structured JSON log format confirmed in CI | (Assumption) log destination (stdout / file / log aggregator) TBD |
| **NFR-9** | Observability — Search Events | Every search query logged with: query text (truncated to 500 chars), result count, top score, response time ms, service filter if applied (no user PII) | Search analytics endpoint (FR-11) returns non-empty data after seeded searches in integration test | |
| **NFR-10** | Operability — Index Refresh | Manual index refresh (FR-12) completes within 60 seconds for a corpus of 500 runbooks / 5,000 steps | Timed in integration test with max corpus; result logged | (Assumption) |
| **NFR-11** | Data Retention | Incident touch log records and retired runbook records are retained indefinitely (not purged by any automated process in MVP) | No scheduled deletion job present in codebase; verified by code review | Retention policy review deferred to post-MVP compliance review |
| **NFR-12** | Compliance / Data Handling | No production alert data, PII, or credentials are stored in the vector index or analytics tables; query text is stored for analytics but treated as operational data, not personal data | Data model review; DPA assessment deferred to post-MVP | (Assumption) internal tooling; formal data classification TBD |

---

## 7. Data & Integrations

### Core Entities

| Entity | Key Fields | Notes |
|--------|-----------|-------|
| `Service` | `id`, `name` (unique), `owning_team`, `criticality_tier` (1–3), `active_support` (bool) | Managed by Admin only |
| `Runbook` | `id`, `title`, `service_id` (FK → Service), `default_severity`, `short_summary`, `author`, `lifecycle_status` (draft / active / retired), `created_at`, `updated_at` | Unique constraint: (title, service_id, status=active) |
| `RunbookStep` | `id`, `runbook_id` (FK), `step_number` (ordered int), `title`, `body_text`, `estimated_minutes` (nullable int), `warning_callout` (nullable text) | Body text is the primary source for vector embedding |
| `IncidentTouch` | `id`, `runbook_id` (FK), `step_number` (nullable), `ticket_reference` (required), `notes` (nullable), `created_at` | No user PII stored; role recorded as string |
| `SearchEvent` | `id`, `query_text` (truncated 500 chars), `service_filter_id` (nullable FK), `result_count`, `top_score`, `response_time_ms`, `created_at` | Aggregated for analytics; no user identity |
| `VectorIndex` | Embedding per `RunbookStep` keyed by `step_id`; metadata: `runbook_id`, `service_id`, `lifecycle_status` | Only `active` steps indexed; retired steps removed on retirement |

### Integrations

| System | Direction | Purpose | Notes |
|--------|-----------|---------|-------|
| Vector store / embedding model | Internal | Embed step `body_text`; query by similarity at search time | Specific vector DB and embedding model TBD (see Open Questions) |
| Relational database | Internal | Persist all entities above | Database engine TBD (see Open Questions) |
| Streamlit UI | Outbound HTTP | Calls FastAPI backend over REST; no direct DB or `app/` imports | UI at `ui/streamlit_app.py` |
| `/health` endpoint | Inbound | Load balancer / monitoring health probe | Returns 200 + JSON status; unauthenticated |

No external system integrations (PagerDuty, Confluence, SSO) are in scope for MVP.

---

## 8. Analytics & Observability

**Search Analytics (operational)**
- Every call to the symptom search endpoint writes a `SearchEvent` record (query text capped at 500 chars, result count, top score, response time, optional service filter).
- Admin analytics endpoint aggregates `SearchEvent` records to produce: top-N query terms by frequency, queries with zero results or top score below confidence threshold, median and p95 response times.
- All aggregations are time-windowed; default window is rolling 30 days.

**Incident Touch Analytics**
- Admin reliance report aggregates `IncidentTouch` records grouped by `service_id` (via `runbook.service_id`) over a rolling 30-day window, returning touch counts per service.

**Application Logging**
- Structured JSON logs emitted to stdout for every API request: timestamp, method, path, HTTP status, response time ms, role (not user identity).
- Log destination (stdout → log aggregator or file) is deployment-configuration concern; not hardcoded.

**Alerts (Assumptions)**
- `/health` endpoint polled at a configurable interval; consecutive failures trigger an operational alert.
- Index refresh failures logged at ERROR level; Admin UI surfaces the error status returned by FR-12.

**No individual user tracking**: analytics tables store no `user_id`, `email`, or other personal identifier.

---

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Vector search returns low-relevance results for terse or highly technical alert snippets | On-call engineers distrust the tool and revert to grep workflows | Implement confidence score disclosure (FR-15); surface weak-match analytics to Admin (FR-11); invest in quality demo data with realistic alert phrasings to tune threshold before launch |
| Embedding model or vector store adds unacceptable latency at search time | p95 exceeds 3-second target (NFR-1); on-call experience degraded | Benchmark candidate vector stores early in development; pre-filter by service before vector similarity; cache embeddings for query terms seen in recent `SearchEvent` history |
| Index drift — active runbooks edited but index not refreshed | Stale search results mislead on-call engineers | Trigger incremental re-index on runbook activation and step save; provide Admin manual refresh (FR-12) as backstop; surface index-age timestamp in Admin UI |
| Duplicate / overlapping runbooks pollute search ranking | Multiple conflicting procedures returned for same symptom | Similar-runbook check (FR-8) surfaces conflicts before activation; Admin analytics highlight frequently co-returned runbooks |
| Retirement of a runbook during an active incident | On-call loses access to steps mid-incident if they reload | Document operational guidance: do not retire runbooks during declared incidents; consider a "pinned session" cache as a post-MVP enhancement |
| Role bypass via direct API calls from Streamlit-savvy users | Privilege escalation (e.g., Viewer activating runbooks) | Authorization enforced at API layer (NFR-5), not UI layer only; Streamlit UI is a convenience surface, not the security boundary |
| Incident touch log data quality | Touches logged with junk ticket references; analytics become unreliable | Enforce `ticket_reference` as required field (FR-9); optionally add lightweight format hint (e.g., prefix pattern) configurable by Admin post-MVP |
| Demo data insufficient to showcase ranking and overlap detection | Stakeholder demos fail to illustrate value | Demo data spec (8–10 services, 12–15 runbooks, 60+ steps with overlapping topics) codified in seed script; reviewed by PM before demo |

---

## 10. Open Questions

| # | Question | Suggested owner |
|---|----------|-----------------|
| 1 | Which vector store and embedding model should be used (e.g., local FAISS + sentence-transformers, Chroma, pgvector, hosted API)? Affects latency, ops burden, and offline availability. | Platform Engineering / Architect |
| 2 | What is the relational database engine for MVP (e.g., PostgreSQL, SQLite for local dev)? | Platform Engineering |
| 3 | What authentication mechanism should be used for the development/MVP deployment — hardcoded dev tokens, a simple API key store, or a lightweight JWT issuer? SSO is out of scope but minimal auth is required. | Platform Engineering / Security |
| 4 | What is the confidence-score threshold below which the low-confidence disclosure (FR-15) triggers? Should it be a fixed value or configurable by Admin? | Product + ML/Search lead |
| 5 | How should the optional one-liner search summary be generated — a local LLM, a hosted LLM API call, or a rule-based excerpt? What are the latency and cost constraints? | Product + Platform Engineering |
| 6 | What is the maximum length of `body_text` for a runbook step — is there a practical cap for embedding quality and API payload size? | Search/ML lead |
| 7 | Should the similar-runbook check (FR-8) be triggered automatically on the activation request, or should it be a separate advisory endpoint the Editor calls explicitly before activating? | Product |
| 8 | What is the desired index refresh strategy — incremental (on each activation/step save) vs. batch (Admin-triggered only)? A hybrid approach is assumed but needs confirmation. | Platform Engineering |
| 9 | Are there data retention or audit requirements for incident touch records or search event logs beyond "retain indefinitely for MVP"? (Legal / compliance review deferred.) | Legal / Compliance |
| 10 | What defines "top N" in search analytics — is N fixed (e.g., 25) or configurable per Admin request? | Product |
| 11 | Should retired runbooks' steps remain in the `IncidentTouch` records with full context, or should they be anonymized/summarized if the runbook is eventually purged post-MVP? | Product / Legal |
| 12 | Is there a required format or validation pattern for `ticket_reference` (e.g., must match `INC-\d+`), or is free text acceptable for MVP? | Platform Engineering / SRE lead |

---

## 11. Delivery & Client Surface

| Concern | Choice | Implementation notes |
|---------|--------|---------------------|
| Client UI | **Streamlit** | Role-gated; four functional areas: On-Call Search, Browse, Editor workspace, Admin dashboard |
| UI location | `ui/streamlit_app.py` | HTTP client calls FastAPI backend only — never imports `app/` modules directly |
| Auth for UI | API key or JWT Bearer (per Open Question 3) | Token stored in Streamlit `st.session_state`; role decoded from token to determine visible UI sections |
| API | FastAPI under `target-apps/runbook-vector-desk/` | REST + OpenAPI (auto-generated Swagger UI); all business logic and RBAC enforced here |
| API versioning | `/api/v1/` prefix | Allows non-breaking UI iteration |
| Vector index | Embedded within API service for MVP | Refresh triggered via Admin endpoint (FR-12); decoupled store considered post-MVP |
| Demo / seed data | Seed script at `target-apps/runbook-vector-desk/seed.py` | Produces 8–10 services, 12–15 runbooks, 60+ steps, sample search events and incident touches per brief |
| Health endpoint | `GET /health` — unauthenticated | Returns `{"status": "ok", "version": "..."}` |
| Streamlit role views | Viewer: Search tab + Browse tab + Log Incident Touch; Editor: adds Draft Management + Step Editor + Similar-Runbook Panel + Activate/Retire; Admin: adds Service Catalog + Analytics Dashboard + Index Refresh | Tab or sidebar section visibility controlled by role from session state |

---

## Appendix: Assumptions

- **Authentication mechanism**: A lightweight JWT or API-key scheme is assumed sufficient for internal MVP deployment. No SSO provider is integrated. Token lifetime and refresh policy are TBD.
- **Vector store**: A locally hosted embedding solution (e.g., sentence-transformers with FAISS or ChromaDB) is assumed for MVP to avoid external API dependency and latency. This choice must be confirmed by Platform Engineering.
- **Embedding unit**: The full `body_text` of each step is embedded as a single vector. Steps with very long bodies may need truncation; the truncation limit is TBD.
- **Incremental indexing**: It is assumed that activating a runbook or saving a step triggers an incremental index update automatically, with the Admin manual refresh (FR-12) serving as a backstop for bulk operations.
- **Confidence threshold**: A numeric similarity score threshold below which FR-15 low-confidence disclosure activates is assumed to be configurable via an environment variable; default value to be established during search tuning.
- **One-liner summary**: The optional one-liner on search results (mentioned in the brief) is assumed to be generated by a lightweight mechanism (excerpt extraction or LLM call). The specific implementation and whether a hosted model is acceptable are deferred to Open Question 5.
- **No user PII stored**: The system stores no username, email, or user identifier in any analytics or incident touch table. Role (string) may be logged for operational purposes.
- **Search analytics retention**: `SearchEvent` records are retained for the rolling 30-day analytics window; longer retention is not explicitly scoped.
- **Relational DB**: PostgreSQL is assumed as the production relational store; SQLite may be used for local development only.
- **Step reordering**: When a step is reordered, all affected `step_number` values are recalculated and persisted atomically.
- **NFR targets** (latency, availability, scalability figures) are reasonable assumptions for an internal SRE tooling context; they should be validated with stakeholders before sprint planning.
- **Streamlit session state** is the assumed mechanism for storing the authentication token client-side; no persistent browser storage is used.
- **Demo data seed script** is a first-class deliverable alongside application code, not an afterthought, given the explicit demo data requirements in the brief.
