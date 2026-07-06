# Support Knowledge Hub — Solution Design

## 1. Summary
Internal knowledge hub enabling employees to search articles semantically, contributors to author with duplicate-awareness, and admins to manage categories, pins, and analytics. Primary DB: PostgreSQL + pgvector. API style: REST (FastAPI). Auth: JWT Bearer with role in payload.
TBD: chunk size strategy (512-token assumed), gap analytics threshold, pinning-limit eviction policy.
Diagram: `docs/generated-diagrams/support-knowledge-hub.png`

## 2. Stack
| Layer | Technology | Notes |
|-------|------------|-------|
| UI | Streamlit | `ui/streamlit_app.py`; calls FastAPI over HTTP port 8501 |
| API | FastAPI | `target-apps/support-knowledge-hub/`; JWT auth, OpenAPI at `/docs` |
| DB | PostgreSQL + pgvector | Relational metadata + 1024-dim embeddings (`vector(1024)`) |
| Embeddings | Bedrock Titan Embed v2 | `amazon.titan-embed-text-v2:0`; query + chunk embed |
| LLM | Bedrock Claude | RAG answer generation from top-k chunks |
| File store | Local FS | `data/evidence/`; Phase-2: S3 |

## 3. Data model
| Table | Columns | Indexes / Constraints |
|-------|---------|-----------------------|
| `users` | `id uuid PK`, `email text UNIQUE`, `display_name text`, `role text`, `hashed_password text`, `created_at timestamptz` | idx on `email`; role ∈ {employee,contributor,knowledge_admin,leadership} |
| `categories` | `id uuid PK`, `name text UNIQUE`, `is_active bool DEFAULT true`, `created_at timestamptz`, `created_by uuid FK users` | idx on `is_active` |
| `articles` | `id uuid PK`, `title text`, `body text`, `category_id uuid FK categories`, `tags text[]`, `author_id uuid FK users`, `state text DEFAULT 'draft'`, `created_at timestamptz`, `updated_at timestamptz`, `published_at timestamptz`, `archived_at timestamptz` | idx on `state`, `category_id`; state ∈ {draft,published,archived} |
| `article_chunks` | `id uuid PK`, `article_id uuid FK articles`, `chunk_index int`, `chunk_text text`, `embedding vector(1024)` | `ivfflat` idx on `embedding`; UNIQUE(`article_id`,`chunk_index`) |
| `search_logs` | `id uuid PK`, `user_id_hash text`, `query_text text`, `category_filter uuid FK categories NULL`, `result_count int`, `executed_at timestamptz` | idx on `executed_at` |
| `search_result_items` | `id uuid PK`, `search_log_id uuid FK search_logs`, `article_id uuid FK articles`, `rank_position int` | idx on `search_log_id` |
| `feedback` | `id uuid PK`, `search_log_id uuid FK search_logs`, `article_id uuid FK articles`, `user_id_hash text`, `signal text`, `created_at timestamptz` | UNIQUE(`search_log_id`,`article_id`,`user_id_hash`); signal ∈ {helpful,not_helpful} |
| `pinned_articles` | `id uuid PK`, `category_id uuid FK categories`, `article_id uuid FK articles`, `pinned_by uuid FK users`, `pinned_at timestamptz`, `display_order int` | UNIQUE(`category_id`,`article_id`); max 5 per category enforced at API |

