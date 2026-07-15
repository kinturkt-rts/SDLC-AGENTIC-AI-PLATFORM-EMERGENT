# Database handoff — benefits-qa-desk

_Generated 2026-07-15 19:25 UTC by database-agent._

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
| Postgres schema | `benefits_qa_desk` |
| Database | `sdlc_agentic_ai` |
| Endpoint | `agenticaidbinstance.c1u0cggiolxp.us-east-2.rds.amazonaws.com` |
| SQL artifacts | `target-apps/benefits-qa-desk/db/sql/` |
| RDS apply (last run) | yes — apply_sql_to_rds.py |
| Dev seed rows/table | 5–10 (see `*_seed.sql`) |

## SQL files (apply order)

1. `target-apps/benefits-qa-desk/db/sql/001_enable_pgvector.sql`
2. `target-apps/benefits-qa-desk/db/sql/002_create_users.sql`
3. `target-apps/benefits-qa-desk/db/sql/003_create_collections.sql`
4. `target-apps/benefits-qa-desk/db/sql/004_create_documents.sql`
5. `target-apps/benefits-qa-desk/db/sql/005_create_document_chunks.sql`
6. `target-apps/benefits-qa-desk/db/sql/006_create_faq_topics.sql`
7. `target-apps/benefits-qa-desk/db/sql/007_create_audit_events.sql`
8. `target-apps/benefits-qa-desk/db/sql/008_seed.sql`

**Connection:** load credentials from env/Key Vault (NFR-5). Use schema `benefits_qa_desk` (`search_path` or qualified table names). Do not rely on unqualified `public` for app tables.

## ORM parity (required for live RDS)

- **ENUM `user_role`** → `sqlalchemy.Enum(..., name='user_role', schema='benefits_qa_desk', create_type=False, native_enum=True)` + `.with_variant(String, 'sqlite')` (see `_template/app/models/pg_types.py`).
- **ENUM `document_status`** → `sqlalchemy.Enum(..., name='document_status', schema='benefits_qa_desk', create_type=False, native_enum=True)` + `.with_variant(String, 'sqlite')` (see `_template/app/models/pg_types.py`).
- **uuid columns** → `PG_UUID(as_uuid=False).with_variant(String(36), 'sqlite')`; Pydantic response schemas: coerce `UUID` → `str` in `@field_validator`.
- **Driver/DSN** → `psycopg[binary]` in requirements; `.env.example`: `postgresql+psycopg://...?sslmode=require`; `POSTGRES_SCHEMA=benefits_qa_desk` (set search_path in `database.py`, not copied from other apps).

## Developer-agent checklist

1. `dev_read_file` → `docs/design/benefits-qa-desk.md`
2. `dev_read_file` → `target-apps/benefits-qa-desk/db/sql/` migrations + seed
3. Scaffold `target-apps/<app>/` from `_template` if empty; extend `requirements.txt` for DB libs
4. SQLAlchemy models aligned with DDL (ENUM + uuid rules above); Pydantic schemas for §4 API
5. README: Windows+bash setup, `.env` copy, uvicorn, Swagger auth, seed UUIDs, RDS smoke test
6. `pytest tests/ -q` passes; engineer smoke-tests one DB list route against RDS after `.env` is set
