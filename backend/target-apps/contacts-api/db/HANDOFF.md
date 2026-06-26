# Database handoff — contacts-api

_Generated 2026-06-18 16:04 UTC by database-agent._

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
| Postgres schema | `contacts_api` |
| Database | `(set POSTGRES_MCP_DATABASE)` |
| Endpoint | `(set POSTGRES_MCP_DB_ENDPOINT)` |
| SQL artifacts | `target-apps/contacts-api/db/sql/` |
| RDS apply (last run) | not this session |
| Dev seed rows/table | 5–10 (see `*_seed.sql`) |

## SQL files (apply order)

1. `target-apps/contacts-api/db/sql/001_create_departments.sql`
2. `target-apps/contacts-api/db/sql/001_create_schema.sql`
3. `target-apps/contacts-api/db/sql/002_create_contacts.sql`
4. `target-apps/contacts-api/db/sql/002_create_departments.sql`
5. `target-apps/contacts-api/db/sql/003_add_indexes.sql`
6. `target-apps/contacts-api/db/sql/003_create_contacts.sql`
7. `target-apps/contacts-api/db/sql/004_seed.sql`

**Connection:** load credentials from env/Key Vault (NFR-5). Use schema `contacts_api` (`search_path` or qualified table names). Do not rely on unqualified `public` for app tables.

## ORM parity (required for live RDS)

- **uuid columns** → `PG_UUID(as_uuid=False).with_variant(String(36), 'sqlite')`; Pydantic response schemas: coerce `UUID` → `str` in `@field_validator`.
- **Driver/DSN** → `psycopg[binary]` in requirements; `.env.example`: `postgresql+psycopg://...?sslmode=require`; `POSTGRES_SCHEMA=contacts_api` (set search_path in `database.py`, not copied from other apps).

## Developer-agent checklist

1. `dev_read_file` → `docs/design/contacts-api.md`
2. `dev_read_file` → `target-apps/contacts-api/db/sql/` migrations + seed
3. Scaffold `target-apps/<app>/` from `_template` if empty; extend `requirements.txt` for DB libs
4. SQLAlchemy models aligned with DDL (ENUM + uuid rules above); Pydantic schemas for §4 API
5. README: Windows+bash setup, `.env` copy, uvicorn, Swagger auth, seed UUIDs, RDS smoke test
6. `pytest tests/ -q` passes; engineer smoke-tests one DB list route against RDS after `.env` is set
