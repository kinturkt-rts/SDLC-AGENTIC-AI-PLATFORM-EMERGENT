# Platform tests

Pytest suite for **shared agent tooling** (`agents/_shared/`), pipeline scripts, and agent modules — not per-app tests (those live under `target-apps/<app>/tests/`).

```bash
python -m pytest tests/ -q
```

## What is covered

| Area | Module |
|------|--------|
| Pipeline orchestration + RDS apply | `test_sdlc_pipeline.py` |
| Artifact store (local + S3) | `test_artifact_store.py`, `test_*_s3*.py` |
| GitLab publish | `test_gitlab_agent.py`, `test_gitlab_mcp_actions.py`, `test_gitlab_mcp_client.py` |
| AgentCore deploy / invoke | `test_agentcore_deploy.py`, `test_agentcore_invoke.py`, `test_agentcore_dockerfile.py` |
| CloudWatch log parsing | `test_cloudwatch_logs.py` |
| RDS SQL apply | `test_apply_sql_to_rds.py` |
| RDS / ORM parity checks | `test_validate_rds_parity.py` |
| UI / API surface parity | `test_validate_ui_parity.py` |
| Seed credential parsing | `test_seed_credentials.py`, `test_verify_seed_bcrypt.py` |
| Developer / database / product / QA agents | `test_*_agent*.py` |
| Other `_shared` helpers | `test_pipeline_context.py`, `test_db_handoff.py`, `test_telemetry.py`, … |

Integration tests that need a real RDS instance or MCP are **not** in this folder. Use manual scripts instead:

- `scripts/postgres_mcp_smoke.py` — Postgres MCP connect + query smoke test
- `scripts/check_rds_network.py` — network reachability to RDS

## Environment

`tests/conftest.py` clears `POSTGRES_MCP_*` and `DATABASE_URL` before each test so local `.env.local` does not make unit tests flaky.
