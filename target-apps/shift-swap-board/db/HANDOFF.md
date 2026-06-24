# Database handoff — shift-swap-board

_Generated 2026-06-24 15:55 UTC by database-agent._

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
| Postgres schema | `shift_swap_board` |
| Database | `sdlc_agentic_ai` |
| Endpoint | `agenticaidbinstance.c1u0cggiolxp.us-east-2.rds.amazonaws.com` |
| SQL artifacts | `target-apps/shift-swap-board/db/sql/` |
| RDS apply (last run) | not this session |
| Dev seed rows/table | 5–10 (see `*_seed.sql`) |

## SQL files (apply order)

1. `target-apps/shift-swap-board/db/sql/001_create_enum_types.sql`
2. `target-apps/shift-swap-board/db/sql/002_users.sql`
3. `target-apps/shift-swap-board/db/sql/003_staff_profiles.sql`
4. `target-apps/shift-swap-board/db/sql/004_shift_roster.sql`
5. `target-apps/shift-swap-board/db/sql/005_floor_lead_weeks.sql`
6. `target-apps/shift-swap-board/db/sql/006_swap_requests.sql`
7. `target-apps/shift-swap-board/db/sql/007_swap_audit_log.sql`
8. `target-apps/shift-swap-board/db/sql/011_seed.sql`

**Connection:** load credentials from env/Key Vault (NFR-5). Use schema `shift_swap_board` (`search_path` or qualified table names). Do not rely on unqualified `public` for app tables.

## ORM parity (required for live RDS)

- **ENUM `user_role`** → `sqlalchemy.Enum(..., name='user_role', schema='shift_swap_board', create_type=False, native_enum=True)` + `.with_variant(String, 'sqlite')` (see `_template/app/models/pg_types.py`).
- **ENUM `shift_window`** → `sqlalchemy.Enum(..., name='shift_window', schema='shift_swap_board', create_type=False, native_enum=True)` + `.with_variant(String, 'sqlite')` (see `_template/app/models/pg_types.py`).
- **ENUM `swap_status`** → `sqlalchemy.Enum(..., name='swap_status', schema='shift_swap_board', create_type=False, native_enum=True)` + `.with_variant(String, 'sqlite')` (see `_template/app/models/pg_types.py`).
- **uuid columns** → `PG_UUID(as_uuid=False).with_variant(String(36), 'sqlite')`; Pydantic response schemas: coerce `UUID` → `str` in `@field_validator`.
- **Driver/DSN** → `psycopg[binary]` in requirements; `.env.example`: `postgresql+psycopg://...?sslmode=require`; `POSTGRES_SCHEMA=shift_swap_board` (set search_path in `database.py`, not copied from other apps).

## Developer-agent checklist

1. `dev_read_file` → `docs/design/shift-swap-board.md`
2. `dev_read_file` → `target-apps/shift-swap-board/db/sql/` migrations + seed
3. Scaffold `target-apps/<app>/` from `_template` if empty; extend `requirements.txt` for DB libs
4. SQLAlchemy models aligned with DDL (ENUM + uuid rules above); Pydantic schemas for §4 API
5. README: Windows+bash setup, `.env` copy, uvicorn, Swagger auth, seed UUIDs, RDS smoke test
6. `pytest tests/ -q` passes; engineer smoke-tests one DB list route against RDS after `.env` is set
