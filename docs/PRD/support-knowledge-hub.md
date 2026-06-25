# Support Knowledge Hub — PRD

## 1. Overview

Priya, an IT support lead at a 400-person company, faces a fragmented knowledge landscape: canonical answers to common questions (VPN reset, expense policy, onboarding checklists) are scattered across Confluence pages and Slack threads. Keyword-based search surfaces nothing useful for new hires, and contributors routinely duplicate articles under slightly different titles. The result is wasted contributor effort, frustrated employees, and undiscoverable institutional knowledge.

The Support Knowledge Hub centralises internal how-to content in a single, role-gated web application. Employees search by meaning rather than exact keywords and see only vetted, published content. Contributors receive real-time duplicate-awareness warnings when drafting, reducing redundancy before it is baked in. Admins gain full lifecycle control—category management, article pinning, and analytics revealing where documentation is thin or missing.

The MVP will be delivered as a FastAPI backend (`target-apps/support-knowledge-hub/`) with a Streamlit front-end (`ui/streamlit_app.py`). Semantic capabilities (search and similarity) are backed by vector embeddings; all user-facing operations are brokered through the REST API.

---

## 2. Goals & Success Metrics

| Goal | Metric | Target | Notes |
|------|--------|--------|-------|
| Improve search relevance | % of searches where top result is marked "helpful" | ≥ 60 % within 60 days of launch | Baseline: no prior structured data |
| Reduce duplicate articles | New articles flagged by similarity check that are merged/cancelled before publish | ≥ 30 % of flagged drafts do not result in a new article | Signals the warning is acted upon |
| Surface knowledge gaps | Distinct gap-query clusters identified and new articles created per quarter | ≥ 5 new articles per quarter traced to gap analytics | Ownership: Knowledge Admin |
| Increase content discoverability | Employee searches that return ≥ 1 published result | ≥ 85 % of all searches | Measured in backend search log |
| Reduce onboarding friction | New hire "no result" search rate in first 30 days | < 20 % of new-hire searches return zero results | Segment by account age |
| Maintain content freshness | Median time from article edit to updated search index | ≤ 2 minutes | Measured end-to-end via test article mutation |

---

## 3. Non-Goals / Out of Scope

- External public internet access; SSO beyond a dev-login mechanism
- Multi-language support; machine translation of articles
- File attachments (images, PDFs, video hosting)
- Confluence / Slack synchronisation or import pipelines
- Auto-merge or publish blocking based on similarity score (warning is advisory only)
- Ticketing system integration or general chatbot small-talk
- Fine-grained per-article access control lists beyond the four defined roles
- Real-time collaborative editing (multiple contributors editing the same draft simultaneously)
- Email or push notifications (e.g., "your article was archived")
- Public leaderboards for helpful-rating scores
- Leadership access to individual employee identities in any feedback data

---

## 4. Users & Use Cases

| Persona | Need | Primary use case |
|---------|------|------------------|
| **Employee** | Find accurate answers fast without knowing exact article titles | Natural-language search on the home screen; read published articles; submit helpful / not-helpful feedback on results viewed from search |
| **Contributor** | Create, edit, and publish vetted how-to articles; avoid duplicating existing content | Draft editor with a live "similar articles" warning panel; publish flow with required-field validation |
| **Knowledge Admin** | Maintain quality and structure of the entire knowledge base; understand coverage | Manage all articles (publish, archive, restore); manage category list; pin articles per category; view full analytics including gap report |
| **Leadership** | Monitor documentation health and coverage gaps without touching content | Read-only analytics dashboard showing aggregated search trends, feedback rates, and gap signals — no individual employee identities |
| **Public / Unauthenticated** | Verify the service is running (monitoring, load-balancer health checks) | `GET /health` endpoint only — no content access |

---

## 5. Functional Requirements

