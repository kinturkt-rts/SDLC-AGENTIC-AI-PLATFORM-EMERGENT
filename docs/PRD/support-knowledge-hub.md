# Support Knowledge Hub — PRD

## 1. Overview

Priya manages internal IT support for a ~400-person organisation whose institutional knowledge is fragmented across Confluence pages and Slack threads. Employees searching for answers (e.g., "how do I reset VPN?", "expense policy for client meals") receive poor results because searches are keyword-only and content is scattered. Worse, contributors repeatedly write near-duplicate articles without realising similar content already exists, eroding trust in the hub over time.

The Support Knowledge Hub centralises vetted how-to articles in a single internal platform with semantic (meaning-based) search, a structured article lifecycle (draft → published → archived), and an AI-assisted duplicate-awareness check that warns contributors when their draft resembles existing published content. Employees find answers faster; contributors write with confidence; admins maintain quality and spot documentation gaps through analytics.

The MVP is delivered as a FastAPI backend under `target-apps/support-knowledge-hub/` with a Streamlit front-end that presents role-gated views for four authenticated personas (Employee, Contributor, Knowledge Admin, Leadership). Unauthenticated access is restricted to a `/health` endpoint.

---

## 2. Goals & Success Metrics

| Goal | Metric | Target | Notes |
|------|--------|--------|-------|
| Improve answer-findability | % of semantic searches returning ≥1 published result rated "helpful" | ≥ 60% of rated searches at launch | Measured from feedback table |
| Reduce duplicate content | Proportion of published articles with a near-duplicate sibling (cosine similarity > 0.85) | < 10% of total published articles | Evaluated monthly |
| Surface documentation gaps | Distinct "weak-result" query topics appearing in analytics | Reviewed weekly by Knowledge Admin; backlog created within 5 business days | Popular-gaps dashboard drives content roadmap |
| Enable fast browsing | Median time-to-first-useful-result for employees | < 30 seconds from search bar to article open | Tracked via optional client-side timing |
| Content freshness | % of published articles updated within the last 90 days | ≥ 70% of active articles | Visible in admin articles table |
| Adoption | Weekly active employee searchers as % of total employee population | ≥ 25% within 60 days of launch | User activity logs |

---

## 3. Non-Goals / Out of Scope

- External public internet access or public-facing search
- SSO / enterprise identity federation beyond the dev-login mechanism used in the demo
- Multi-language content or UI localisation
- File attachments (PDFs, images) or video hosting within articles
- Automated sync with Confluence, Slack, or any external knowledge source
- Auto-merge of duplicate articles or hard-blocking publish based on similarity (warning is advisory only)
- Ticketing system integration or chatbot small-talk outside the article corpus
- Fine-grained per-article access control beyond the four defined roles
- Public leaderboard or gamification of helpful/not-helpful scores
- Mobile-native application (Streamlit responsive layout is acceptable)

---

## 4. Users & Use Cases

| Persona | Need | Primary use case |
|---------|------|------------------|
| **Employee** | Find accurate answers quickly without knowing exact keywords | Types a natural-language question into the search bar; receives ranked excerpts from published articles; marks results helpful or not helpful |
| **Contributor** | Write and maintain high-quality articles; avoid duplicating existing work | Creates a draft, sees a "similar published articles" panel while editing, publishes once satisfied; edits own published articles |
| **Knowledge Admin** | Govern content quality, organise categories, spotlight key articles, monitor gaps | Publishes or archives any article, manages category list, pins up to 5 articles per category, views full analytics dashboard |
| **Leadership** | Understand documentation coverage and employee search behaviour at an aggregate level | Views read-only analytics dashboard (popular searches, gap reports, helpful-rate trends) without seeing individual employee identities |
| **Public / Unauthenticated** | Confirm service liveness (monitoring, load-balancer checks) | Calls `GET /health`; receives `200 OK` with service status; cannot access any content endpoints |

---

## 5. Functional Requirements

