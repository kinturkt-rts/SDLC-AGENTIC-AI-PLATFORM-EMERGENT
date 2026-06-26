# Bug Deduplicator — PRD

## 1. Overview

Engineering teams are experiencing significant noise and rework caused by duplicate bug reports filed across teams. Without a way to detect semantic similarity at submission time, reporters unknowingly create redundant tickets, splitting discussion, effort, and fix history across multiple records.

This tool addresses the problem by intercepting the bug-filing flow: when a reporter submits a new bug, the system embeds the bug description using AWS Bedrock Titan embeddings, compares it against embeddings of all existing open bugs stored in Postgres with pgvector, and returns the top-K most semantically similar bugs with cosine similarity scores. If the highest score exceeds a configurable threshold (default 0.85), the submission is flagged as a "likely duplicate" and the reporter is prompted to decide whether to proceed with a new ticket or link to an existing one.

The MVP is API-only (Swagger as the demo surface), authenticated via shared API key. An elevated admin API key is required for resolving and merging duplicates. The system is built with FastAPI, Postgres + pgvector, and AWS Bedrock Titan embeddings, with pytest as the testing framework.

---

## 2. Goals & Success Metrics

| Goal | Metric | Target | Notes |
|------|--------|--------|-------|
| Reduce duplicate bug creation | % of filed bugs later marked as duplicates | ≤ 10% (down from baseline) | Baseline to be measured before rollout |
| Surface true duplicates at submission time | Recall of duplicate detection for known duplicate pairs | ≥ 80% | Measured against a labelled test set |
| Maintain fast submission feedback | P95 latency for similarity search on submit | ≤ 1 500 ms end-to-end | Includes embed + vector search |
| High system reliability | API availability | ≥ 99.5% uptime | Measured monthly |
| Configurable dedup sensitivity | Threshold and top-K changeable without code deploy | 100% via env vars | Verified by ops team |

---

## 3. Non-Goals / Out of Scope

- Any browser-based or Streamlit UI (Swagger is the sole demo surface for MVP)
- Cross-project or cross-table bug search (single `bugs` table for MVP)
- Automatic / ML-driven duplicate merging without human confirmation
- Slack, email, or webhook notifications of any kind
- JWT authentication (shared API key only for MVP)
- Embedding the bug title (too short and noisy; description only)
- Searching closed or resolved bugs in deduplication results
- Role-based access control beyond two key tiers (standard vs. admin)
- Bulk import or migration of historical bugs from external trackers

---

## 4. Users & Use Cases

| Persona | Need | Primary use case |
|---------|------|------------------|
| **Bug Reporter** (internal engineer) | Avoid accidentally filing a duplicate ticket | Submit a new bug via `POST /bugs`; review the top-3 similar open bugs returned; decide to proceed or link to existing |
| **Bug Reporter** (internal engineer) | Update a bug description without creating stale embeddings | `PATCH /bugs/{id}` with a new description; system re-embeds automatically |
| **Admin / Bug Triage Lead** | Formally mark a bug as a duplicate and link it to the canonical record | Call `POST /bugs/{id}/duplicate` with admin API key; system links records and sets status to `duplicate` |
| **Admin / Bug Triage Lead** | Prevent closed bugs from polluting dedup results | Resolve/close a bug via admin endpoint; system excludes it from future similarity searches |
| **Developer / QA** | Verify system behaviour via automated tests | Run pytest suite covering near-duplicate detection, unrelated bug scoring, closed-bug exclusion, and re-embed-on-PATCH |

---

## 5. Functional Requirements