| ID | Description | Priority | Acceptance criteria (Given / When / Then) |
|----|-------------|----------|-------------------------------------------|
| **FR-1** | **Article CRUD with lifecycle states** — The system shall allow Contributors to create articles with: title (required), rich-text body (required), category (required, from managed list), optional tags, and persist author + created/updated timestamps. Articles exist in exactly one state: `draft`, `published`, or `archived`. | P0 | **Given** a Contributor is authenticated; **When** they submit a new article with title, body, and category; **Then** the article is persisted with state `draft`, the author field is set to the authenticated user, and `created_at` / `updated_at` timestamps are recorded. **Given** a required field (title, body, or category) is missing; **When** submit is attempted; **Then** the API returns HTTP 422 and no article is created. |
| **FR-2** | **Article lifecycle transitions** — Contributors may transition their own articles `draft → published`. Knowledge Admins may transition any article across all states including `published → archived` and `archived → published`. Archiving is effective immediately for search visibility. | P0 | **Given** a Contributor owns a `draft` article with all required fields; **When** they request `publish`; **Then** the article moves to `published` and appears in employee search within the index-refresh SLA (≤ 2 min). **Given** a Contributor attempts to archive another user's article; **When** the request is submitted; **Then** the API returns HTTP 403. **Given** a Knowledge Admin archives a published article; **When** archiving completes; **Then** a subsequent search that previously returned that article no longer includes it. |
| **FR-3** | **Semantic search for employees** — The system shall accept a natural-language query and return up to N (configurable, default 10) published articles ranked by semantic relevance, including: article title, a short excerpt of the most relevant passage (chunk-level match for long articles), category, and a link to the full article. Each article appears at most once per result set. Drafts and archived articles are never returned. | P0 | **Given** an Employee is authenticated; **When** they submit the query "how do I reset my VPN?"; **Then** the response contains only published articles, ranked by semantic relevance, each appearing exactly once, with a passage excerpt. **Given** the same query after an article matching VPN reset is archived; **When** search is executed; **Then** the archived article does not appear in results. **Given** a query against an article with a long body; **When** the result is returned; **Then** the excerpt reflects the most semantically relevant passage, not only the title or introduction. |
| **FR-4** | **Category filter on search** — Employees may optionally supply one category as a filter; when supplied, semantic search is constrained to published articles in that category. | P1 | **Given** an Employee selects category "IT" and submits a query; **When** results are returned; **Then** every article in the result set has category "IT" and no article from another category appears. **Given** no category filter is applied; **When** search executes; **Then** results span all categories. |
| **FR-5** | **Similar-article check for contributors** — When a Contributor saves or requests to publish a draft, the system shall return the top 3–5 published articles most semantically similar to the draft's body. The list is advisory; it does not block publish. Similarity is computed against published articles only. | P0 | **Given** a Contributor saves a draft whose body closely resembles a published "VPN Setup" article; **When** save or publish is triggered; **Then** the response includes the published "VPN Setup" article in the similarity list with a similarity score. **Given** no published articles exist; **When** the check runs; **Then** the response returns an empty similarity list and no error. **Given** the Contributor chooses to publish despite the warning; **When** publish is confirmed; **Then** publish succeeds without additional gates. |
| **FR-6** | **Search index refresh on article edit** — When a published article's body is materially changed and saved, the search index (vectors/embeddings) shall be updated so that subsequent searches and similarity checks reflect the new content within the index-refresh SLA. | P0 | **Given** a published article about "VPN setup" is updated to include "two-factor authentication"; **When** at least 2 minutes have elapsed after the save; **Then** a semantic search for "two-factor VPN" returns the updated article. **Given** an article is archived; **When** archiving completes; **Then** subsequent searches do not return it regardless of embedding state. |
| **FR-7** | **Helpful / Not-Helpful feedback** — An authenticated Employee who navigated to a published article via a search result may submit exactly one feedback signal (helpful or not-helpful) per article per search session. The signal is stored for analytics. No public count is exposed to employees. | P1 | **Given** an Employee opened an article from a search result; **When** they click "Helpful"; **Then** a feedback record is created associating the query, article ID, user ID (hashed/anonymised for Leadership view), and signal. **Given** the same Employee submits feedback on the same search-result article a second time in the same session; **When** the second submission is attempted; **Then** the API returns HTTP 409 and no duplicate is stored. **Given** the article is not in state `published`; **When** feedback submission is attempted; **Then** the API returns HTTP 422. |
| **FR-8** | **Popular gaps analytics** — The system shall maintain an analytics view (accessible to Knowledge Admin and Leadership) listing frequent search queries that returned weak or no useful results, defined as: result set empty OR all returned articles for that query received "not-helpful" feedback. Results are aggregated; no individual employee identity is exposed to Leadership. | P1 | **Given** the query "contractor onboarding" has been searched 10 times and all results were rated "not helpful"; **When** a Knowledge Admin views the gap report; **Then** "contractor onboarding" appears with its frequency count. **Given** a Leadership user views the same report; **Then** no individual employee usernames or IDs appear in the data. |
| **FR-9** | **Pinned articles per category** — A Knowledge Admin may pin up to 5 published articles per category for display on the employee home screen. Attempting to pin a 6th replaces the oldest pin or returns an error (configurable). Pinning an archived article is rejected. Unpinning is available at any time. | P1 | **Given** a Knowledge Admin pins 5 articles in category "IT"; **When** they attempt to pin a 6th "IT" article; **Then** the API returns HTTP 422 with a message indicating the limit is reached. **Given** a Knowledge Admin attempts to pin an archived article; **When** the request is submitted; **Then** the API returns HTTP 422. **Given** a pinned article is subsequently archived; **When** an Employee loads the home screen; **Then** the archived article does not appear in pinned results. |
| **FR-10** | **Category management (Admin only)** — Knowledge Admins may create, rename, and deactivate categories. Deactivated categories are hidden from the contributor category picker and employee filter; existing articles in that category retain their category value but are not discoverable via the category filter. | P1 | **Given** a Knowledge Admin creates a new category "Legal"; **When** a Contributor opens the article editor; **Then** "Legal" appears in the category dropdown. **Given** a non-admin user attempts to create a category via the API; **When** the request is submitted; **Then** the API returns HTTP 403. |
| **FR-11** | **Role-gated Streamlit UI** — The Streamlit application shall present role-appropriate views after authentication: Employee (home with pins, search bar, result excerpts, feedback buttons); Contributor (my drafts list, article editor with similar-articles panel, publish flow); Knowledge Admin (all-articles table, category manager, pin manager, analytics dashboard); Leadership (read-only analytics dashboard). The UI shall call the backend API exclusively over HTTP and never import application modules directly. | P0 | **Given** a user logs in with Employee credentials; **When** the home page loads; **Then** only the pinned articles and search interface are visible — no draft management or admin controls appear. **Given** a user logs in with Knowledge Admin credentials; **When** the dashboard loads; **Then** the all-articles table, category manager, pin manager, and analytics views are accessible. **Given** an unauthenticated session; **When** any protected UI route is accessed; **Then** the user is redirected to the login screen. |
| **FR-12** | **Public health-check endpoint** — The API shall expose `GET /health` returning HTTP 200 and a JSON status payload. No authentication required. | P0 | **Given** no authentication header is provided; **When** `GET /health` is called; **Then** HTTP 200 is returned with `{"status": "ok"}` (or equivalent). |

