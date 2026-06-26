# Backend (SDLC platform)

Python agents, orchestrator, target apps, pipeline artifacts, and shared config.

| Path | Purpose |
|------|---------|
| `agents/` | Strands specialist agents + `pipeline/*.context.json` handoffs |
| `orchestrator/` | Sequential pipeline driver (`python -m orchestrator.sdlc_pipeline`) |
| `target-apps/` | FastAPI services built by developer-agent |
| `inputs/` | Plain-text requirement briefs |
| `docs/` | PRDs, design docs, diagrams |
| `scripts/` | `run-sdlc.ps1`, RDS/MCP helpers |
| `config/` | MCP catalog, orchestrator agent transport config |
| `a2a/` | Agent-to-agent registry |
| `deploy/` | Bedrock AgentCore packaging |
| `tests/` | Platform pytest suite |

## Setup

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Secrets: `.env` at **monorepo root** (parent of `backend/`) or `backend/.env` — both are loaded.

## Run pipeline (CLI)

```powershell
cd backend
.\scripts\run-sdlc.ps1 -Feature my-app -InputFile inputs\my-app.txt
```

Or via the dashboard: `frontend/` → Save Input → Start SDLC Pipeline (spawns `orchestrator.sdlc_pipeline` with `cwd=backend/`).

See `orchestrator/README.md` and root `README.md` for AWS transport (`a2a-http`) rollout.
