# Bug Deduper — Solution Design

## 1. Summary
FastAPI service (`target-apps/bug-deduper/`) that accepts bug reports, embeds descriptions via AWS Bedrock Titan, and detects near-duplicate open bugs using pgvector cosine similarity. Postgres stores bug records and embedding vectors; Streamlit provides the analyst UI. TBD: Bedrock Titan embedding dimension (assumed 1536); API key storage mechanism (env vs. DB table).
Diagram: `docs/diagrams/generated-diagrams/bug-deduper.png`

## 2. Stack
| Layer | Technology | Path / Notes |
|-------|------------|--------------|
| UI | Streamlit | `ui/streamlit_app.py` calls FastAPI over HTTP (port 8501) |
| API | FastAPI | `target-apps/bug-deduper/app/` — REST + Swagger at `/docs` |
| Embedding | AWS Bedrock Titan | Sync call on POST/PATCH; model+region via env vars |
| DB | Postgres + pgvector | `bugs` table with HNSW index on `embedding` column |
| Auth | API Key (`X-API-Key`) | Two tiers: `standard` / `admin`; hashed in `api_keys` table |
| Config | Environment variables | `DATABASE_URL`, `BEDROCK_MODEL_ID`, `BEDROCK_REGION`, `SIMILARITY_THRESHOLD`, `TOP_K`, `API_KEY_STANDARD`, `API_KEY_ADMIN` |

## 3. Data model
| Table | Columns | Indexes / Constraints |
|-------|---------|-----------------------|
| `bugs` | `id UUID PK`, `title TEXT NOT NULL`, `description TEXT NOT NULL`, `embedding VECTOR(1536)`, `status bug_status NOT NULL DEFAULT 'open'`, `duplicate_of UUID FK→bugs.id NULLABLE`, `created_at TIMESTAMPTZ DEFAULT now()`, `updated_at TIMESTAMPTZ DEFAULT now()` | HNSW index on `embedding` (cosine); index on `status` |
| `api_keys` | `id UUID PK`, `key_hash TEXT NOT NULL UNIQUE`, `tier key_tier NOT NULL`, `created_at TIMESTAMPTZ DEFAULT now()` | UNIQUE on `key_hash` |

**Enums:** `bug_status` = `open, resolved, closed, duplicate`; `key_tier` = `standard, admin`

## 4. API surface
| Method | Path | Request | Response | Notes |
|--------|------|---------|----------|-------|
| POST | `/bugs` | `{title: str, description: str}` | `201 {bug, similar_bugs[], likely_duplicate: bool, top_match_id: UUID\|null}` | FR-1, FR-2; embeds + vector search |
| PATCH | `/bugs/{id}` | `{title?: str, description?: str}` | `200 {bug, similar_bugs[], likely_duplicate: bool}` | FR-4, FR-8; re-embeds if description changes |
| GET | `/bugs/{id}` | — | `200 {id, title, description, status, duplicate_of, created_at, updated_at}` | FR-9; no vector in response |
| POST | `/bugs/{id}/duplicate` | `{canonical_bug_id: UUID}` | `200 {bug}` | FR-5; admin key only |
| POST | `/bugs/{id}/resolve` | — | `200 {bug}` | FR-10; admin key only |
| GET | `/health` | — | `200 {db: str, bedrock: str}` | NFR-8; unauthenticated |

## 5. Rules
- **Auth:** All endpoints except `GET /health` require valid `X-API-Key` → HTTP 401 if missing/invalid (FR-7, NFR-4).
- **Admin guard:** `POST /bugs/{id}/duplicate` and `POST /bugs/{id}/resolve` require `tier=admin` → HTTP 403 for standard keys (FR-7).
- **Dedup filter:** Vector search queries only `status = 'open'` bugs; `closed`, `resolved`, `duplicate` excluded (FR-3, FR-5, FR-10).
- **Self-exclusion:** On PATCH, filter `id != current_bug_id` in vector search (FR-8).
- **likely_duplicate flag:** `true` when `max(similarity_score) >= SIMILARITY_THRESHOLD` env var (default 0.85); `TOP_K` default 3 (FR-2, FR-6).
- **Re-embed gate:** Bedrock called only when `description` field is present and changed on PATCH; title-only PATCH skips embed (FR-4).
- **Key hashing:** API keys stored as bcrypt hashes; never returned in any response (NFR-4).
- **Structured logging:** JSON log per request with `method`, `path`, `status_code`, `latency_ms`, `bug_id`, `api_key_tier`; similarity scores at DEBUG (NFR-7).

## 6. DB delivery
1. Migration order:
   - `001_enable_pgvector.sql` — `CREATE EXTENSION IF NOT EXISTS vector;`
   - `002_create_enums.sql` — `bug_status`, `key_tier`
   - `003_create_bugs.sql` — `bugs` table + HNSW index
   - `004_create_api_keys.sql` — `api_keys` table
2. Seed data:
   - 2 `api_keys` rows: one `standard` tier, one `admin` tier (bcrypt hashes of test keys `dev-standard-key` / `dev-admin-key`)
   - 3 `bugs` rows with status `open` and pre-computed embeddings (zero-vectors acceptable for local dev smoke tests)
3. pgvector: HNSW index — `CREATE INDEX ON bugs USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64);`