---

## 6. Non-Functional Requirements

| ID | Category | Target | Measurement / verification | Notes |
|----|----------|--------|---------------------------|-------|
| NFR-1 | Performance — Search latency | p95 semantic search response ≤ 1.5 s under typical load | Load test with 20 concurrent users; measure p95 via API timing logs | (Assumption) Acceptable for internal tooling; revisit if embedding model is hosted remotely |
| NFR-2 | Performance — Similarity check latency | p95 similar-article check ≤ 2 s at save/publish time | Automated test measuring response time on draft save with corpus of 200 published articles | (Assumption) |
| NFR-3 | Performance — Index refresh SLA | Updated article content reflected in search within ≤ 2 minutes of save | Integration test: mutate article body, wait 2 min, assert new content appears in search results | Derived from business rule in brief |
| NFR-4 | Availability | API uptime ≥ 99.5 % during business hours | Uptime monitoring via `/health` endpoint polling every 60 s | (Assumption) Internal tool; 24 × 7 SLA TBD |
| NFR-5 | Security / Authentication | All non-health endpoints require a valid auth token (JWT Bearer or API key); tokens scoped to role | Attempt unauthenticated request to any protected endpoint; assert HTTP 401 returned | Auth mechanism (JWT vs API key) to be confirmed — see Open Questions |
| NFR-6 | Security / Authorisation | Role enforcement verified at API layer; UI role-gating is cosmetic only | Automated tests for each protected endpoint called with a token of insufficient role; assert HTTP 403 | Never rely solely on UI hiding |
| NFR-7 | Privacy / Analytics | Leadership analytics views contain no individual employee PII; feedback records store only hashed or anonymised user references | Review SQL/query results for Leadership role; assert no raw user IDs or names returned | Derived from brief business rules |
| NFR-8 | Scalability | Embedding index and API stateless beyond DB; designed to support corpus growth to ≥ 10,000 articles without architectural change | Design review; benchmark re-index time at 10k articles | (Assumption) |
| NFR-9 | Observability | All API requests logged with: timestamp, endpoint, HTTP status, latency ms, role (no user PII in logs) | Inspect log output for a sample of API calls; assert required fields present | (Assumption) Log storage destination TBD |
| NFR-10 | Observability — Alerting | Alerts fire when: p95 search latency exceeds 3 s, error rate > 5 % over 5-min window, or `/health` fails 3 consecutive checks | Alert rule configuration reviewed in observability stack | (Assumption) Alerting destination (PagerDuty, email, Slack) TBD |
| NFR-11 | Operability | Application deployable via a single `docker compose up` command with seed data loaded automatically | Smoke test: fresh clone → `docker compose up` → seed → assert 5 categories and ≥ 15 published articles present via API | (Assumption) |
| NFR-12 | Data retention | Article history (all states including archived) retained indefinitely unless explicitly deleted by admin; feedback records retained ≥ 12 months | DB schema review; confirm soft-delete pattern for articles; confirm feedback table retention policy | (Assumption) Regulatory requirements TBD — see Open Questions |