| ID | Description | Priority | Acceptance criteria (Given / When / Then) |
|----|-------------|----------|-------------------------------------------|
| FR-1 | **Submit bug with dedup check** — `POST /bugs` accepts `title` (string) and `description` (string), embeds the description via Bedrock Titan, searches open bugs by cosine similarity, and returns the new bug record plus the top-K most similar open bugs with their similarity scores. | P0 | **Given** a valid API key and a bug payload; **When** `POST /bugs` is called; **Then** HTTP 201 is returned with the created bug object and a `similar_bugs` array containing up to K entries (each with `id`, `title`, `similarity_score`), all sourced from open/non-resolved bugs only. |
| FR-2 | **Likely-duplicate flag** — If the highest similarity score in the top-K results meets or exceeds the configurable threshold (default 0.85), the response includes `"likely_duplicate": true` and the ID of the highest-scoring match; otherwise `"likely_duplicate": false`. | P0 | **Given** an existing open bug whose description is semantically near-identical to the submitted description; **When** `POST /bugs` is called; **Then** the response contains `"likely_duplicate": true` and the matching bug's ID appears as `top_match_id`. Conversely, an unrelated submission returns `"likely_duplicate": false`. |
| FR-3 | **Exclude closed/resolved bugs from dedup search** — Bugs with status `closed` or `resolved` are never included in the pgvector similarity search. | P0 | **Given** a bug that has been closed or resolved exists in the database; **When** any `POST /bugs` or `PATCH /bugs/{id}` dedup search is performed; **Then** the closed/resolved bug does not appear in the `similar_bugs` array under any circumstances. |
| FR-4 | **Re-embed on description PATCH** — `PATCH /bugs/{id}` allows updating `title` and/or `description`. If `description` changes, the system re-generates the Bedrock Titan embedding and persists the new vector. The bug being patched is excluded from its own similarity search during the PATCH flow. | P0 | **Given** an existing bug with an embedding; **When** `PATCH /bugs/{id}` is called with a changed `description`; **Then** the stored embedding is updated, the response includes a refreshed `similar_bugs` array that does not contain the bug itself, and a subsequent similarity search reflects the new embedding. If only `title` changes, the embedding is unchanged. |
| FR-5 | **Mark as duplicate** — `POST /bugs/{id}/duplicate` (admin key required) accepts a `canonical_bug_id`, sets the target bug's status to `duplicate`, stores a `duplicate_of` foreign-key link to the canonical bug, and returns the updated bug object. | P0 | **Given** an admin API key and two existing bugs; **When** `POST /bugs/{id}/duplicate` is called with a valid `canonical_bug_id`; **Then** HTTP 200 is returned, the target bug's `status` is `duplicate`, `duplicate_of` equals `canonical_bug_id`, and a subsequent dedup search no longer returns the newly duplicated bug in results (treat as non-open). |
| FR-6 | **Configurable threshold and top-K** — `SIMILARITY_THRESHOLD` and `TOP_K` are read from environment variables at startup with documented defaults (0.85 and 3 respectively). No code change or redeploy is needed to adjust them. | P1 | **Given** `TOP_K=5` and `SIMILARITY_THRESHOLD=0.70` are set as env vars; **When** the service starts and `POST /bugs` is called; **Then** up to 5 similar bugs are returned and the `likely_duplicate` flag uses the 0.70 threshold. |
| FR-7 | **API key authentication** — All endpoints require a valid `X-API-Key` header. Admin-only endpoints additionally require an admin-tier key. Requests with missing or invalid keys are rejected. | P0 | **Given** a request with no `X-API-Key` header or an invalid key; **When** any endpoint is called; **Then** HTTP 401 is returned. **Given** a standard key; **When** `POST /bugs/{id}/duplicate` is called; **Then** HTTP 403 is returned. |
| FR-8 | **Self-exclusion in dedup search** — When computing similar bugs for an existing bug (e.g. during PATCH), the bug's own ID is explicitly filtered from vector search results. | P0 | **Given** bug A exists and its description is updated via PATCH; **When** the dedup search runs; **Then** bug A does not appear in its own `similar_bugs` results regardless of its own similarity score. |
| FR-9 | **Retrieve bug by ID** — `GET /bugs/{id}` returns the full bug record including `status`, `duplicate_of`, `title`, `description`, and metadata. Embedding vector is not exposed in the API response. | P1 | **Given** a valid bug ID; **When** `GET /bugs/{id}` is called with a valid API key; **Then** HTTP 200 is returned with the bug object (no vector field). An unknown ID returns HTTP 404. |
| FR-10 | **Resolve / close bug** — `POST /bugs/{id}/resolve` (admin key required) sets `status` to `resolved` and excludes the bug from future dedup searches. | P1 | **Given** an admin API key and an open bug; **When** `POST /bugs/{id}/resolve` is called; **Then** HTTP 200 is returned, `status` is `resolved`, and the bug does not appear in any subsequent dedup `similar_bugs` arrays. |

