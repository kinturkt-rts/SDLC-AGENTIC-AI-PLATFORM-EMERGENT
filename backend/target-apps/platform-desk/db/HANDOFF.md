# Database handoff — platform-desk

_Generated 2026-06-24 17:10 UTC by database-agent._

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
| Postgres schema | `platform_desk` |
| Database | `sdlc_agentic_ai` |
| Endpoint | `agenticaidbinstance.c1u0cggiolxp.us-east-2.rds.amazonaws.com` |
| SQL artifacts | `target-apps/platform-desk/db/sql/` |
| RDS apply (last run) | yes — apply_sql_to_rds.py |
| Dev seed rows/table | 5–10 (see `*_seed.sql`) |

## SQL files (apply order)

1. `target-apps/platform-desk/db/sql/001_create_services.sql`
2. `target-apps/platform-desk/db/sql/002_create_runbooks.sql`
3. `target-apps/platform-desk/db/sql/003_create_runbook_steps.sql`
4. `target-apps/platform-desk/db/sql/004_create_incident_touches.sql`
5. `target-apps/platform-desk/db/sql/005_create_search_events.sql`
6. `target-apps/platform-desk/db/sql/006_create_api_keys.sql`
7. `target-apps/platform-desk/db/sql/007_seed.sql`

**Connection:** load credentials from env/Key Vault (NFR-5). Use schema `platform_desk` (`search_path` or qualified table names). Do not rely on unqualified `public` for app tables.

## ORM parity (required for live RDS)

- **uuid columns** → `PG_UUID(as_uuid=False).with_variant(String(36), 'sqlite')`; Pydantic response schemas: coerce `UUID` → `str` in `@field_validator`.
- **Driver/DSN** → `psycopg[binary]` in requirements; `.env.example`: `postgresql+psycopg://...?sslmode=require`; `POSTGRES_SCHEMA=platform_desk` (set search_path in `database.py`, not copied from other apps).

## Developer-agent checklist

1. `dev_read_file` → `docs/design/platform-desk.md`
2. `dev_read_file` → `target-apps/platform-desk/db/sql/` migrations + seed
3. Scaffold `target-apps/<app>/` from `_template` if empty; extend `requirements.txt` for DB libs
4. SQLAlchemy models aligned with DDL (ENUM + uuid rules above); Pydantic schemas for §4 API
5. README: Windows+bash setup, `.env` copy, uvicorn, Swagger auth, seed UUIDs, RDS smoke test
6. `pytest tests/ -q` passes; engineer smoke-tests one DB list route against RDS after `.env` is set