| ID | Description | Priority | Acceptance criteria (Given / When / Then) |
|----|-------------|----------|-------------------------------------------|
| **FR-1** | **Article CRUD with lifecycle** — The system shall allow Contributors to create articles with title (required), rich-text body (required), category (required), optional tags, and expose draft → published → archived state transitions. | P0 | **Given** a Contributor is authenticated; **When** they submit a new article with title, body, and category; **Then** the article is persisted in `draft` state, assigned a unique ID, author, and `created_at` timestamp, and is visible only in the Contributor's "my drafts" view. |
| **FR-2** | **Publish / archive lifecycle enforcement** — The system shall enforce that only `published` articles are visible in employee search and browse; archiving removes an article from search immediately; restoring to published re-enables search. Only Knowledge Admin may archive another user's article or edit another user's published body. | P0 | **Given** an article transitions to `archived`; **When** any Employee performs a semantic search or category browse; **Then** the archived article does not appear in results. **And Given** the article is restored to `published`; **When** the same query is issued; **Then** the article reappears in results within one re-index cycle (≤ 60 seconds). |
| **FR-3** | **Semantic search with excerpt and section highlighting** — The system shall accept a natural-language query from an authenticated Employee (or any higher role) and return the top-N ranked published articles by semantic similarity, each with a short excerpt from the most relevant passage (not only the title), a relevance score indicator, and a link to the full article. The result set shall never contain duplicate article IDs. | P0 | **Given** an Employee submits the query "how do I connect to the VPN from home"; **When** results are returned; **Then** at least one published VPN-related article appears in the top 3 results; the excerpt shown is drawn from the body passage most relevant to the query (not necessarily the title); and no article ID appears more than once in the result set. |
| **FR-4** | **Category filter on search and browse** — The system shall allow employees to filter search results and the article browse view by one or more categories. Knowledge Admin can create, rename, and delete categories (deletion only if no published articles reference the category). | P0 | **Given** published articles exist in categories `IT` and `HR`; **When** an Employee applies the `IT` filter and searches "password reset"; **Then** only articles with category `IT` are returned. **And Given** a Knowledge Admin attempts to delete a category with assigned published articles; **When** the delete request is submitted; **Then** the API returns a `409 Conflict` with a message listing the blocking articles. |
| **FR-5** | **Similar-article warning on save/publish** — When a Contributor saves or attempts to publish a draft, the system shall compute semantic similarity between the draft body and all published articles, and return the top-K (K ≤ 5) similar published articles (title, excerpt, similarity score) if any exceed a configured similarity threshold. The warning is advisory; publish is not blocked. | P0 | **Given** a Contributor drafts an article whose body is semantically close to an existing published VPN guide; **When** they click Save or Publish; **Then** the API response includes a `similar_articles` list with ≥ 1 entry containing article ID, title, excerpt, and similarity score ≥ the threshold. **And When** the body has no meaningful overlap with any published article; **Then** `similar_articles` is an empty list and publish proceeds without a warning panel. |
| **FR-6** | **Search result feedback (helpful / not helpful)** — Authenticated Employees shall be able to submit a single helpful or not-helpful rating per article per search session, only for published articles they opened from a search result. Ratings are stored with article ID, query text (anonymised of PII), and timestamp. Leadership and Admin views show aggregated counts only — never individual employee identity. | P0 | **Given** an Employee opens a published article from a search result; **When** they click "Helpful" or "Not Helpful"; **Then** the rating is persisted and the button state reflects their choice. **And Given** the same Employee tries to rate the same article from the same search session a second time; **Then** the API returns `409 Conflict` (idempotent: updating the existing rating is acceptable). **And** the rating is never attributable to a named individual in the Leadership analytics view. |
| **FR-7** | **Popular-gaps analytics** — The system shall provide a Knowledge Admin / Leadership-accessible view listing search queries (or query clusters) that frequently returned zero results or results rated predominantly "not helpful", ordered by frequency descending. | P1 | **Given** seed analytics data contains 10+ queries with zero published-article matches or ≥ 70% not-helpful ratings; **When** a Knowledge Admin opens the Popular Gaps dashboard; **Then** those queries appear ranked by frequency and each shows result count and helpful-rate. No individual employee identity is exposed. |
| **FR-8** | **Pinned articles per category** — A Knowledge Admin may pin up to 5 published articles per category. Pinned articles appear prominently on the Employee home screen for the relevant category. Attempting to pin a 6th article in a category, or to pin an archived/draft article, shall be rejected. | P1 | **Given** a Knowledge Admin has already pinned 5 articles in category `IT`; **When** they attempt to pin a 6th `IT` article; **Then** the API returns `422 Unprocessable Entity` with message "Maximum 5 pinned articles per category". **And Given** a Knowledge Admin attempts to pin an archived article; **Then** the API returns `422` with message "Only published articles may be pinned". |
| **FR-9** | **Embedding refresh on material article edits** — When a published article's body is updated, the system shall regenerate the article's semantic embedding and update the search index so that subsequent searches and similarity checks reflect the new content within one index cycle. | P1 | **Given** a published article titled "VPN Setup Guide" has its body substantially rewritten; **When** the update is saved and one re-index cycle completes (≤ 60 seconds); **Then** a semantic search query aligned with the new content returns the updated article ranked higher than before the edit, and the old excerpt is no longer surfaced. |
| **FR-10** | **Role-gated Streamlit UI** — The Streamlit application shall enforce role-based views: (a) Employee home shows pinned articles, search bar, result excerpts, and feedback buttons; (b) Contributor view shows "My Drafts" list, rich-text editor with similar-articles side panel, and publish flow; (c) Knowledge Admin view includes all-articles table, category manager, pin manager, and analytics dashboard; (d) Leadership view shows read-only analytics dashboard. Navigation items and actions unavailable to a role must be hidden or disabled — not merely protected server-side. The Streamlit app calls the FastAPI backend exclusively over HTTP and never imports `app/` modules directly. | P0 | **Given** a user is authenticated as Employee; **When** the Streamlit app loads; **Then** the Contributor editor, Admin controls, and analytics actions are not present in the navigation or page content. **And Given** a user is authenticated as Knowledge Admin; **When** they navigate to Category Manager; **Then** create, rename, and delete category controls are rendered and functional. |
| **FR-11** | **Contributor publish validation** — The system shall reject publish attempts where title, body, or category is missing, returning a `422` with field-level errors. | P0 | **Given** a Contributor submits a publish request with an empty category field; **When** the API processes the request; **Then** it returns `422 Unprocessable Entity` with an error referencing the `category` field, and the article remains in `draft` state. |
| **FR-12** | **Demo / seed data** — The system shall ship a seed script that loads: ≥ 5 categories, ≥ 15 published articles (mix of short and long bodies, ≥ 2 near-duplicate pairs for similarity demo), several drafts, 2–3 archived articles, seed search-feedback records including weak-result gaps, and at least 2 Contributors, 1 Knowledge Admin, 1 Leadership user, and several Employees. | P1 | **Given** the seed script is executed against a clean database; **When** a Knowledge Admin logs in and opens the analytics dashboard; **Then** popular-gaps data is visible; the similar-article warning triggers on at least one draft; and pinned articles appear on the Employee home screen. |