---

## 6. Non-Functional Requirements

| ID | Category | Target | Measurement / verification | Notes |
|----|----------|--------|---------------------------|-------|
| NFR-1 | Performance | P95 end-to-end latency for `POST /bugs` ≤ 1 500 ms | Load test with realistic corpus; measure from request receipt to response sent | Includes Bedrock embed call + pgvector ANN search; Bedrock latency is a dependency risk |
| NFR-2 | Performance | P95 latency for `PATCH /bugs/{id}` with description change ≤ 1 500 ms | Same load test harness | Re-embed path must not regress beyond submit latency |
| NFR-3 | Availability | API uptime ≥ 99.5% per calendar month | Uptime monitoring (e.g. health-check endpoint polled at 1-min intervals) | (Assumption) |
| NFR-4 | Security / Auth | All non-health endpoints return HTTP 401 for missing/invalid key; admin endpoints return HTTP 403 for standard keys | Automated pytest security assertions; penetration test pre-launch | API keys stored as bcrypt hashes or equivalent — never in plaintext in DB |
| NFR-5 | Security / Data | Embedding vectors stored in Postgres; no bug content or vectors transmitted to third parties beyond AWS Bedrock for embedding generation | Architecture review; data-flow diagram signed off by security | AWS Bedrock data-processing terms must be reviewed (Open Question) |
| NFR-6 | Scalability | pgvector HNSW or IVFFlat index on the embedding column; query performance must not degrade >20% as bug table grows from 1 K to 100 K rows | Benchmark at 1 K, 10 K, 100 K rows | (Assumption) Index type and parameters to be tuned during implementation |
| NFR-7 | Observability | Structured JSON logs for every request (method, path, status, latency_ms, bug_id where applicable); similarity scores logged at DEBUG level | Log aggregation pipeline; sampled log review | (Assumption) |
| NFR-8 | Observability | `/health` endpoint returns `200 OK` with DB and Bedrock connectivity status | Automated health-check poll; alert on consecutive failures | (Assumption) |
| NFR-9 | Operability | `SIMILARITY_THRESHOLD` and `TOP_K` read from env at startup; service fails fast with clear error if required env vars (DB URL, Bedrock region, API keys) are missing | Integration test with missing env var; review startup logs | |
| NFR-10 | Compliance / Data Retention | Bug records and embeddings retained indefinitely unless explicitly deleted (no automated purge for MVP); deletion must also remove the associated vector | Manual verification; no scheduled-job code shipped | (Assumption) — retention policy to be confirmed with legal/compliance team |
| NFR-11 | Testability | pytest suite achieves ≥ 80% line coverage on core dedup logic (embed, search, threshold evaluation) | CI coverage report gate | Covers FR-1 through FR-5 acceptance scenarios explicitly |

---

## 7. Data & Integrations

### Core Data Entity: `bugs`

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | Auto-generated |
| `title` | TEXT NOT NULL | Display only; not embedded |
| `description` | TEXT NOT NULL | Source text for embedding |
| `embedding` | VECTOR(N) | Bedrock Titan output dimension (TBD — see Open Questions); indexed via HNSW or IVFFlat |
| `status` | ENUM(`open`, `resolved`, `closed`, `duplicate`) | Default `open` |
| `duplicate_of` | UUID FK → `bugs.id` | Nullable; set when status = `duplicate` |
| `created_at` | TIMESTAMPTZ | Auto |
| `updated_at` | TIMESTAMPTZ | Auto-updated on PATCH |

### API Keys Store

A separate table (or env-based map for MVP) holding hashed API keys and their tier (`standard` | `admin`). Details TBD (see Open Questions).

### External Integrations

