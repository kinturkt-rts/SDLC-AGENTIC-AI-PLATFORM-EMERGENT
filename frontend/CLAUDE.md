# frontend

> **Scope:** This file documents `frontend/`. See the root `CLAUDE.md` for setup commands, API mode switching (`NEXT_PUBLIC_API_BASE_URL`), the service-layer architecture, MCP store secret-reference rules, and the ECS deploy script.

## Purpose

Next.js 14 (App Router) control-plane UI for monitoring and operating the SDLC agent pipeline: projects, runs, artifacts, agents, MCP servers, and token usage. The browser never runs Bedrock or agent logic — server routes under `src/app/api/` read platform state and can start pipeline runs.

## Directory structure

```
frontend/
├── src/
│   ├── app/
│   │   ├── (app)/          # Shell layout + all pages
│   │   ├── api/v1/         # REST bridge to backend monorepo state
│   │   ├── api/mcp/        # MCP config CRUD (reads/writes data/mcp.json)
│   │   ├── login/          # Auth login page
│   │   └── layout.tsx      # Root layout + Providers wrapper
│   ├── components/         # Shell, common UI, flow graph, logs viewer
│   ├── features/           # auth/, context/, projects/, runs/, tokens/
│   ├── lib/                # Service layer, data loaders, query hooks
│   ├── mocks/              # Static fixture data for offline/test use
│   ├── store/              # Zustand UI state (ui-store.ts)
│   └── types/              # Shared TypeScript types (index.ts)
├── components/ui/          # shadcn/ui primitives (CLI-generated — do not hand-edit)
├── hooks/                  # Shared React hooks
├── public/                 # Static assets
├── data/                   # mcp.json (git-ignored, written by /api/mcp routes)
├── Dockerfile              # Multi-stage standalone build (includes Python 3 + boto3)
├── next.config.js          # Standalone output, cache policy, CORS headers
├── tailwind.config.js      # Tailwind 3 + shadcn/ui CSS-variable theme
├── tsconfig.json           # strict: true, paths @/* → ./*, ES2020
└── .env.example            # All supported env vars with comments
```

## Pages

> See `src/app/(app)/` for each page's implementation.

| Route | Description |
|-------|-------------|
| `/dashboard` | Summary, activity feed, submit brief / start pipeline run |
| `/runs`, `/runs/[id]` | Pipeline runs list, live progress, handoffs, logs |
| `/projects`, `/projects/[id]` | Target apps — overview, runs, artifacts, context, repo link |
| `/pipelines`, `/pipelines/[id]` | SDLC pipeline definitions |
| `/agents`, `/agents/[id]` | Agent registry, MCP tools, optional connectivity test |
| `/orchestrator`, `/orchestrator/messages` | Orchestrator flow graph and message log |
| `/artifacts` | PRDs, designs, diagrams, generated apps |
| `/context` | Pipeline context documents per project |
| `/mcp` | MCP server registry (edit via UI → `data/mcp.json`) |
| `/tokens` | Per-run model token usage from pipeline telemetry |
| `/checkpoints` | HITL approval queue |
| `/logs` | Run and agent log stream |
| `/settings` | Platform settings |
| `/login` | Cognito auth shell (no-op when Cognito vars are absent) |

## Commands

| Command | What it does |
|---------|-------------|
| `npm run dev` | Dev server on `0.0.0.0:3000` (file-poll mode, 2s interval) |
| `npm run build` | Production Next.js build (standalone output) |
| `npm start` | Start the built standalone server |

Package manager: **yarn** (`yarn install`). Dockerfile uses `npm ci`.

## Key `src/lib/` modules

> Root `CLAUDE.md` covers `api.ts`, `repo-reader.ts`, `artifact-store.ts`, and `mcp-store.ts`.

| Module | Role |
|--------|------|
| `queries.ts` | TanStack Query hooks (`useAgents`, `useRuns`, `useProjects`, etc.) — all pages consume data through these |
| `run-reconcile.ts` | Derives run status (`running`/`failed`/`completed`) from log text + S3 mtime signals; has a test file `run-reconcile.test.ts` |
| `orchestrator-cloud-run.ts` | Builds orchestrator task payload; handles frontend dev-agent retry when orchestrator session dies mid-run |
| `agentcore-invoke.ts` | Invoke deployed AgentCore runtimes via SigV4 (used by cloud run path) |
| `auth-cognito.ts` | Amplify/Cognito client-side session gate — optional, only active when `COGNITO_*` vars are set |
| `auth-session.ts` | Server-side session check for API routes |
| `pipeline-phases.ts` | `MVP_TIMELINE_PHASES`, `PHASE_AGENT`, `PHASE_DISPLAY_LABEL` constants |
| `pipeline-handoffs.ts` | Parse developer/gitlab/devops/qa handoff JSONs; resolve run failure detail |
| `run-events.ts` | Build activity feed from S3 artifacts + log lines |
| `cloudwatch-logs.ts` + `cloudwatch-activity.ts` | Fetch and parse ECS task CloudWatch logs |
| `live-activity.ts` | Filter which runs are "live" (idle threshold: 60 min without S3/log activity) |
| `backend-env.ts` | Load `backend/.env.local` for AWS/S3 config that isn't set in `.env.local` |
| `bedrock-pricing.ts` | Token → USD cost calculation from pipeline telemetry |
| `request-cache.ts` | Server-side in-memory cache (`cachedAsync`) — reduces repeated filesystem reads |
| `runs-cache.ts` | Runs cache key + `invalidateRunsCache()` |
| `repo-root.ts` | `getBackendRoot()` — resolves `BACKEND_ROOT` env var (default `../backend`) |
| `pipeline-telemetry.ts` | Parse and aggregate `pipeline-telemetry.json` per run |
| `brief-payload.ts` | Build the POST body for `POST /api/v1/runs/start` |
| `pipeline-run.ts` | Start a pipeline run (local subprocess or AgentCore A2A) |