---

## 7. Data & Integrations

### Core Entities

| Entity | Key Attributes | Notes |
|--------|---------------|-------|
| `User` | id, email, display_name, role (`employee` \| `contributor` \| `knowledge_admin` \| `leadership`), created_at | Passwords hashed; role stored server-side |
| `Category` | id, name, is_active, created_at, created_by | Soft-deactivation; articles retain category FK |
| `Article` | id, title, body_rich_text, category_id, tags[ ], author_id, state (`draft` \| `published` \| `archived`), created_at, updated_at, published_at, archived_at | Body stored as rich text (HTML or Markdown — TBD) |
| `ArticleChunk` | id, article_id, chunk_index, chunk_text, embedding_vector | For long-article passage-level retrieval; re-generated on material body edit |
| `SearchLog` | id, user_id_hash, query_text, category_filter, result_count, executed_at | user_id stored as one-way hash for gap analytics |
| `SearchResultItem` | id, search_log_id, article_id, rank_position | Links a logged search to returned articles |
| `Feedback` | id, search_log_id, article_id, user_id_hash, signal (`helpful` \| `not_helpful`), created_at | One record per user per article per search session |
| `PinnedArticle` | id, category_id, article_id, pinned_by, pinned_at, display_order | Max 5 active pins per category enforced at API layer |
| `GapQueryAggregate` | id, query_text_normalised, search_count, weak_result_count, last_seen_at | Materialised/computed from SearchLog + Feedback; refreshed periodically |

### Integrations

| System | Direction | Purpose | Notes |
|--------|-----------|---------|-------|
| **Vector / Embedding model** | Internal call (API or local) | Generate embeddings for article chunks and search queries | Specific model TBD (see Open Questions); must support batch re-indexing |
| **Relational database** | Read / Write | Persist all entities above | PostgreSQL assumed (Assumption); pgvector extension candidate for embedding storage |
| **`GET /health`** | Outbound from load balancer / monitoring | Liveness check | No external dependency on response |

All integrations are internal to the deployment; no Confluence, Slack, or external SaaS connectors in scope.

---

## 8. Analytics & Observability

### Logged Events

| Event | Trigger | Stored fields |
|-------|---------|---------------|
| `search.executed` | Employee submits search query | hashed user ID, query text, category filter, result count, article IDs returned, ranks, timestamp |
| `article.viewed` | User opens full article | hashed user ID, article ID, source (search result / direct / pinned), timestamp |
| `feedback.submitted` | Employee clicks helpful / not-helpful | hashed user ID, article ID, search_log_id, signal, timestamp |
| `article.state_changed` | Article moves between lifecycle states | article ID, old state, new state, actor user ID, timestamp |
| `similar_article.shown` | Similarity check results returned to contributor | draft article ID, similar article IDs, similarity scores, timestamp |

### Analytics Views (exposed in UI)

