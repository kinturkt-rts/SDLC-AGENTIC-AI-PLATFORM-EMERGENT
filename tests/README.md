# Platform tests

Pytest suite for **shared agent tooling** (`agents/_shared/`), pipeline scripts, and agent modules — not per-app tests (those live under `target-apps/<app>/tests/`).

```bash
python -m pytest tests/ -q
```

## What is covered

| Area | Module |
|------|--------|
| RDS SQL apply | `test_apply_sql_to_rds.py` |
| RDS / ORM parity checks | `test_validate_rds_parity.py` |
| UI / API surface parity | `test_validate_ui_parity.py` |
| Seed credential parsing | `test_seed_credentials.py` |
| Developer agent helpers | `test_developer_agent.py` |
| Database agent context | `test_database_agent_postgres_context.py` |
| Web crawler utilities | `test_web_crawler_*.py` |
| Other `_shared` helpers | `test_*.py` |

Integration tests that need a real RDS instance or MCP are **not** in this folder. Use manual scripts instead:

- `scripts/postgres_mcp_smoke.py` — Postgres MCP connect + query smoke test
- `scripts/check_rds_network.py` — network reachability to RDS

## Environment

`tests/conftest.py` clears `POSTGRES_MCP_*` and `DATABASE_URL` before each test so local `.env.local` does not make unit tests flaky.