---

## 6. Non-Functional Requirements

| ID | Category | Target | Measurement / verification | Notes |
|----|----------|--------|---------------------------|-------|
| **NFR-1** | Performance — Search latency | p95 semantic search response ≤ 1.5 s under nominal load (≤ 50 concurrent users) | Load test with k6 or Locust against `POST /search`; measure p95 over 60-second run | (Assumption) Embedding inference may be pre-computed; real-time re-ranking must still meet target |
| **NFR-2** | Performance — Similarity check | Similar-article check response ≤ 2 s for a draft body up to 5 000 words | Automated test timing `POST /articles/{id}/similar` with max-size payload | (Assumption) |
| **NFR-3** | Security / Auth | All content endpoints (search, articles, feedback, analytics) require a valid JWT Bearer token; unauthenticated requests receive `401 Unauthorized` | Integration test suite: assert every protected route returns `401` without a token | Unauthenticated access permitted only on `GET /health` |
| **NFR-4** | Security / Authorisation | Role claims in JWT are enforced server-side; a Contributor JWT cannot access Admin or Leadership endpoints | Integration tests: Contributor token → `GET /admin/analytics` must return `403 Forbidden` | Role elevation solely via JWT claim; no client-side bypass |
| **NFR-5** | Security / Privacy | Employee identity must not appear in any Leadership-accessible analytics API response; feedback records store only a hashed or omitted user identifier in aggregated outputs | Code review of analytics query layer + API response schema inspection confirming no `user_id` / `email` in Leadership-scoped responses | Complies with brief's anonymisation requirement |
| **NFR-6** | Availability | API uptime ≥ 99.5% during business hours (Mon–Fri 06:00–22:00 local) | Uptime monitor (e.g., UptimeRobot or equivalent) against `/health` endpoint | (Assumption) SLA window; 24/7 target is out of scope for MVP |
| **NFR-7** | Scalability | System handles article corpus up to 10 000 published articles without degradation beyond NFR-1 latency targets | Offline benchmark: load 10 000 embeddings into vector store; re-run search latency test | (Assumption) Growth estimate for a 400-person company over 3 years |
| **NFR-8** | Observability | All API requests logged with method, path, status code, latency, and role (not user identity); structured JSON logs; error events include stack trace | Verify log output format in CI; confirm no PII fields (email, name) appear in log lines | (Assumption) Log aggregation destination (e.g., stdout → collector) TBD |
| **NFR-9** | Operability | Application deployable via a single `docker compose up` command; environment variables documented in `.env.example`; seed script executable with one command | Reviewer runs `docker compose up` + seed script on a clean machine and confirms all health checks pass | (Assumption) Containerisation required; orchestration platform TBD |
| **NFR-10** | Data Retention | Article history (including archived articles) retained indefinitely in the primary store; feedback records retained ≥ 12 months | Schema inspection confirms archived articles are soft-deleted (not hard-deleted); retention policy documented in README | (Assumption) 12-month feedback retention; adjust per legal/compliance review |
| **NFR-11** | Compliance / Data | No personal employee data stored beyond what is required for authentication and role assignment; feedback rows must not store free-text that could identify an individual | Data model review: confirm feedback table schema contains no name/email fields | (Assumption) No specific regulatory regime stated; apply data-minimisation principle |