| System | Purpose | Notes |
|--------|---------|-------|
| **AWS Bedrock — Titan Embeddings** | Generate description embeddings on create and PATCH | Synchronous HTTP call; latency is the primary SLA risk; region and model ID via env vars |
| **Postgres + pgvector** | Persistent storage of bugs and embedding vectors; ANN similarity search | pgvector extension must be enabled; index type to be decided during implementation |

---

## 8. Analytics & Observability

**Structured logging (JSON)**
- Every API request: `timestamp`, `method`, `path`, `status_code`, `latency_ms`, `bug_id` (where applicable), `api_key_tier` (standard/admin, never the key value).
- On dedup search: `top_k_scores` array (DEBUG level), `likely_duplicate` flag, `threshold_used`, `top_k_used`.
- On Bedrock call: `embed_latency_ms`, `model_id`, `success/failure`.

**Metrics (recommended — implementation TBD)**
- Request rate and error rate per endpoint.
- `dedup_likely_duplicate_rate` — fraction of submissions flagged likely duplicate over time.
- `embed_latency_p95` — track Bedrock dependency health.
- `search_latency_p95` — pgvector query performance.

**Alerts (Assumption)**
- `/health` returning non-200 for ≥ 2 consecutive checks → page on-call.
- Error rate on `POST /bugs` > 5% over 5 minutes → alert engineering.

**Pytest observability**
- Tests assert that `similar_bugs` arrays contain required fields (`id`, `title`, `similarity_score`) and that `similarity_score` values are floats in [0, 1].

---

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Bedrock Titan API latency spikes cause P95 to exceed 1 500 ms SLA | High — degrades reporter experience and blocks bug filing | Set aggressive HTTP timeout on Bedrock calls; consider async embed with immediate 202 + polling for high-latency scenarios (Phase 2); monitor `embed_latency_p95` |
| Bedrock Titan service outage makes submission impossible | High — reporters cannot file bugs | Implement graceful degradation: if Bedrock is unavailable, allow bug submission without dedup (store without embedding, flag for back-fill); alert ops |
| pgvector index scan degrades at large table size | Medium — search latency exceeds SLA | Benchmark at 10 K and 100 K rows; tune HNSW `m` and `ef_construction`; add DB read replica if needed |
| API key leaked (shared key model has no per-user revocation) | High — unauthorised write/admin access | Key rotation procedure documented; keys hashed in DB; short-lived keys (expiry) considered for Phase 2 |
| Embedding dimension mismatch if Bedrock model version changes | Medium — breaks vector index and all similarity searches | Pin Bedrock model ID via env var; add startup assertion that embedding dimension matches pgvector column definition |
| False-negative dedup (threshold too high) means duplicates still get filed | Medium — defeats purpose of the tool | Make threshold env-configurable; monitor `dedup_likely_duplicate_rate`; allow post-MVP threshold tuning without redeploy |
| Description updates via PATCH desynchronise embedding (e.g. partial failure) | Medium — stale vectors corrupt search quality | Wrap description update + re-embed + vector persist in a single DB transaction where possible; log and alert on embed failure during PATCH |

---

## 10. Open Questions

| # | Question | Suggested owner |
|---|----------|-----------------|
| 1 | What is the output embedding dimension for the specific Bedrock Titan Embeddings model to be used (e.g. `amazon.titan-embed-text-v1` = 1 536 dims)? Affects pgvector column definition. | Engineering lead |
| 2 | How should API keys be stored and managed for MVP — env-var map, DB table, or AWS Secrets Manager? What is the key rotation process? | Engineering lead / Security |
| 3 | What is the current baseline duplicate-bug rate (to set a meaningful reduction target)? | Engineering / Triage lead |
| 4 | Should the filer be able to proceed with filing even when `likely_duplicate: true` (i.e. is the flag advisory only), or should a second explicit confirmation field be required in the request? | Product owner |
| 5 | Are AWS Bedrock data-processing and data-residency terms acceptable to the security/legal team? Is bug description content considered sensitive IP? | Legal / Security |
| 6 | Should `PATCH /bugs/{id}` return the updated similar-bugs array (re-search after re-embed), or just confirm the update? | Product owner |
| 7 | What is the expected steady-state bug corpus size at launch, and the anticipated growth rate? (Informs pgvector index tuning and scalability planning.) | Engineering / Triage lead |
| 8 | Is there a requirement to expose a `GET /bugs` list/search endpoint for MVP, or is retrieval by ID (`GET /bugs/{id}`) sufficient? | Product owner |
| 9 | Should bugs in `duplicate` status also be excluded from dedup searches (in addition to `closed`/`resolved`)? | Product owner |
| 10 | Is a back-fill job needed to embed bugs that existed before the service is deployed? | Engineering lead |