## 4. API surface
| Method | Path | Request | Response | Notes |
|--------|------|---------|----------|-------|
| POST | `/api/v1/auth/login` | `{email, password}` | `{access_token, role}` | Returns JWT; no auth required |
| GET | `/health` | — | `{status, version}` | Public (FR-12) |
| GET | `/api/v1/articles` | `?state&category_id&skip&limit` | `[ArticleSummary]` | Admin sees all states; others see published only |
| POST | `/api/v1/articles` | `{title, body, category_id, tags}` | `ArticleOut` | Contributor+ (FR-1); triggers similarity check |
| GET | `/api/v1/articles/{id}` | — | `ArticleOut` | Published→any auth; draft→owner/admin |
| PATCH | `/api/v1/articles/{id}` | `{title?,body?,category_id?,tags?,state?}` | `ArticleOut` | State transitions per FR-2; re-embeds on body change |
| POST | `/api/v1/articles/{id}/similar` | `{body}` | `[{article_id,title,score}]` | Top 3–5 published similar (FR-5) |
| POST | `/api/v1/search` | `{query, category_id?, top_k?}` | `[SearchResultItem]` | Employee+ ; logs to search_logs (FR-3,FR-4) |
| POST | `/api/v1/feedback` | `{search_log_id, article_id, signal}` | `FeedbackOut` | Employee+; 409 on duplicate (FR-7) |
| GET | `/api/v1/categories` | — | `[CategoryOut]` | All auth; active only unless admin |
| POST | `/api/v1/categories` | `{name}` | `CategoryOut` | Admin only (FR-10) |
| PATCH | `/api/v1/categories/{id}` | `{name?,is_active?}` | `CategoryOut` | Admin only (FR-10) |
| GET | `/api/v1/pins/{category_id}` | — | `[PinnedArticleOut]` | All auth; published pins only |
| POST | `/api/v1/pins` | `{category_id, article_id, display_order}` | `PinnedArticleOut` | Admin only; 422 if >5 or archived (FR-9) |
| DELETE | `/api/v1/pins/{id}` | — | `204` | Admin only (FR-9) |
| GET | `/api/v1/analytics/gaps` | `?limit` | `[{query_text,search_count,weak_result_count}]` | Admin + Leadership; no PII (FR-8) |

## 5. Rules
- **Auth (FR-11, NFR-5):** JWT Bearer via `Depends(get_current_user)`; all non-health routes return 401 if token absent/invalid; Streamlit: `st.session_state["token"]` checked at app entry — missing token redirects to login form; token stores role for tab gating.
- **RBAC (FR-2, FR-10, NFR-6):** roles employee/contributor/knowledge_admin/leadership; API: `Depends(require_role(...))` on every protected route; Streamlit: employee=search+feedback tabs, contributor=+editor tab, knowledge_admin=+admin/analytics tabs, leadership=analytics-only tab.
- **Article lifecycle (FR-2):** state machine enforced in `PATCH /articles/{id}`; contributor may only transition own draft→published; admin transitions any state; archived→search excluded via `WHERE state='published'` filter.
- **Embedding refresh (FR-6, NFR-3):** on `PATCH` with body change and `state=published`, FastAPI background task deletes existing chunks, re-chunks (512-token fixed), calls Titan Embed v2, upserts `article_chunks`; SLA ≤ 2 min.
- **Similarity check (FR-5, NFR-2):** `POST /articles/{id}/similar` calls Titan Embed v2 on draft body, runs pgvector `<=>` against published chunks, returns top-5 distinct articles; advisory only — no publish block.
- **Feedback dedup (FR-7):** UNIQUE constraint on `(search_log_id, article_id, user_id_hash)`; API returns 409 on conflict; only allowed when article `state=published` else 422.
- **Pin guard (FR-9):** `POST /pins` checks `COUNT(*) WHERE category_id=X` ≤ 4 before insert; 422 on limit exceeded or if article state ≠ published; on article archive, background task deletes all pins for that article.
- **Privacy (NFR-7):** `user_id` stored as SHA-256 hash in `search_logs` and `feedback`; `GET /analytics/gaps` query never joins to `users`; Leadership JWT role excluded from any endpoint returning raw user data.

## 6. DB delivery
1. Migration order: `001_enable_pgvector.sql`, `002_users.sql`, `003_categories.sql`, `004_articles.sql`, `005_article_chunks.sql`, `006_search_logs_and_items.sql`, `007_feedback.sql`, `008_pinned_articles.sql`
2. Seed data (`scripts/seed.py`): 5 active categories (IT, HR, Finance, Legal, Onboarding); 15 published articles (including 2 semantically similar VPN-reset articles with distinct wording), 3 drafts, 2 archived; users: 2 employees, 2 contributors, 1 knowledge_admin, 1 leadership; 10 search log rows with feedback signals to populate gap report; 3 pinned articles in IT category.
3. Athena / NoSQL: not used.
