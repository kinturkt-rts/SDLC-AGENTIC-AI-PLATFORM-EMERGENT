# SDLC pipeline — default commands

Run from **repo root**. Each agent uses a **default task** when `--task` is omitted.
Handoff lives in **`agents/pipeline/<target-app>.context.json`** (auto-loaded unless `--no-auto-context`).

## One-liners (FinOps)

```powershell
# 1 Product — needs input (no default task)
python agents/product-agent/product_agent.py --input-file inputs/finops-web-app.txt --prd-name finops-web-app

# 2 Architect — pass target app (or --context-file from product-agent)
python agents/architect-agent/architect_agent.py --target-app finops-web-app

# 3 Database — default task + auto context (files only)
python agents/database-agent/database_agent.py --target-app finops-web-app

# 3b Database — apply SQL to RDS
python agents/database-agent/database_agent.py --with-postgres

# 4 Developer — default task + auto context
python agents/developer-agent/developer_agent.py --target-app finops-web-app
```

After product-agent, `agents/pipeline/<prd-name>.context.json` is created automatically (`prdPath`, `designDocPath`, `diagramPaths` stubs). Optionally add a short `productAgentOutput` summary for the LLM.
After architect, `run-sdlc.ps1` (or you) should set `diagramPaths` and confirm `designDocPath` → `docs/design/<target-app>.md`.

## Optional flags (only used when provided)

| Flag | Agents | Purpose |
|------|--------|---------|
| `--task "..."` | all | Override default pipeline task |
| `--target-app NAME` | db, dev, arch, qa | **Required** unless context JSON includes `targetApp` (product-agent sets this) |
| `--context-file PATH` | all | Explicit handoff JSON (PowerShell-friendly) |
| `--context-json '{...}'` | all | Inline handoff (avoid on PowerShell) |
| `--no-auto-context` | db, arch, dev | Skip auto-load of `agents/pipeline/*.context.json` |
| `--with-postgres` | database | Attach RDS MCP + optional apply |
| `--with-mongodb` | database | Attach MongoDB MCP |
| `--diagram-name NAME` | architect | PNG basename (default from targetApp) |
| `--skip-design` | architect | Diagram only, no design.md |
| `--jira-key KEY` | developer | Traceability in code |
| `--serve-a2a` | all | HTTP A2A server mode |

## Context file template

`agents/pipeline/finops-web-app.context.json`:

```json
{
  "targetApp": "finops-web-app",
  "prdPath": "docs/PRD/finops-web-app.md",
  "productAgentOutput": "Short MVP summary for the LLM (2-4 sentences).",
  "designDocPath": "docs/design/finops-web-app.md",
  "diagramPaths": ["docs/diagrams/generated-diagrams/finops-web-app.png"],
  "architectSummary": "Optional; auto-filled from design §1 if omitted.",
  "dbOutputDir": "target-apps/finops-web-app/db",
  "preferredSqlPath": "target-apps/finops-web-app/db/sql"
}
```

Canonical content is in **files** (`docs/PRD`, `docs/design/<app>.md`, `db/sql/`). JSON holds **pointers + short summaries**.