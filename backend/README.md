# Backend — SDLC Agentic AI Platform

Python Strands agents, pipeline orchestration, generated target apps, and platform tests.

| Path | Purpose |
|------|---------|
| `agents/` | Specialist agents + `pipeline/` handoffs and run state |
| `agents/_shared/` | Pipeline runner, artifact store (local/S3), delivery profile, validators |
| `target-apps/` | FastAPI apps produced by developer-agent (`_template/` is the scaffold) |
| `inputs/` | Plain-text requirement briefs |
| `docs/` | PRDs, design docs, diagrams (local runs) |
| `scripts/` | `run-sdlc-local.ps1`, RDS apply, AgentCore deploy |
| `config/` | MCP catalog, AgentCore runtime config |
| `a2a/` | Agent registry and agent cards |
| `deploy/` | AgentCore packaging |
| `tests/` | Platform pytest suite (not per-app tests) |

## Setup

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Secrets: `.env` at the **monorepo root** or `backend/.env` (loaded by `agents/_shared/env.py`).  
For S3 artifact reads from the UI, use `backend/.env.local` for `ARTIFACT_STORE`, `ARTIFACT_S3_BUCKET`, and AWS profile overrides.

```powershell
aws sso login --profile eks-admin-user
```

## Run the pipeline

**CLI (full local chain):**

```powershell
cd backend
.\scripts\run-sdlc-local.ps1 -Feature my-app -InputFile inputs\my-app.txt
```

Steps: product → architect → database → RDS apply → developer → verify → gitlab (when `GITLAB_*` set).  
Use `-SkipGitlab` to skip publish; `-WithQa` for qa-agent after gitlab.

**Dashboard:** `frontend/` → submit brief → starts a cloud run (AgentCore A2A when `ARTIFACT_STORE=s3`) or local subprocess when configured.

Details, flags, and presets: `scripts/PIPELINE.md`.

## Run a single agent

```powershell
python agents/product-agent/product_agent.py --input-file inputs/my-app.txt --prd-name my-app
python agents/architect-agent/architect_agent.py --context-file agents/pipeline/my-app.context.json
python agents/database-agent/database_agent.py --context-file agents/pipeline/my-app.context.json
python agents/developer-agent/developer_agent.py --target-app my-app --context-file agents/pipeline/my-app.context.json
python agents/gitlab-agent/gitlab_agent.py --target-app my-app --context-file agents/pipeline/my-app.context.json
```

Per-agent defaults and context keys: `agents/pipeline/README.md`.

## Transport and artifacts

| Mode | Env | Behavior |
|------|-----|----------|
| Local subprocess | `SDLC_PIPELINE_TRANSPORT=local` (default) | Orchestrator spawns agents on this machine |
| AgentCore A2A | `SDLC_PIPELINE_TRANSPORT=a2a` + peer URLs | Agents run on deployed runtimes |
| Local artifacts | `ARTIFACT_STORE=local` | Files under `target-apps/<app>/` |
| S3 artifacts | `ARTIFACT_STORE=s3` + bucket | `runs/<runId>/<app>/` in S3; UI reads via frontend `/api/v1` |

## Tests

```powershell
cd backend
python -m pytest tests/ -q
```

Per-app tests live under `target-apps/<app>/tests/` after developer-agent runs.

## Deploy agents (AgentCore)

```powershell
.\scripts\deploy-agentcore-agents.ps1 -Agents orchestrator_agent,product_agent,architect_agent,database_agent,developer_agent,gitlab_agent
```

Runtime config: `config/agentcore/runtimes.json` (no secrets).

## Key env vars

| Variable | Used for |
|----------|----------|
| `AWS_PROFILE`, `AWS_REGION` | Bedrock, S3, RDS SSO |
| `MODEL_ID`, `CODING_MODEL_ID` | Agent model selection |
| `ARTIFACT_STORE`, `ARTIFACT_S3_BUCKET` | Run artifact storage |
| `SDLC_PIPELINE_TRANSPORT` | `local`, `a2a`, or `auto` |
| `GITLAB_PERSONAL_ACCESS_TOKEN`, `GITLAB_PROJECT_PATH` | gitlab-agent publish |
| `GITLAB_APPS_REPO=true` | Publish to apps repo branch `<app>` instead of `sdlc/<app>` |
| `POSTGRES_MCP_*` / `DATABASE_URL` | database-agent and RDS apply |

Full platform map: monorepo root `README.md`.
