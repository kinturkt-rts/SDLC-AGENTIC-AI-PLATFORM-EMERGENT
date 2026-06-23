# gitlab-pipeline-smoke — Solution Design

## 1. Summary
Team Notice Board API: a FastAPI + PostgreSQL service for creating, filtering, and archiving short-form team notices with API-key-protected writes and anonymous reads. Streamlit UI at `ui/streamlit_app.py` calls FastAPI over HTTP. TBD: `/health` DB-ping vs static; un-archive support; Postgres sslmode in local Docker.

Diagram: `docs/diagrams/generated-diagrams/gitlab-pipeline-smoke.png`

## 2. Stack
| Layer | Technology | Path |
|-------|------------|------|
| UI | Streamlit | `ui/streamlit_app.py` calls FastAPI over HTTP (port 8501) |
| API | FastAPI + Pydantic v2 | `target-apps/gitlab-pipeline-smoke/app/` |
| ORM | SQLAlchemy 2.x sync | `app/database.py` dialect guard (Postgres/SQLite) |
| DB | PostgreSQL (schema `gitlab_pipeline_smoke`) | `psycopg[binary]`; SQLite in-memory for pytest |
| Auth | API key via `X-API-Key` header (PyJWT-free) | `app/dependencies.py` checks `API_KEY` env var |
| Config | pydantic-settings + `.env` | `DATABASE_URL`, `POSTGRES_SCHEMA`, `API_KEY`, `PORT` |

## 3. Data model
| Table | Columns | Indexes / constraints |
|-------|---------|-----------------------|
| `categories` | `id uuid PK`, `name text NOT NULL UNIQUE`, `description text`, `created_at timestamptz NOT NULL DEFAULT now()` | UNIQUE on `name` |
| `notices` | `id uuid PK`, `category_id uuid FK→categories.id ON DELETE RESTRICT`, `title text NOT NULL`, `body text NOT NULL`, `author_name text NOT NULL`, `starts_at timestamptz`, `ends_at timestamptz`, `is_archived bool NOT NULL DEFAULT false`, `created_at timestamptz NOT NULL DEFAULT now()`, `updated_at timestamptz NOT NULL DEFAULT now()` | `CREATE INDEX ON notices (is_archived, starts_at DESC)` |

## 4. API surface
| Method | Path | Request | Response | Notes |
|--------|------|---------|----------|-------|
| GET | `/health` | — | `{status, service}` | No auth (FR-1) |
| GET | `/api/v1/categories` | — | `[{id,name,description,created_at}]` | No auth; sorted by name (FR-9) |
| GET | `/api/v1/categories/{id}` | — | category obj \| 404 | No auth |
| POST | `/api/v1/categories` | `{name, description?}` | 201 category | API key; 409 on dup name (FR-9) |
| PATCH | `/api/v1/categories/{id}` | `{name?, description?}` | 200 category | API key; 409 on name collision |
| GET | `/api/v1/notices` | `?active_only=true&category_id?&q?&limit=20&offset=0` | `{items,total,limit,offset}` | No auth (FR-2, FR-3, FR-10) |
| GET | `/api/v1/notices/{id}` | — | notice obj \| 404 | No auth (FR-4) |
| POST | `/api/v1/notices` | `{title,body,author_name,category_id,starts_at?,ends_at?}` | 201 notice | API key; 404 unknown category; 422 ends_at<starts_at (FR-5) |
| PATCH | `/api/v1/notices/{id}` | partial notice fields | 200 notice | API key; same validations (FR-6) |
| POST | `/api/v1/notices/{id}/archive` | — | 204 | API key; idempotent (FR-7) |

## 5. Rules
- **Auth**: `verify_api_key` dependency injected on all POST/PATCH routes; missing/wrong key → 401; key never logged (FR-8, NFR-3, NFR-4).
- **Active filter**: `is_archived=false AND starts_at <= now() AND (ends_at IS NULL OR ends_at > now())` evaluated in DB with `now()` UTC (FR-2).
- **Search**: `?q=` applies `ILIKE '%q%'` on `title` and `body`; full-text search deferred to Phase 2 (FR-3).
- **Timestamps**: `updated_at` bumped in application layer (not DB trigger) for SQLite compatibility (FR-6, NFR-11).
- **Archive is one-way**: PATCH cannot set `is_archived=false`; only `POST /archive` toggles it to true (NFR-8).
- **FK guard**: `POST /notices` with unknown `category_id` → 404 before insert (FR-15); `ON DELETE RESTRICT` enforced at DB level.
- **No DELETE routes**: notices and categories are never physically deleted (NFR-8).
- **Secrets**: `API_KEY` and `DATABASE_URL` from env only; `.env` in `.gitignore`; `.env.example` ships with placeholder (NFR-4).

## 6. DB delivery
1. Migration order: `001_schema.sql` (create schema, `categories`, `notices`, index), `002_seed.sql` (seed rows)
2. Seed (`002_seed.sql`): 3 categories (`General`, `HR`, `Engineering`) with stable UUIDs; 5 notices (1 active, 1 future `starts_at`, 1 expired `ends_at`, 1 archived, 1 active different category) using `ON CONFLICT DO NOTHING` (FR-11)
3. All tables in schema `gitlab_pipeline_smoke`; set via `SET search_path TO gitlab_pipeline_smoke` at top of each migration file
