# Database handoff — inventory-app

_Generated 2026-06-09 16:21 UTC by database-agent._

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
| Postgres schema | `inventory_app` |
| Database | `sdlc_agentic_ai` |
| Endpoint | `agenticaidbinstance.c1u0cggiolxp.us-east-2.rds.amazonaws.com` |
| SQL artifacts | `target-apps/inventory-app/db/sql/` |
| RDS apply (last run) | not this session |
| Dev seed rows/table | 5–10 (see `*_seed.sql`) |

## SQL files (apply order)

1. `target-apps/inventory-app/db/sql/001_create_enums_and_users.sql`
2. `target-apps/inventory-app/db/sql/002_create_categories.sql`
3. `target-apps/inventory-app/db/sql/003_create_products.sql`
4. `target-apps/inventory-app/db/sql/004_create_stock_movements.sql`
5. `target-apps/inventory-app/db/sql/011_seed.sql`

**Connection:** load credentials from env/Key Vault (NFR-5). Use schema `inventory_app` (`search_path` or qualified table names). Do not rely on unqualified `public` for app tables.

## Schema summary (database-agent)

- **Schema:** `inventory_app` (single Postgres schema; no MongoDB).
- **Tables (4):** `users`, `categories`, `products`, `stock_movements` — exactly per design §3 / PRD §7.
- **Enums (2):** `user_role('admin','staff')`, `movement_reason('sale','restock','adjustment')` — created idempotently in `001_*.sql`.
- **Extension:** `pgcrypto` for `gen_random_uuid()` (Postgres 13+ assumption, PRD Open Q4).
- **FR-2 / FR-10 →** `users` with bcrypt `password_hash`, `role` enum, `is_active` flag, unique `username` index.
- **FR-4 →** `categories` with unique `slug` index (DB backstop for slug collisions, Risk #6).
- **FR-5 / FR-6 →** `products` with unique `sku`, `category_id` index (filtering), `CHECK (unit_price>=0)`, `CHECK (qty_on_hand>=0)`.
- **FR-7 / NFR-6 →** `qty_on_hand >= 0` CHECK is the DB backstop for the atomic adjust-stock transaction.
- **FR-8 →** composite `(product_id, created_at DESC)` index on `stock_movements` for newest-first paginated history.
- **FR-11 →** `products.category_id` is `ON DELETE RESTRICT`; `stock_movements.product_id` is `ON DELETE CASCADE`; `stock_movements.performed_by` is `ON DELETE SET NULL` to preserve audit trail.
- **Out of scope (correctly omitted):** no audit/log tables (PRD §3), no soft-delete tables, no refresh-token table.
- **Seed (dev only, NFR-10):** 5 users, 5 categories, 8 products (3 at/below `qty_on_hand<=5` for FR-6 low-stock tests), 10 stock_movements covering all 3 reason values, with stable UUIDs for pytest fixtures.

## Implementation notes (database-agent)

- **DSN pattern:** `postgresql+psycopg://<user>:<pwd>@agenticaidbinstance.c1u0cggiolxp.us-east-2.rds.amazonaws.com:5432/sdlc_agentic_ai`; set `POSTGRES_SCHEMA=inventory_app`.
- **Per-session search_path** is required — migrations set it but ORM sessions don't inherit; use a SQLAlchemy `connect` event to `SET search_path TO inventory_app, public` (snippet in `HANDOFF.md`).
- **Native enums** — bind both enums with `create_type=False, schema='inventory_app'` so SQLAlchemy doesn't try to re-create them.
- **Adjust-stock txn (NFR-6):** wrap `SELECT … FOR UPDATE` on `products` row + `UPDATE qty_on_hand` + `INSERT stock_movements` in one transaction; rely on `CHECK (qty_on_hand>=0)` as backstop and surface failure as HTTP 422 (FR-7).
- **`updated_at` on `products`** is application-maintained — set explicitly on PATCH; no DB trigger.
- **Stable seed UUIDs** for tests: admin `11111111-…`, staff `22222222-…`, low-stock product (qty=3) `bbbbbbb1-0000-0000-0000-000000000002`, boundary product (qty=5) `bbbbbbb1-0000-0000-0000-000000000004`. Inactive user `staff_carol` (`5555…`) covers the FR-2 inactive→401 case.
- **Bcrypt hashes** in `011_seed.sql` are dev fixtures generated with the `bcrypt` package (cost=12). If the database-agent regenerates them, run `bcrypt.hashpw(..., bcrypt.gensalt(12))` — do not use placeholder strings. Plaintext passwords (`Admin123!` / `Staff123!`) appear nowhere in SQL — only in `HANDOFF.md` and the README per NFR-10.

(`applyToRdsAfterWrite=true` — the host will run `scripts/apply_sql_to_rds.py` against the RDS endpoint; no execution_commands section needed.)

## Developer-agent checklist

1. `dev_read_file` → `docs/design/inventory-app.md`
2. `dev_read_file` → `target-apps/inventory-app/db/sql/` migrations + seed
3. Scaffold `target-apps/<app>/` from `_template` if empty; extend `requirements.txt` for DB libs
4. SQLAlchemy models aligned with DDL; Pydantic schemas for §4 API
5. Document run steps in `target-apps/inventory-app/README.md` (`uvicorn app.main:app --reload`)
