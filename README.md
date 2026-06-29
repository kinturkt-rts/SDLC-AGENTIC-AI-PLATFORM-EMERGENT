# SDLC Agentic AI Platform

Agentic AI Platform that automates the software development lifecycle (SDLC) from a plain-text brief through deployable application code, with quality and governance gates.

Built with **Cursor** for IDE-assisted development and **AWS Strands Agents** for runtime agent orchestration.

## SDLC pipeline (target flow)

End-to-end delivery order:

```text
inputs/*.txt
    → product-agent        (PRD + pipeline context [+ optional Jira])
    → architect-agent      (design doc + architecture diagram)
    → web-crawler-agent    (optional — external docs)
    → database-agent       (SQL migrations + seed)
    → apply_sql_to_rds     (shared RDS apply + SQL validation)
    → developer-agent      (FastAPI [+ Streamlit UI when required])
    → local verify         (import smoke + pytest)
    → gitlab-agent         (publish branch sdlc/<app> on GitLab)
    → qa-agent             (extended tests + coverage handoff)
    → devops-agent         (CI/CD + infra — roadmap / manual)
    → security-agent       (SAST, deps, compliance — roadmap / manual)
```

| Step | Agent / script | Status in `run-sdlc.ps1` | Primary outputs |
|------|----------------|--------------------------|-----------------|
| 1 | **product-agent** | Default (skip with `-SkipProduct`) | `docs/PRD/<app>.md`, `agents/pipeline/<app>.context.json` |
| 2 | **architect-agent** | Default (skip with `-SkipArchitect`) | `docs/design/<app>.md`, `docs/diagrams/generated-diagrams/<app>.png` |
| 2b | web-crawler-agent | Opt-in `-WithWebCrawler` | `docs/PRD/scraped/<app>/` |
| 3 | **database-agent** | Default (skip with `-SkipDb`) | `target-apps/<app>/db/sql/` |
| 3b | `apply_sql_to_rds.py` | Default when DB runs (skip with `-SkipPostgres`) | RDS schema + seed |
| 4 | **developer-agent** | Default (skip with `-SkipDeveloper`) | `target-apps/<app>/` |
| 5 | local verify | Default (skip with `-SkipVerify`) | pytest in app folder |
| 6 | **gitlab-agent** | Default after verify when `GITLAB_*` in `.env` (skip with `-SkipGitlab`) | branch `sdlc/<app>`, `agents/pipeline/<app>.gitlab-handoff.json` |
| 7 | **qa-agent** | Opt-in `-WithQa` (skip with `-SkipQa`) | `agents/pipeline/<app>.qa-handoff.json` |
| 8 | **devops-agent** | Not chained yet — run manually | CI/CD, Terraform (planned) |
| 9 | **security-agent** | Not chained yet — run manually | security review handoff (planned) |

**Run the automated chain (`backend/`):**

```powershell
aws sso login --profile eks-admin-user
cd backend
.\scripts\run-sdlc.ps1 -Feature platform-desk -InputFile inputs\platform-desk.txt
```

With QA and without GitLab publish:

```powershell
cd backend
.\scripts\run-sdlc.ps1 -Feature platform-desk -InputFile inputs\platform-desk.txt -WithQa -SkipGitlab
```

Full flag reference: `backend/scripts/PIPELINE.md`. Flow diagram and handoff details: `backend/docs/SDLC_PIPELINE_FLOW.md`.

**Pipeline telemetry:** each agent run writes `backend/agents/pipeline/<app>.<agent>-telemetry.json`; the script prints a token summary at the end via `backend/agents/_shared/pipeline_telemetry.py`.

## Stack

