# Database handoff — expense-tracker

_Generated 2026-07-20 19:17 UTC by database-agent._

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
| Postgres schema | `expense_tracker` |
| Database | `sdlc_agentic_ai` |
| Endpoint | `agenticaidbinstance.c1u0cggiolxp.us-east-2.rds.amazonaws.com` |
| SQL artifacts | `target-apps/expense-tracker/db/sql/` |
| RDS apply (last run) | yes — apply_sql_to_rds.py |
| Dev seed rows/table | 5–10 (see `*_seed.sql`) |

## SQL files (apply order)

1. `target-apps/expense-tracker/db/sql/001_create_teams.sql`
2. `target-apps/expense-tracker/db/sql/002_create_users.sql`
3. `target-apps/expense-tracker/db/sql/003_create_api_keys.sql`
4. `target-apps/expense-tracker/db/sql/004_create_fx_snapshots.sql`
5. `target-apps/expense-tracker/db/sql/005_create_expenses.sql`
6. `target-apps/expense-tracker/db/sql/006_create_audit_log.sql`
7. `target-apps/expense-tracker/db/sql/007_create_indexes.sql`
8. `target-apps/expense-tracker/db/sql/008_seed.sql`

**Connection:** load credentials from env/Key Vault (NFR-5). Use schema `expense_tracker` (`search_path` or qualified table names). Do not rely on unqualified `public` for app tables.

## Schema summary (database-agent)

- **6 tables** created: `teams`, `users`, `api_keys`, `fx_snapshots`, `expenses`, `audit_log`
- No enums used — `category`, `status`, `role` stored as constrained `VARCHAR(20)` per design §3
- `teams` — FR-7 team management
- `users` — FR-9 employee/manager/admin auth with `token_hash` (bcrypt)
- `api_keys` — FR-9, NFR-1 manager/admin API key auth with `key_hash` (bcrypt)
- `fx_snapshots` — FR-10 daily FX rate storage; `UNIQUE(currency, date)`
- `expenses` — FR-1/2/3/4/5 full expense lifecycle; `NUMERIC(19,4)` for all monetary columns
- `audit_log` — FR-8, NFR-7 append-only immutable trail
- Composite index `idx_expenses_team_date(team_id, expense_date, status, deleted_at)` — NFR-4 P95 ≤ 500 ms
- Index `idx_expenses_user(user_id, status)` — employee own-expense listing
- Index `idx_audit_expense(expense_id, created_at)` — audit trail retrieval
- All tables use `IF NOT EXISTS` for idempotent re-runs
- Seed: 5 teams, 7 users, 5 api_keys, 8 fx_snapshots, 10 expenses, 10 audit_log rows

## Implementation notes (database-agent)

- **DSN pattern:** `postgresql+asyncpg://<user>:<pass>@agenticaidbinstance.c1u0cggiolxp.us-east-2.rds.amazonaws.com:5432/sdlc_agentic_ai` with schema `expense_tracker`
- **SQLAlchemy:** set `schema` in `MetaData(schema="expense_tracker")` or use `__table_args__ = {"schema": "expense_tracker"}`
- **Auth column:** `users.token_hash` stores bcrypt of employee bearer tokens; `api_keys.key_hash` stores bcrypt of admin/manager API keys
- **Monetary columns:** all `NUMERIC(19,4)` — map to Python `Decimal`; never use `float`
- **Stable user UUIDs:** admin=`b1b2c3d4-0001-...0001`, manager=`b1b2c3d4-0003-...0003`, alice(employee)=`b1b2c3d4-0004-...0004`, bob=`b1b2c3d4-0005-...0005`
- **Stable team UUID:** Engineering=`a1b2c3d4-0001-...0001`
- **FX lookup:** query `fx_snapshots` by `(currency, date)` unique pair; raise HTTP 422 if not found
- **Soft-delete:** all list/aggregate queries must filter `WHERE deleted_at IS NULL`

### seedCredentials

| email | role | plaintext_password |
|-------|------|--------------------|
| admin@example.com | admin | ExpenseTest123! |
| admin2@example.com | admin | ExpenseTest123! |
| manager@example.com | manager | ExpenseTest123! |
| alice@example.com | employee | ExpenseTest123! |
| bob@example.com | employee | ExpenseTest123! |
| carol@example.com | employee | ExpenseTest123! |
| dave@example.com | employee | ExpenseTest123! |


## ORM parity (required for live RDS)

- **uuid columns** → `PG_UUID(as_uuid=False).with_variant(String(36), 'sqlite')`; Pydantic response schemas: coerce `UUID` → `str` in `@field_validator`.
- **Driver/DSN** → `psycopg[binary]` in requirements; `.env.example`: `postgresql+psycopg://...?sslmode=require`; `POSTGRES_SCHEMA=expense_tracker` (set search_path in `database.py`, not copied from other apps).

## Developer-agent checklist

1. `dev_read_file` → `docs/design/expense-tracker.md`
2. `dev_read_file` → `target-apps/expense-tracker/db/sql/` migrations + seed
3. Scaffold `target-apps/<app>/` from `_template` if empty; extend `requirements.txt` for DB libs
4. SQLAlchemy models aligned with DDL (ENUM + uuid rules above); Pydantic schemas for §4 API
5. README: Windows+bash setup, `.env` copy, uvicorn, Swagger auth, seed UUIDs, RDS smoke test
6. `pytest tests/ -q` passes; engineer smoke-tests one DB list route against RDS after `.env` is set