| View | Accessible by | Content |
|------|--------------|---------|
| **Gap report** | Knowledge Admin, Leadership | Normalised queries with weak/no useful results, frequency, trend |
| **Search volume by category** | Knowledge Admin, Leadership | Query count per category per time period |
| **Helpful rate by article** | Knowledge Admin | % helpful feedback per published article |
| **Content coverage map** | Knowledge Admin | Published article count per category; % with ≥ 1 search hit in last 30 days |
| **Article lifecycle audit** | Knowledge Admin | State-change log for all articles |

### Alerting (Assumptions)

- Search p95 latency > 3 s over a 5-minute window → alert.
- API error rate > 5 % over a 5-minute window → alert.
- Three consecutive `/health` failures → alert.
- Vector index staleness > 10 minutes after a published-article edit → alert.

---

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Embedding model produces low-quality semantic matches for internal jargon (e.g. company-specific acronyms) | Employees get poor search results; hub is distrusted | Seed demo corpus with realistic internal vocabulary; plan for domain-adapted or fine-tuned embeddings post-MVP; monitor helpful-rate metric |
| Vector index grows stale after article edits (re-indexing lag > SLA) | Search returns outdated or misleading excerpts | Implement async re-index job triggered on article save; monitor index-staleness alert; expose "last indexed at" timestamp in admin view |
| Contributors ignore similarity warnings and publish duplicates anyway | Knowledge base redundancy persists | Track "warning shown but published anyway" events; Knowledge Admin can archive duplicates retroactively; consider adding a prompt asking contributor to confirm intent |
| Feedback data is insufficient to power gap analytics early on (cold-start problem) | Gap report is empty or noisy for weeks after launch | Pre-seed search logs with plausible demo queries (as called out in brief); set expectation that gap report gains signal over 4–6 weeks |
| Role bypass via direct API calls (UI role-gating is cosmetic only) | Unauthorised content edits or data exposure | All authorisation enforced at API layer with automated role-permission tests (NFR-6); pen-test before full rollout |
| Pinned article becomes stale or is archived after pinning | Employees see no content or an error on home screen | On archive, auto-unpin from all categories; prevent pinning archived articles (FR-9) |
| Database / embedding store grows large with long article bodies and chunk vectors | Performance degradation; storage costs | Chunk-size tuning; enforce reasonable article body length limit (TBD); index on article_id + chunk_index; plan vector DB upgrade path |
| Demo data similarity overlap insufficient to trigger warnings | Similarity check feature cannot be demoed | Explicitly author two VPN-setup articles with different wording but same meaning in seed data; validate similarity score ≥ threshold before demo |

---

## 10. Open Questions

| # | Question | Suggested owner |
|---|----------|-----------------|
| 1 | Which embedding model will be used (e.g., OpenAI `text-embedding-*`, sentence-transformers local model, other)? What are the latency and cost implications for real-time search and similarity checks? | Engineering lead |
| 2 | Should article body be stored as Markdown or HTML rich text? Does the Streamlit editor need a rich-text WYSIWYG component, or is Markdown with preview acceptable for MVP? | Product + Engineering |
| 3 | What authentication mechanism is used for the dev/MVP environment — JWT Bearer tokens with a simple login endpoint, or static API keys per role? Is there a plan to layer SSO on top post-MVP? | Security / Engineering lead |
| 4 | What is the maximum acceptable article body length? Should the system enforce a hard cap (e.g., 50,000 characters) to protect chunking and indexing performance? | Product + Engineering |
| 5 | What chunking strategy should be used for long articles (fixed token window, sentence boundary, heading-based section split)? What is the target chunk size (tokens)? | Engineering lead |
| 6 | Who owns onboarding of real users and migrating existing Confluence/Slack content in Phase 2? Is there any expectation of a one-time import tool? | Priya (Knowledge Admin) + Product |
| 7 | What is the "weak result" threshold for gap analytics — e.g., result set empty, OR top result has < X % helpful rate, OR all results rated not-helpful? | Product + Data |
| 8 | What is the data retention obligation for feedback and search logs under the company's privacy or legal policy (GDPR, CCPA, or internal policy)? | Legal / Compliance |
| 9 | Should the pinning-limit-exceeded behaviour default to hard-reject (HTTP 422) or auto-evict the oldest pin? This affects the admin UX significantly. | Product |
| 10 | Is pgvector sufficient for the target corpus size (up to 10,000 articles × N chunks), or should a dedicated vector database (e.g., Qdrant, Weaviate) be evaluated before implementation begins? | Engineering lead |
| 11 | What is the refresh cadence for the `GapQueryAggregate` materialised view — real-time, hourly, daily? | Engineering lead |
| 12 | Are there any accessibility (WCAG) compliance requirements for the Streamlit UI given this is an internal HR/IT tool? | HR / Legal |

