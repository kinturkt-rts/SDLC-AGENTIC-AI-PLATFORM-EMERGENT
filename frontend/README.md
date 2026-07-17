# SDLC Agentic AI Platform - Control Plane

Next.js 14 (App Router) UI for monitoring and operating the SDLC agent pipeline: projects,
runs, artifacts, agents, MCP servers, and token usage.

The browser does **not** run Bedrock or agent logic directly. Server routes under `src/app/api/`
read platform state and can **start** pipeline runs (local Python subprocess or AgentCore invoke).

## Modes

| Mode | Config | Data source |
|------|--------|-------------|
| **Local (default)** | Leave `NEXT_PUBLIC_API_BASE_URL` unset | Next.js `/api/v1/*` reads `backend/` (filesystem + optional S3 artifact store) |
| **Remote API** | Set `NEXT_PUBLIC_API_BASE_URL` | External platform REST API at that base URL |

Copy `.env.example` → `.env.local` for local development.

## Getting started

```powershell
cd frontend
copy .env.example .env.local
npm install   # or: yarn install
npm run dev   # http://localhost:3000
```

`/` redirects to `/dashboard`. The dashboard can submit an input brief and start a pipeline run
(`POST /api/v1/runs/start` → `backend/scripts/run-sdlc-local.ps1` or AgentCore when
`SDLC_PIPELINE_TRANSPORT=a2a`).

## Environment variables

| Variable | Purpose |
|----------|---------|
| `NEXT_PUBLIC_API_BASE_URL` | Optional remote API base. Unset = local `/api/v1` mode. |
| `BACKEND_ROOT` | Path to `backend/` (default: `../backend`) |
| `ORCHESTRATOR_PYTHON` | Python for pipeline subprocess (default: auto-detect `backend/.venv`) |
| `SDLC_PIPELINE_TRANSPORT` | `local` (subprocess) or `a2a` (AgentCore cloud invoke) |
| `ARTIFACT_STORE`, `ARTIFACT_S3_BUCKET`, `AWS_*` | S3 run artifacts - loaded from `backend/.env.local` if unset here |
| `CORS_ORIGINS` | CORS allow-list for API routes (default: `*`) |

See `.env.example` for comments. Secrets stay in env files - never in the repo.

## Pages

| Route | Description |
|-------|-------------|
| `/dashboard` | Summary, activity feed, submit brief / start pipeline |
| `/runs`, `/runs/[id]` | Pipeline runs, live progress, handoffs, logs |
| `/projects`, `/projects/[id]` | Target apps - overview, runs, artifacts, context, repo link |
| `/pipelines`, `/pipelines/[id]` | SDLC pipeline definitions |
| `/agents`, `/agents/[id]` | Agent registry, MCP tools, optional connectivity test |
| `/orchestrator`, `/orchestrator/messages` | Orchestrator flow and message log |
| `/artifacts` | PRDs, designs, diagrams, generated apps |
| `/context` | Pipeline context documents per project |
| `/mcp` | MCP server registry (edit via UI → `frontend/data/mcp.json`) |
| `/tokens` | Per-run model token usage from pipeline telemetry |
| `/checkpoints` | HITL approval queue (local UI state until platform API wired) |
| `/logs` | Run and agent log stream |
| `/settings` | Platform settings |
| `/login` | Auth shell (placeholder) |

## Project layout

```
src/
  app/
    (app)/          # Shell + pages
    api/v1/         # REST bridge: agents, runs, projects, artifacts, telemetry, …
    api/mcp/        # MCP config CRUD
  components/       # Shell, common UI, shadcn/ui
  features/         # Auth, context, runs handoffs, tokens, projects
  lib/              # api.ts (service layer), repo-reader.ts, artifact-store.ts, queries
  store/            # Zustand UI state
  types/            # Shared TypeScript types
```

All pages consume data through `src/lib/api.ts` and TanStack Query hooks in `src/lib/queries.ts`.

## Deployed UI

Docker/ECS packaging lives under repo deploy scripts (e.g. `backend/scripts/push-frontend-ecr.ps1`).
Set `BACKEND_ROOT=/backend` in the container so API routes can reach agent config and inputs.
