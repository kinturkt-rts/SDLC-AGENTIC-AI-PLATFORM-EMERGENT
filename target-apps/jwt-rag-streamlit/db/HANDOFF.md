# Database handoff — jwt-rag-streamlit

_Generated 2026-06-22 19:20 UTC by database-agent._

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
| Postgres schema | `jwt_rag_streamlit` |
| Database | `sdlc_agentic_ai` |
| Endpoint | `agenticaidbinstance.c1u0cggiolxp.us-east-2.rds.amazonaws.com` |
| SQL artifacts | `target-apps/jwt-rag-streamlit/db/sql/` |
| RDS apply (last run) | yes — apply_sql_to_rds.py |
| Dev seed rows/table | 5–10 (see `*_seed.sql`) |

## SQL files (apply order)

1. `target-apps/jwt-rag-streamlit/db/sql/001_enable_pgvector.sql`
2. `target-apps/jwt-rag-streamlit/db/sql/002_schema_and_enums.sql`
3. `target-apps/jwt-rag-streamlit/db/sql/003_users_table.sql`
4. `target-apps/jwt-rag-streamlit/db/sql/004_collections_table.sql`
5. `target-apps/jwt-rag-streamlit/db/sql/005_collection_memberships_table.sql`
6. `target-apps/jwt-rag-streamlit/db/sql/006_documents_table.sql`
7. `target-apps/jwt-rag-streamlit/db/sql/007_document_chunks_table.sql`
8. `target-apps/jwt-rag-streamlit/db/sql/008_chat_sessions_table.sql`
9. `target-apps/jwt-rag-streamlit/db/sql/009_chat_messages_table.sql`
10. `target-apps/jwt-rag-streamlit/db/sql/010_audit_log_table.sql`
11. `target-apps/jwt-rag-streamlit/db/sql/011_seed.sql`

**Connection:** load credentials from env/Key Vault (NFR-5). Use schema `jwt_rag_streamlit` (`search_path` or qualified table names). Do not rely on unqualified `public` for app tables.

## ORM parity (required for live RDS)

- **ENUM `user_role`** → `sqlalchemy.Enum(..., name='user_role', schema='jwt_rag_streamlit', create_type=False, native_enum=True)` + `.with_variant(String, 'sqlite')` (see `_template/app/models/pg_types.py`).
- **ENUM `user_status`** → `sqlalchemy.Enum(..., name='user_status', schema='jwt_rag_streamlit', create_type=False, native_enum=True)` + `.with_variant(String, 'sqlite')` (see `_template/app/models/pg_types.py`).
- **ENUM `collection_member_role`** → `sqlalchemy.Enum(..., name='collection_member_role', schema='jwt_rag_streamlit', create_type=False, native_enum=True)` + `.with_variant(String, 'sqlite')` (see `_template/app/models/pg_types.py`).
- **ENUM `document_status`** → `sqlalchemy.Enum(..., name='document_status', schema='jwt_rag_streamlit', create_type=False, native_enum=True)` + `.with_variant(String, 'sqlite')` (see `_template/app/models/pg_types.py`).
- **Driver/DSN** → `psycopg[binary]` in requirements; `.env.example`: `postgresql+psycopg://...?sslmode=require`; `POSTGRES_SCHEMA=jwt_rag_streamlit` (set search_path in `database.py`, not copied from other apps).

## Developer-agent checklist

1. `dev_read_file` → `docs/design/jwt-rag-streamlit.md`
2. `dev_read_file` → `target-apps/jwt-rag-streamlit/db/sql/` migrations + seed
3. Scaffold `target-apps/<app>/` from `_template` if empty; extend `requirements.txt` for DB libs
4. SQLAlchemy models aligned with DDL (ENUM + uuid rules above); Pydantic schemas for §4 API
5. README: Windows+bash setup, `.env` copy, uvicorn, Swagger auth, seed UUIDs, RDS smoke test
6. `pytest tests/ -q` passes; engineer smoke-tests one DB list route against RDS after `.env` is set