---

## 11. Delivery & Client Surface

| Concern | Choice | Implementation notes |
|---------|--------|---------------------|
| **Client UI** | **Streamlit** | Role-gated multi-page app. Four distinct view sets: Employee, Contributor, Knowledge Admin, Leadership. Login screen collects credentials, stores JWT/token in `st.session_state`. |
| **API** | FastAPI under `target-apps/support-knowledge-hub/` | Full REST + OpenAPI (Swagger UI at `/docs`). All business logic and authorisation enforced here. |
| **UI location** | `ui/streamlit_app.py` (multi-page via `pages/` subdirectory) | HTTP client (e.g., `httpx` or `requests`) to API only — **never** import `app/` modules from Streamlit. |
| **Auth for UI** | JWT Bearer token (or API key per Open Question #3) | Streamlit stores token in `st.session_state["token"]`; passed as `Authorization: Bearer <token>` header on every API call. Session cleared on logout or token expiry. |
| **Semantic / vector layer** | Embedding model + pgvector (or equivalent) | Wrapped behind an internal service or utility module called only by the API. Streamlit never calls embedding functions directly. |
| **Seed / demo data** | `scripts/seed.py` (or equivalent) | Loads ≥ 5 categories, 15–20 published articles (mix of short/long), several drafts, 2–3 archived, 2 contributors, 1 admin, 1 leadership, several employees, pre-seeded search logs with feedback. Triggered automatically on `docker compose up` in dev. |
| **Health check** | `GET /health` — no auth required | Returns `{"status": "ok", "version": "<build>"}`. Used by container orchestration and uptime monitoring. |

---

## Appendix: Assumptions

- **Database**: PostgreSQL with the `pgvector` extension is assumed as the primary datastore for both relational data and vector embeddings. A dedicated vector database may be substituted if performance benchmarks warrant it (see Open Question #10).
- **Embedding model**: A sentence-transformer-style model (local or API-hosted) is assumed. The specific model is not yet decided; latency targets in NFR-1 and NFR-2 assume sub-second embedding inference for a single query.
- **Article body format**: Markdown is assumed for MVP rich text; a Streamlit markdown editor with preview is considered sufficient for contributor workflow.
- **Authentication**: JWT Bearer tokens with a `/auth/login` endpoint returning a signed token are assumed for MVP. Roles are embedded in the token payload.
- **Chunk size**: Heading-based or fixed 512-token chunks are assumed for long-article passage retrieval; exact strategy to be confirmed (Open Question #5).
- **Gap analytics threshold**: A query is classified as "weak result" if (a) zero published articles were returned, or (b) all feedback received for results of that query is "not-helpful". Configurable threshold TBD (Open Question #7).
- **Pinning limit exceeded**: Default behaviour is hard-reject (HTTP 422) rather than auto-evict. Final decision pending (Open Question #9).
- **Index refresh**: An async background job (e.g., Celery task or FastAPI background task) re-computes and upserts chunk embeddings within 2 minutes of a published-article body save.
- **`GapQueryAggregate` refresh**: Assumed to be an hourly batch job materialising from `SearchLog` + `Feedback` tables.
- **Availability**: 99.5 % uptime target is assumed for business-hours internal use; 24×7 SLA not required for MVP.
- **Article body length cap**: No hard cap defined in the brief; 50,000 characters assumed as a reasonable default limit to protect indexing performance.
- **Demo data similarity**: At least two VPN-related articles with semantically equivalent but lexically distinct bodies will be authored explicitly in seed data to guarantee the similar-article warning triggers during demos.
- **Leadership user**: Leadership role has no ability to publish, edit, archive, or pin; they access only read-only aggregated analytics endpoints.
- **Accessibility**: No explicit WCAG compliance requirement assumed for MVP; basic keyboard navigation and sufficient colour contrast recommended as best effort (Open Question #12).
- **Deployment**: Docker Compose is assumed for local development and demo environments. Production deployment target not specified in the brief.