---

## 7. Data & Integrations

### Core Entities

| Entity | Key Fields | Notes |
|--------|-----------|-------|
| `User` | `id`, `email` (hashed in analytics outputs), `display_name`, `role` (`employee`, `contributor`, `knowledge_admin`, `leadership`), `created_at` | Auth source TBD (see Open Questions) |
| `Category` | `id`, `name`, `slug`, `created_by`, `created_at` | Managed by Knowledge Admin only |
| `Article` | `id`, `title`, `body` (rich text / Markdown), `category_id`, `tags[]`, `author_id`, `status` (`draft`\|`published`\|`archived`), `created_at`, `updated_at`, `published_at`, `archived_at` | Soft-delete via status; body changes trigger re-embed |
| `ArticleEmbedding` | `article_id`, `chunk_index`, `chunk_text`, `embedding_vector`, `model_version`, `embedded_at` | Long articles split into overlapping chunks for passage-level retrieval |
| `PinnedArticle` | `id`, `category_id`, `article_id`, `pinned_by`, `pinned_at` | Max 5 per category enforced at API layer |
| `SearchEvent` | `id`, `query_text`, `query_embedding`, `result_article_ids[]`, `result_count`, `timestamp`, `role` | No `user_id` stored; anonymised at write time |
| `Feedback` | `id`, `search_event_id`, `article_id`, `rating` (`helpful`\|`not_helpful`), `timestamp` | No user identity; idempotent per session+article |
| `AnalyticsGapView` | Derived/materialised from `SearchEvent` + `Feedback` | Surfaces queries with low result count or high not-helpful rate |

### External Integrations (MVP)

| System | Purpose | Notes |
|--------|---------|-------|
| Embedding model (e.g., `sentence-transformers` or OpenAI embeddings) | Generate semantic vectors for article chunks and search queries | Model choice TBD (see Open Questions); must be callable at write time and query time |
| Vector store (e.g., pgvector, Chroma, or Qdrant) | Approximate nearest-neighbour search over article chunk embeddings | Selection TBD; must support filtered search by `status = published` |
| Relational database (PostgreSQL assumed) | Persistent storage for all entities above | (Assumption) |
| `GET /health` | Liveness endpoint for load balancer / monitoring | Returns `{"status": "ok", "version": "..."}` |

