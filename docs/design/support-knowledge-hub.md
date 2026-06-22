# Support Knowledge Hub — Solution Design

## 1. Summary
Internal knowledge hub for ~400-person org: semantic article search, lifecycle management (draft→published→archived), AI-assisted duplicate detection, and role-gated analytics. PostgreSQL (+ pgvector) is the primary store; FastAPI serves all business logic; Streamlit provides the role-gated UI. Auth via lightweight JWT (username/password against seeded users).
TBD: embedding model choice (local `all-MiniLM-L6-v2` assumed), vector store confirmed as pgvector, similarity threshold default 0.75.
Diagram: `docs/diagrams/generated-diagrams/support-knowledge-hub.png`

---

## 2. Stack
| Layer | Technology | Path / Notes |
|-------|------------|--------------|
| UI | Streamlit | `ui/streamlit_app.py`; sub-pages in `ui/pages/`; calls FastAPI over HTTP (port 8501) |
| API | FastAPI | `target-apps/support-knowledge-hub/app/`; `X-API-Key` middleware + JWT Bearer |
| LLM / Embeddings | AWS Bedrock (`boto3`) | `app/services/bedrock_client.py`; model ID + region from `.env` |
| Vector search | pgvector (Postgres extension) | `ArticleRepository.search()` abstraction; cosine similarity ANN |
| Database | PostgreSQL | RDS or local Docker; primary relational + vector store |
| Local FS | Filesystem | `data/evidence/` for document files (no S3 in MVP) |

---

## 3. Data model
| Table | Columns | Indexes / Constraints |
|-------|---------|-----------------------|
| `users` | `id uuid PK`, `email text UNIQUE`, `display_name text`, `role text`, `hashed_password text`, `created_at timestamptz` | idx on `role`; role IN ('employee','contributor','knowledge_admin','leadership') |
| `categories` | `id uuid PK`, `name text UNIQUE`, `slug text UNIQUE`, `created_by uuid FK(users)`, `created_at timestamptz` | unique slug |
| `articles` | `id uuid PK`, `title text`, `body text`, `category_id uuid FK(categories)`, `tags text[]`, `author_id uuid FK(users)`, `status text`, `created_at timestamptz`, `updated_at timestamptz`, `published_at timestamptz`, `archived_at timestamptz` | idx `(status, category_id)`; status IN ('draft','published','archived') |
| `article_embeddings` | `id uuid PK`, `article_id uuid FK(articles)`, `chunk_index int`, `chunk_text text`, `embedding vector(384)`, `model_version text`, `embedded_at timestamptz` | ivfflat idx on `embedding`; unique `(article_id, chunk_index)` |
| `pinned_articles` | `id uuid PK`, `category_id uuid FK(categories)`, `article_id uuid FK(articles)`, `pinned_by uuid FK(users)`, `pinned_at timestamptz` | unique `(category_id, article_id)`; max-5-per-category enforced at API |
| `search_events` | `id uuid PK`, `query_text text`, `query_embedding vector(384)`, `result_article_ids uuid[]`, `result_count int`, `role text`, `timestamp timestamptz` | idx on `timestamp`; no user_id stored |
| `feedback` | `id uuid PK`, `search_event_id uuid FK(search_events)`, `article_id uuid FK(articles)`, `rating text`, `timestamp timestamptz` | unique `(search_event_id, article_id)`; rating IN ('helpful','not_helpful') |

---

## 4. API surface
| Method | Path | Request | Response | Notes |
|--------|------|---------|----------|-------|
| POST | `/auth/token` | `{email, password}` | `{access_token, role}` | Public; issues JWT |
| GET | `/health` | — | `{status, version}` | Unauthenticated |
| POST | `/articles` | `{title, body, category_id, tags[]}` | `Article` | Contributor+; creates in `draft` |
| PATCH | `/articles/{id}` | `{title?, body?, category_id?, tags?, status?}` | `Article + similar_articles[]` | Triggers similarity check + re-embed on body edit (FR-5, FR-9) |
| GET | `/articles` | `?status&category_id&q` | `Article[]` | Employee+ sees `published` only; Admin sees all |
| GET | `/articles/{id}` | — | `Article` | Employee+ for published; author/admin for draft |
| POST | `/articles/{id}/similar` | `{body}` | `{similar_articles[{id,title,excerpt,score}]}` | Contributor+; advisory only (FR-5) |
| POST | `/search` | `{query, category_ids[]?, top_n?}` | `{results[{article_id,excerpt,score}], search_event_id}` | Employee+; logs SearchEvent (FR-3) |
| POST | `/feedback` | `{search_event_id, article_id, rating}` | `{id, rating}` | Employee+; 409 on duplicate (FR-6) |
| GET | `/admin/analytics/gaps` | `?limit` | `{gaps[{query_text,count,helpful_rate}]}` | knowledge_admin / leadership only (FR-7) |
| POST | `/categories` | `{name, slug}` | `Category` | knowledge_admin only |
| DELETE | `/categories/{id}` | — | `204` / `409` | Blocked if published articles exist (FR-4) |
| POST | `/categories/{id}/pins` | `{article_id}` | `PinnedArticle` | knowledge_admin; 422 if >5 or non-published (FR-8) |

---

## 5. Rules
- **Auth**: All routes except `GET /health` and `POST /auth/token` require `Authorization: Bearer <jwt>`; middleware returns `401` on missing/invalid token (NFR-3).
- **RBAC**: `employee` → search, browse published, feedback; `contributor` → + create/edit own articles, similarity check; `knowledge_admin` → all articles, categories, pins, analytics; `leadership` → read-only analytics only. `403` on role violation (NFR-4).
- **Lifecycle**: Only `knowledge_admin` may archive another user's article or modify another user's published body (FR-2).
- **Similarity warning**: Computed on every `PATCH` save/publish for `contributor+`; response always includes `similar_articles` list (empty if none ≥ 0.75 threshold); never blocks publish (FR-5).
- **Feedback idempotency**: Unique constraint `(search_event_id, article_id)`; duplicate submission returns `409` (FR-6).
- **Privacy**: `search_events` and `feedback` rows store no `user_id` or email; `GET /admin/analytics/gaps` response omits all user identifiers (NFR-5, NFR-11).
- **Category delete guard**: Returns `409 Conflict` listing blocking article IDs if any published articles reference the category (FR-4).
- **Pin guard**: Returns `422` if category already has 5 pins or target article is not `published` (FR-8).

---

## 6. DB delivery
1. Migration order: `001_users.sql`, `002_categories.sql`, `003_articles.sql`, `004_article_embeddings.sql`, `005_pinned_articles.sql`, `006_search_events.sql`, `007_feedback.sql`, `008_enable_pgvector.sql`
2. Seed (`scripts/seed_db.py`, idempotent):
   - 5 categories: `IT`, `HR`, `Finance`, `Legal`, `Facilities`
   - 15+ published articles (≥2 near-duplicate pairs for similarity demo), 3 drafts, 2 archived
   - Users: 5 employees, 2 contributors, 1 knowledge_admin (`priya@example.com`), 1 leadership
   - 20+ search_events (mix of zero-result and weak-rating queries for gaps dashboard)
   - 10+ feedback rows; 3 pinned articles in `IT` category
3. pgvector: enable via `CREATE EXTENSION IF NOT EXISTS vector;` in `008_enable_pgvector.sql`; IVFFlat index on `article_embeddings.embedding` after seed load.
