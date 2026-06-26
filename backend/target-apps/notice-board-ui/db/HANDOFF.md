# Database handoff — notice-board-ui

_Generated 2026-06-24 15:18 UTC by database-agent._

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
| Postgres schema | `notice_board_ui` |
| Database | `your_db_name` |
| Endpoint | `your-rds-host.rds.amazonaws.com` |
| SQL artifacts | `target-apps/notice-board-ui/db/sql/` |
| RDS apply (last run) | not this session |
| Dev seed rows/table | 5–10 (see `*_seed.sql`) |

## SQL files (apply order)

1. `target-apps/notice-board-ui/db/sql/001_create_schema_and_categories.sql`
2. `target-apps/notice-board-ui/db/sql/002_create_notices.sql`
3. `target-apps/notice-board-ui/db/sql/003_create_audit_log.sql`
4. `target-apps/notice-board-ui/db/sql/004_seed_data.sql`

**Connection:** load credentials from env/Key Vault (NFR-5). Use schema `notice_board_ui` (`search_path` or qualified table names). Do not rely on unqualified `public` for app tables.

## ORM parity (required for live RDS)

- **Driver/DSN** → `psycopg[binary]` in requirements; `.env.example`: `postgresql+psycopg://...?sslmode=require`; `POSTGRES_SCHEMA=notice_board_ui` (set search_path in `database.py`, not copied from other apps).

## Developer-agent checklist

1. `dev_read_file` → `docs/design/notice-board-ui.md`
2. `dev_read_file` → `target-apps/notice-board-ui/db/sql/` migrations + seed
3. Scaffold `target-apps/<app>/` from `_template` if empty; extend `requirements.txt` for DB libs
4. SQLAlchemy models aligned with DDL (ENUM + uuid rules above); Pydantic schemas for §4 API
5. README: Windows+bash setup, `.env` copy, uvicorn, Swagger auth, seed UUIDs, RDS smoke test
6. `pytest tests/ -q` passes; engineer smoke-tests one DB list route against RDS after `.env` is set