---

## 8. Analytics & Observability

### Logging
- Structured JSON logs on stdout; fields: `timestamp`, `level`, `method`, `path`, `status_code`, `duration_ms`, `role`.
- No PII (email, display_name, IP address) in log fields.
- Error logs include `exception_type`, `message`, `stack_trace`.

### Application Metrics
| Metric | Type | Purpose |
|--------|------|---------|
| `search_requests_total` | Counter | Request volume by role |
| `search_latency_ms` | Histogram | p50/p95/p99 tracking |
| `similar_check_latency_ms` | Histogram | Similarity endpoint performance |
| `articles_by_status` | Gauge | Draft / published / archived counts |
| `feedback_ratings_total` | Counter | Helpful vs not-helpful by category |
| `gap_queries_total` | Counter | Queries with 0 results or weak ratings |

### Alerts (Assumption)
- Search p95 latency > 2 s for 5-minute window → warning alert.
- API error rate > 5% over 5 minutes → critical alert.
- Embedding job failure → critical alert (stale search results risk).

### Analytics Surfaces in UI
- **Knowledge Admin / Leadership dashboard**: helpful-rate trend (7-day rolling), top-20 popular-gap queries, article coverage by category (published count, last-updated distribution).
- Leadership view: aggregated only; no user-level breakdown.

---

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Embedding model latency makes similarity check too slow for interactive use | High — degrades Contributor UX, may discourage use | Pre-compute embeddings asynchronously on article save; cache query embeddings; set 2 s SLA with fallback message if exceeded |
| Stale embeddings after article body edit | Medium — incorrect search ranking and similarity results | Trigger async re-embed job on every published body update; expose embedding freshness flag in admin table |
| Vector store choice locked early, hard to swap | Medium — operational cost or scaling limit | Abstract vector store behind a repository interface; document swap-out procedure |
| Contributors ignore similarity warnings and publish duplicates anyway | Medium — content quality degrades | Track warning-acknowledgement rate in analytics; Knowledge Admin notified of new duplicates above threshold |
| Privacy leak: employee identity appears in Leadership analytics | High — trust violation, potential regulatory issue | Enforce anonymisation at the query/serialisation layer; add automated test asserting `user_id`/`email` absent from Leadership API responses |
| Category deletion breaks existing articles | Medium — orphaned articles disappear from browse | Block category deletion if published articles reference it (FR-4); require reassignment first |
| Seed data insufficient for compelling demo | Low-Medium — weak stakeholder buy-in | Seed script acceptance test (FR-12) gates deployment; reviewed by PM before demo |
| JWT secret misconfiguration exposes all content | High — unauthorised data access | Validate JWT configuration in startup health check; fail fast if secret is default/empty |

---

## 10. Open Questions

| # | Question | Suggested owner |
|---|----------|-----------------|
| 1 | Which embedding model will be used (local `sentence-transformers`, OpenAI `text-embedding-*`, or other)? This affects latency, cost, and offline-capability. | Tech Lead |
| 2 | Which vector store will be adopted (pgvector extension on existing Postgres, hosted Qdrant, Chroma in-process)? | Tech Lead |
| 3 | What is the dev-login mechanism for the MVP? (Hard-coded users in DB, simple API-key-per-role, or a lightweight JWT issuer?) | Tech Lead / PM |
| 4 | What is the similarity threshold (cosine score) above which the similar-article warning should fire? Needs calibration against demo data. | Tech Lead + Knowledge Admin (Priya) |
| 5 | What chunk size and overlap should be used when splitting long articles for passage-level retrieval? Affects excerpt quality and embedding storage. | Tech Lead |
| 6 | Is there a requirement to notify Contributors via email/Slack when a Knowledge Admin archives their article? | PM / Priya |
| 7 | Should the "popular gaps" view cluster near-duplicate queries (e.g., "VPN reset" and "reset VPN") or list them individually? | PM / Analytics |
| 8 | What is the maximum article body length in characters/tokens? Needed to set chunk strategy and storage limits. | Tech Lead |
| 9 | Is a Contributor allowed to publish their own article directly, or must a Knowledge Admin approve every publish? (Brief implies Contributors can self-publish; confirm.) | PM / Priya |
| 10 | What log aggregation / monitoring stack will be used in production (Datadog, Grafana/Loki, CloudWatch, etc.)? | DevOps / Tech Lead |
| 11 | Are there any data-residency or compliance requirements (GDPR, SOC 2, etc.) that would affect how feedback and search logs are stored? | Legal / PM |

