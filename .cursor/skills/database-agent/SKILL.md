---
name: database-agent
description: Designs schemas, migrations, and read-only DB analysis via Postgres MCP. Use when working on database-agent, SQL, or target-app data models.
---

# Database Agent

Runs **after architect-agent**, **before developer-agent**. Acts as a **DB developer**: migrations in git, optional dev seed, MCP apply when flagged.

## Inputs

| Field | Use |
|-------|-----|
| `designDocPath` | §3 tables, §6 migration order + seed |
| `prdPath` | Validate RDS scope vs PRD §7 (read when present) |
| `productAgentOutput` | Orientation only |

## PRD scope

- **In RDS:** entities design §3 lists (users, budgets, anomalies, recommendations, `jira_tickets` link rows for FR-6, audit, etc.)
- **Not in RDS:** Cost Record / CUR (Athena), Jira ticket body (external API), summary files (S3)

## Outputs

- `target-apps/<app>/db/sql/` — numbered migrations + dev seed
- `agents/pipeline/<app>.database-handoff.md` — written by CLI after each run (for developer-agent)
- `target-apps/<app>/db/nosql/` — only if design requires MongoDB
- Compact reply: `schema_summary`, `sql_artifacts`, `handoff_for_developer` (no `execution_commands` if RDS apply succeeded)

## CLI

```powershell
python agents/database-agent/database_agent.py
python agents/database-agent/database_agent.py --with-postgres
python agents/database-agent/database_agent.py --with-postgres --with-mongodb
```

MCP flags **compose**. FinOps MVP is Postgres-only today; MongoDB when design + env creds exist.

Test connectivity: `python scripts/postgres_mcp_smoke.py`
