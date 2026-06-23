# Database handoff — gitlab-pipeline-smoke

_Generated 2026-06-23 20:19 UTC by database-agent._

## For developer-agent

Read this file with `dev_read_file` before implementing models and repositories.
Primary API and business rules remain in `designDocPath` (§4–§5).

## Application stack (platform default)

Downstream services are **Python**, not chosen per app in `requirements.txt` from database-agent.
Developer-agent scaffolds from `target-apps/_template/` and uses:

- Python 3.12+
- FastAPI + Pydantic v2
- SQLAlchemy 2.x (recommended for RDS models)
- uvicorn

Base dependencies: `target-apps/_template/requirements.txt` (FastAPI, uvicorn, pydantic).
Add `sqlalchemy`, `psycopg[binary]`, and `alembic` in the service `requirements.txt` when wiring RDS.

## RDS target

| Item | Value |
|------|--------|
| Postgres schema | `gitlab_pipeline_smoke` |
| Database | `sdlc_agentic_ai` |
| Endpoint | `agenticaidbinstance.c1u0cggiolxp.us-east-2.rds.amazonaws.com` |
| SQL artifacts | `target-apps/gitlab-pipeline-smoke/db/sql/` |
| RDS apply (last run) | not this session |
| Dev seed rows/table | 5–10 (see `*_seed.sql`) |

## SQL files (apply order)

1. `target-apps/gitlab-pipeline-smoke/db/sql/000_enable_extensions.sql`
2. `target-apps/gitlab-pipeline-smoke/db/sql/001_create_categories.sql`
3. `target-apps/gitlab-pipeline-smoke/db/sql/002_create_notices.sql`
4. `target-apps/gitlab-pipeline-smoke/db/sql/003_seed.sql`

**Connection:** load credentials from env/Key Vault (NFR-5). Use schema `gitlab_pipeline_smoke` (`search_path` or qualified table names). Do not rely on unqualified `public` for app tables.

## Schema summary (database-agent)

- **2 PostgreSQL tables**: categories (lookup), notices (main content) in gitlab_pipeline_smoke schema
- **PRD mapping**: FR-2 (category management), FR-3/4/5/6 (notice CRUD/filtering/search/archival), FR-7 (uniqueness), FR-8 (date validation)
- **Categories table**: id (uuid PK), name (text unique 1-60 chars), description (text nullable ≤240), created_at
- **Notices table**: id (uuid PK), category_id (FK), title/body/author_name (text with length limits), starts_at/ends_at (timestamptz), is_archived (boolean), created_at/updated_at
- **Extensions**: pg_trgm for case-insensitive text search on title/body fields
- **Constraints**: Foreign key with RESTRICT, date validation (ends_at ≥ starts_at), field length checks
- **Indexes**: Unique on category name, composite for active filtering, GIN for text search
- **No authentication tables**: API uses single shared key from environment (no user/password persistence)

## Implementation notes (database-agent)

- **Schema**: `gitlab_pipeline_smoke` - set search_path in SQLAlchemy connection
- **DSN pattern**: `postgresql://{user}:{pass}@{host}:{port}/sdlc_agentic_ai` with schema qualification
- **Active filtering**: `WHERE is_archived = false AND starts_at <= NOW() AND ends_at >= NOW()`
- **Text search**: Use GIN indexes for ILIKE queries on title/body, pg_trgm enabled for fuzzy matching
- **Foreign keys**: category_id uses RESTRICT - prevent category deletion with existing notices
- **Stable UUIDs**: Categories (550e8400-e29b-...-44665544000[0-2]), Notices (660e8400-e29b-...-44665544000[0-7])
- **Seed data**: 3 categories, 8 notices (4 active, 1 future, 1 expired, 1 archived, 1 additional active)

## ORM parity (required for live RDS)

- **uuid columns** → `PG_UUID(as_uuid=False).with_variant(String(36), 'sqlite')`; Pydantic response schemas: coerce `UUID` → `str` in `@field_validator`.
- **Driver/DSN** → `psycopg[binary]` in requirements; `.env.example`: `postgresql+psycopg://...?sslmode=require`; `POSTGRES_SCHEMA=gitlab_pipeline_smoke` (set search_path in `database.py`, not copied from other apps).

## Developer-agent checklist

1. `dev_read_file` → `docs/design/gitlab-pipeline-smoke.md`
2. `dev_read_file` → `target-apps/gitlab-pipeline-smoke/db/sql/` migrations + seed
3. Scaffold `target-apps/<app>/` from `_template` if empty; extend `requirements.txt` for DB libs
4. SQLAlchemy models aligned with DDL (ENUM + uuid rules above); Pydantic schemas for §4 API
5. README: Windows+bash setup, `.env` copy, uvicorn, Swagger auth, seed UUIDs, RDS smoke test
6. `pytest tests/ -q` passes; engineer smoke-tests one DB list route against RDS after `.env` is set