| Layer | Technology |
|---|---|
| IDE & context | Cursor (`.cursor/rules/`, `.cursor/skills/`, `README.md`) |
| Agent runtime | [AWS Strands Agents SDK](https://strandsagents.com/) (Python 3.12+) |
| LLM | Amazon Bedrock via Strands model providers |
| Message bus | BullMQ on Redis (orchestrator in TypeScript — **planned**, not scaffolded yet) |
| MCP tools | Open-source servers (Atlassian, GitLab, Terraform) — see `backend/config/mcp/servers.json` |
| Target services | Python / FastAPI (scaffolded from `backend/target-apps/_template/`) |
| Infra | Terraform — dev / staging / prod (**planned**, see `backend/infrastructure/README.md`) |

## Folder map

```
sdlc-agentic-ai-mvp/
├── README.md                   # Master context (this file)
├── .cursor/                    # Cursor rules, skills, MCP config
├── .env                        # Secrets — git-ignored (monorepo root; also backend/.env supported)
│
├── frontend/                   # Next.js control-plane UI (dashboard, runs, artifacts)
│
└── backend/                    # SDLC platform (agents, orchestrator, target apps, docs)
    ├── requirements.txt        # Python deps (Strands + shared)
    ├── scripts/                # run-sdlc.ps1, RDS/MCP helpers
    ├── agents/                 # Strands specialist agents + pipeline handoffs
    ├── orchestrator/           # Python pipeline driver (cli | a2a-http | dry-run)
    ├── target-apps/            # FastAPI services built by developer-agent
    ├── inputs/                 # Plain-text requirement briefs
    ├── docs/                   # PRD, design, diagrams
    ├── a2a/                    # Agent-to-agent registry
    ├── config/                 # MCP catalog, orchestrator transport config
    ├── deploy/                 # Bedrock AgentCore packaging
    ├── infrastructure/         # Terraform (planned)
    ├── tests/                  # Platform pytest suite
    └── monitoring/             # Planned Grafana dashboards
```

## Agent roster

| Agent | Role | Typical pipeline step |
|---|---|---|
| orchestrator-agent | Receives tasks, plans, delegates to specialist agents | — (planned BullMQ router) |
| **product-agent** | Brief → PRD, pipeline context; optional Jira epic/stories (Atlassian MCP) | **1** |
| **architect-agent** | AWS architecture diagram, `docs/design/<app>.md`, ADRs | **2** |
| web-crawler-agent | Scrapes external docs via Firecrawl MCP | 2b (optional) |
| **database-agent** | SQL migrations, seeds, `db/HANDOFF.md`; pre-apply SQL validation | **3** |
| **developer-agent** | FastAPI (+ Streamlit when required) under `target-apps/` | **4** |
| **gitlab-agent** | Publishes app + PRD/design/pipeline artifacts to GitLab branch `sdlc/<app>` | **6** |
| **qa-agent** | Extended pytest, coverage gaps, QA handoff | **7** (`-WithQa`) |
| devops-agent | Terraform, CI/CD pipelines (GitLab MCP) | **8** (manual / roadmap) |
| security-agent | SAST, dependency audit, compliance checks | **9** (manual / roadmap) |

**Jira:** handled by **product-agent** (`--create-minimal-jira`, Atlassian MCP). A separate `jira-agent` is not implemented.

## Communication pattern

Inter-agent messages are JSON envelopes on BullMQ queues (when the TypeScript orchestrator is added). See `backend/agents/_shared/schemas.py` for `AgentMessage`, `TaskPayload`, and `ResultPayload`. Today agents run via CLI and **A2A** HTTP (`backend/a2a/agent-registry.json`).

## Strands agents

Each agent is a **Strands `Agent`** on **Bedrock** in `backend/agents/<name>/*_agent.py` with:

- System prompt as `{NAME}_SYS_PROMPT` in the same file (runner-based agents pass it to `_shared/runner.py`)
- MCP tools via `backend/agents/_shared/mcp_clients.py` (Atlassian SSE, GitLab stdio, AWS Postgres MCP, MongoDB MCP)
- **A2A** peer tools + optional `--serve-a2a` HTTP server (`backend/a2a/agent-registry.json`)

```bash
cd backend
pip install -r requirements.txt
python agents/product-agent/product_agent.py --task "Your requirement" --project PAY
python agents/product-agent/product_agent.py --serve-a2a   # A2A on :9101
```

See `backend/agents/README.md`, `backend/docs/SDLC_PIPELINE_FLOW.md`, and `backend/a2a/README.md`.

## Control plane (frontend)

`frontend/` holds a **Next.js 14 (App Router) + TypeScript** control-plane UI for visualizing agents, runs, artifacts, MCP servers, and HITL checkpoints. It is **read-only** and **never executes agents** — every page reads through a single typed service layer (`frontend/src/lib/api.ts`).

Today the service layer reads **live backend data** via Next.js routes at `/api/v1/*` (projects from `backend/target-apps/` + `backend/agents/pipeline/*.context.json`, artifacts from `backend/docs/` and SQL, agents from `backend/a2a/agent-registry.json`). Set `NEXT_PUBLIC_API_BASE_URL` only when pointing at a remote platform API.

Run locally:

```powershell
cd frontend
copy .env.example .env.local   # leave NEXT_PUBLIC_API_BASE_URL empty for mock mode
npm install                    # or: yarn install
npm run dev                    # http://localhost:3000  (root redirects to /dashboard)
```

The UI also persists MCP server entries to `frontend/data/mcp.json` (git-ignored) via its own Next API routes under `frontend/src/app/api/mcp/*`. Secrets must be stored as `${env:NAME}` references — raw values are rejected by `frontend/src/lib/mcp-store.ts`.

### Run a pipeline from the dashboard

`/dashboard` has an **Input Requirements** card that drives the full SDLC pipeline:

1. Type a feature slug (e.g. `inventory-app`) and paste/upload the brief.
2. **Save Input** → `POST /api/v1/inputs` writes `backend/inputs/<feature>.txt`.
3. **Start SDLC Pipeline** → `POST /api/v1/runs/start` spawns the orchestrator (cwd `backend/`):

   ```
   python agents/orchestrator-agent/orchestrator_agent.py --run-pipeline --target-app <feature> --input-file inputs/<feature>.txt
   ```

   That runs the SDLC chain via `agents/_shared/sdlc_pipeline.py` (product → architect → database → developer → gitlab; qa optional). Progress is tracked in `backend/agents/pipeline/<feature>.context.json` and handoff JSON files. The dashboard also writes `*.run.json` for live step polling.

Pipeline transport is controlled by env (subprocess **local** vs AgentCore **a2a**):

| Mode | When |
|------|------|
| `local` (default) | Local dev — orchestrator spawns each agent CLI as a subprocess |
| `a2a` | AgentCore runtimes wired via `AGENTCORE_A2A_PEER_URLS` / `ARTIFACT_STORE=s3` |
| `auto` | Picks `a2a` when AgentCore/S3 env is set, else `local` |

```bash
SDLC_PIPELINE_TRANSPORT=local   # force local subprocess chain
```

When deploying agents to AWS one-by-one, flip these env vars (no code changes). See `backend/orchestrator/README.md` for the rollout checklist and the shared-storage caveat that applies when all five agents are on AgentCore.

## MCP (open source)

| Scope | File | Servers |
|-------|------|---------|
| Project | `.cursor/mcp.json` | Atlassian, GitLab, MySQL |
| User | `~/.cursor/mcp.json` | ServiceNow, AWS (CloudWatch, DocumentDB), Sentry |

Catalog and env reference: `backend/config/mcp/servers.json`.

**GitLab (Juno):** use jmrplens MCP via `backend/scripts/gitlab_mcp_server.py` (install: `.\backend\scripts\install-jmrplens-gitlab-mcp.ps1`). Set `GITLAB_PERSONAL_ACCESS_TOKEN` and `GITLAB_URL` in `.env`. Native `https://code.junodev.net/api/v4/mcp` needs GitLab Duo Premium (404 until enabled).

```bash
cp backend/.env.example backend/.env   # or use monorepo-root .env
```

Reload MCP in **Cursor Settings → Tools & MCP** after editing config.

Never commit secrets; use `.env` (git-ignored via `.gitignore`).

## Key conventions

- Python for Strands agents; TypeScript for the orchestrator (planned)
- AWS credentials: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`
- Bedrock model IDs via `MODEL_ID` (product/architect) and `CODING_MODEL_ID` (database/developer) in `.env`
- Target apps scaffold from `backend/target-apps/_template/`; each may add `backend/target-apps/{service}/.cursor/rules/`
- Requirement briefs live under `backend/inputs/`; pipeline handoff under `backend/agents/pipeline/<feature>.context.json`
- GitLab publish: `GITLAB_PERSONAL_ACCESS_TOKEN`, `GITLAB_PROJECT_PATH` in `.env` — see `backend/agents/gitlab-agent/`
- RDS apply: `python backend/scripts/apply_sql_to_rds.py --target-app <app>` (validates seed nullability before apply)
- Terraform remote state per `backend/config/mcp/servers.json` → terraform server section