---

## 11. Delivery & Client Surface

| Concern | Choice | Implementation notes |
|---------|--------|---------------------|
| Client UI | API-only (Swagger / OpenAPI) | No UI for MVP per brief; Swagger UI served by FastAPI at `/docs` is the demo surface |
| API framework | FastAPI under `target-apps/bug-deduplicator/` | REST + OpenAPI; auto-generated Swagger at `/docs` and `/redoc` |
| Auth for API | Shared API key via `X-API-Key` header | Two tiers: `standard` (CRUD + dedup) and `admin` (resolve, mark duplicate); no JWT for MVP |
| Embedding service | AWS Bedrock Titan Embeddings | Model ID and AWS region via env vars; synchronous call on `POST /bugs` and on description-changing `PATCH` |
| Vector store | Postgres + pgvector extension | ANN index (HNSW recommended) on `bugs.embedding`; cosine distance operator |
| Configuration | Environment variables | `SIMILARITY_THRESHOLD`, `TOP_K`, `BEDROCK_MODEL_ID`, `BEDROCK_REGION`, `DATABASE_URL`, `API_KEY_STANDARD`, `API_KEY_ADMIN` (names illustrative) |
| Testing | pytest | Covers: near-duplicate detection, unrelated-bug low scores, closed-bug exclusion, re-embed on PATCH, self-exclusion on PATCH, auth enforcement |
| Phase 2 candidates | React or Streamlit UI, per-user JWT auth, cross-project search, Slack notifications, async embed pipeline | Out of scope for MVP |

---

## Appendix: Assumptions

- **Bedrock Titan model**: `amazon.titan-embed-text-v1` (or v2) is the intended model; exact model ID and embedding dimension to be confirmed (Open Question 1).
- **Similarity metric**: Cosine similarity (via pgvector `<=>` operator) is used; "score" in API responses is normalised to [0, 1] where 1 = identical.
- **Default configuration**: `SIMILARITY_THRESHOLD=0.85`, `TOP_K=3` unless overridden by env vars.
- **Bug status model**: Four statuses — `open`, `resolved`, `closed`, `duplicate`. Only `open` bugs participate in dedup search. (Whether `duplicate`-status bugs are also excluded is an open question.)
- **API key storage**: Keys are hashed (bcrypt or similar) before DB storage; plaintext keys are only available at generation time.
- **Single-tenant, single-table MVP**: All bugs share one table with no project or team partitioning.
- **No soft-delete for MVP**: Bugs are not deleted via the API; status changes are the lifecycle mechanism.
- **PATCH is a partial update**: Only provided fields are changed; unprovided fields are unchanged.
- **Bedrock call is synchronous**: The `POST /bugs` response waits for the Bedrock embed call to complete before persisting and searching.
- **No pagination on `similar_bugs`**: The dedup results array is bounded by `TOP_K` (max ~10); no cursor needed.
- **Health endpoint**: `GET /health` is unauthenticated and checks DB and Bedrock reachability.
- **Embedding not exposed**: The raw embedding vector is never returned in API responses.
- **AWS credentials**: Assumed to be available to the service via IAM role or environment (AWS standard credential chain); not stored in application config.
- **Test database**: pytest uses a separate test Postgres instance (or schema) with pgvector enabled; Bedrock calls are mocked in unit tests, used for integration tests only.
- **Availability target of 99.5%** is an assumption; actual SLA to be agreed with stakeholders.
- **Data retention** is indefinite for MVP; no automated purge scheduled.