---

## 11. Delivery & Client Surface

| Concern | Choice | Implementation notes |
|---------|--------|---------------------|
| **Client UI** | **Streamlit** | Role-gated multi-page app; pages: Employee Home, Contributor Editor, Admin Console (Articles + Categories + Pins + Analytics), Leadership Analytics |
| **API** | FastAPI under `target-apps/support-knowledge-hub/` | REST + OpenAPI (`/docs`); all business logic lives here |
| **UI location** | `ui/streamlit_app.py` (with sub-pages in `ui/pages/`) | HTTP client to FastAPI only — never imports `app/` modules directly |
| **Auth for UI** | JWT Bearer token | User logs in via `POST /auth/token`; Streamlit stores token in `st.session_state`; token passed as `Authorization: Bearer <token>` header on every API call |
| **Role enforcement** | Server-side (JWT role claim) + client-side (Streamlit page hiding) | Server-side is authoritative; UI hides unavailable nav items for UX only |
| **Vector store** | TBD (pgvector preferred for single-DB simplicity) | Abstracted behind `ArticleRepository.search()` interface |
| **Embedding service** | TBD; called at article save/publish and at query time | Async worker for article re-embedding; synchronous for query embedding at search time |
| **Seed script** | `scripts/seed_db.py` | Idempotent; invoked via `python scripts/seed_db.py`; documented in `README.md` |
| **Container** | `docker-compose.yml` at repo root | Services: `api`, `ui`, `db` (Postgres), optionally `vector-db` if not pgvector |
| **API slug** | `support-knowledge-hub` | Base path: `target-apps/support-knowledge-hub/` |

---

## Appendix: Assumptions

- **Authentication**: A lightweight internal JWT issuer (username/password against seeded users) is used for the MVP. No SSO or external IdP is integrated.
- **Database**: PostgreSQL is the primary relational store. pgvector extension is the preferred vector store to avoid an additional service dependency, but this is unconfirmed.
- **Embedding model**: A locally-runnable sentence-transformer model (e.g., `all-MiniLM-L6-v2`) is assumed for offline/dev use. A swap to a hosted API (OpenAI embeddings) may be preferable for production quality but incurs cost.
- **Rich text**: Article body is stored and served as Markdown; the Streamlit editor renders Markdown preview. A full WYSIWYG editor is not assumed for MVP.
- **Re-index cycle**: The 60-second SLA for embedding refresh assumes an async background task polling for pending re-embed jobs; a message queue is not assumed for MVP.
- **Similarity threshold**: A default cosine similarity threshold of 0.75 is assumed as a starting point, subject to calibration (Open Question 4).
- **Chunk strategy**: Articles are split into ~300-token overlapping chunks for passage-level retrieval; exact parameters TBD (Open Question 5).
- **Contributors can self-publish**: Based on the brief ("contributors publish vetted articles"), Contributors can transition their own draft to published without a Knowledge Admin approval step, provided title + body + category are present.
- **Session-scoped feedback**: "Same search session" for idempotent feedback is defined as a single `SearchEvent` record ID, not a browser session token.
- **Analytics anonymisation**: User identity is omitted entirely from `SearchEvent` and `Feedback` rows at write time (not pseudonymised post-hoc), to prevent re-identification.
- **Category list is finite and admin-managed**: No free-form category entry by Contributors; they select from the admin-managed list.
- **Deployment environment**: A single-host Docker Compose deployment is assumed for MVP. Kubernetes or cloud-managed services are out of scope.
- **Article length cap**: A soft limit of ~50 000 characters per article body is assumed; longer content should use multiple articles or sections. This is unconfirmed (Open Question 8).
- **No email notifications**: Contributors are not notified by email when their article is archived by a Knowledge Admin (unconfirmed; see Open Question 6).