## API routes (`src/app/api/v1/`)

Each sub-directory is a Next.js route handler that reads backend state (filesystem or S3):

`activity`, `agent-messages`, `agents`, `artifacts`, `auth`, `checkpoints`, `context`, `dashboard`, `inputs`, `logs`, `mcp-servers`, `pipelines`, `projects`, `repo-asset`, `runs`, `settings`, `telemetry`

`src/app/api/[[...path]]` proxies unmatched routes to `NEXT_PUBLIC_API_BASE_URL` when set.

## Conventions

- **TypeScript:** `strict: true`, path alias `@/*` maps to repo root (`./`), `ES2020` target, no emit (Next handles compilation)
- **Styling:** Tailwind CSS 3.4.1 + CSS custom properties for all colors; dark mode via `darkMode: ["class"]`; shadcn/ui components live in root-level `components/ui/` — regenerate with the shadcn CLI, do not hand-edit
- **State:** TanStack Query for server data (see `queries.ts`); Zustand `store/ui-store.ts` for client-only UI state (sidebar open/closed, etc.)
- **Data flow:** all pages read through `api.ts` → TanStack Query hooks; server API routes read filesystem/S3 via `repo-reader.ts` and `artifact-store.ts`
- **No agent execution in the browser** — API routes may start a subprocess or invoke AgentCore, but client components only read state

## Environment variables

> Root `CLAUDE.md` covers `NEXT_PUBLIC_API_BASE_URL`, `ARTIFACT_STORE`, `ARTIFACT_S3_BUCKET`, `AWS_*`, and `SDLC_PIPELINE_TRANSPORT`.

| Variable | Purpose | Default |
|----------|---------|---------|
| `BACKEND_ROOT` | Path to `backend/` for API routes | `../backend` (container: `/backend`) |
| `ORCHESTRATOR_PYTHON` | Python executable for subprocess runs | auto-detect `backend/.venv` |
| `CORS_ORIGINS` | CORS allow-list for API routes | `*` |
| `SDLC_GITLAB_FALLBACK_HANDOFF_WAIT_SEC` | Seconds to wait for developer output before cloud GitLab publish | `900` |
| `SDLC_GITLAB_PUBLISH_RETRIES` | Re-attempts after first GitLab publish failure | `2` |
| `SDLC_DEVELOPER_FRONTEND_RETRY_ATTEMPTS` | Dev-agent retries when orchestrator session dies | `1` |
| `SDLC_DEV_FALLBACK_HANDOFF_WAIT_SEC` | Wait for dev handoff before frontend retry | `900` |
| `SDLC_ALLOW_PARTIAL_PUBLISH` | Publish to GitLab even if handoff not `completed` | `false` |
| `DEVELOPER_AGENT_FALLBACK_MODEL_ID` | Bedrock model for frontend dev-agent retry | `us.anthropic.claude-sonnet-4-6` |
| `COGNITO_USER_POOL_ID` | Cognito User Pool (from Terraform output) | unset = auth disabled |
| `COGNITO_CLIENT_ID` | Cognito app client ID | unset = auth disabled |
| `COGNITO_REGION` | Cognito region | unset = auth disabled |

## Docker / ECS

Multi-stage build (Node 20 Alpine). The runner stage:
- Installs Python 3 + `boto3` + `python-dotenv` for API route subprocess calls
- Sets `BACKEND_ROOT=/backend` and `SDLC_PIPELINE_TRANSPORT=a2a` as runtime defaults
- Copies `backend/agents`, `config`, `docs`, `scripts`, `inputs`, `a2a` into `/backend/` so API routes can read platform state

Build context is the **monorepo root** (`frontend/Dockerfile` copies from `backend/`). Build + push: `backend/scripts/push-frontend-ecr.ps1`.

## Tests

Only `src/lib/run-reconcile.test.ts` exists. No test runner is wired in `package.json`. Run it directly with your test runner of choice (Jest/Vitest).

## Restrictions and notes

- `components/ui/` is shadcn/ui generated output — add components via the shadcn CLI, not by hand-editing existing files
- MCP server env values in `data/mcp.json` must be `${env:NAME}` references; raw secrets are rejected by `mcp-store.ts`
- `next.config.js` sets `X-Frame-Options: ALLOWALL` and `frame-ancestors *` — the UI is intentionally embeddable in iframes
- HTML responses have `Cache-Control: no-cache` (stale shell keeps old JS chunks alive); `/_next/static/*` is `immutable` with a 1-year TTL
- `NEXT_TELEMETRY_DISABLED=1` is set in the Dockerfile build stage
