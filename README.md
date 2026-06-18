# SDLC Agentic AI Platform — Control Plane

A production-quality **Next.js App Router** control plane UI for an SDLC Agentic AI Platform.
It visualizes specialist AI agents, pipeline runs, artifacts, and human-in-the-loop (HITL)
checkpoints across the software delivery lifecycle.

> **Control plane only.** This UI does **not** run agents or LLMs. It reads platform state
> through a typed service layer that is mock-backed today and swaps to a real REST API
> (`NEXT_PUBLIC_API_BASE_URL`) without changing any call sites.

## Tech stack
- **Next.js (App Router)** + **TypeScript (strict)**
- **Tailwind CSS** + **shadcn/ui**
- **TanStack Query** for server state
- **Zustand** for UI state (sidebar, project switcher, environment, filters, selected run)
- **lucide-react** icons
- **next-themes** dark/light mode (dark default)

## Design
Professional devtools aesthetic (Vercel + Linear + GitHub Actions): neutral slate/zinc palette
with a single **teal** accent. Status colors: `queued`=gray, `running`=blue, `completed`=green,
`failed`=red, `waiting_for_human`/`paused`=amber.

## Pages
| Route | Description |
|-------|-------------|
| `/dashboard` | Active runs, pending HITL approvals, recent artifacts, agent health grid, MCP health |
| `/runs` | All pipeline runs with status filter + run detail sheet (phase timeline) |
| `/checkpoints` | HITL gates with approve/reject (recorded locally — no platform API yet) |
| `/projects` | Target apps as project cards |
| `/projects/[id]` | Tabs: Overview, Pipelines, Runs, Artifacts, Context |
| `/pipelines` | Reusable SDLC pipeline definitions with phase flow |
| `/agents` | Agent registry (cards/table toggle), ports 9100–9108 |
| `/agents/[id]` | Capabilities, MCP servers, execution history, disabled "Test agent" |
| `/artifacts` | Deliverables grid with kind filter + preview dialog |
| `/context` | Shared context store (documents, decisions, memory, references) |
| `/mcp` | MCP Registry (health, latency, tools, endpoints) |
| `/logs` | Agent log stream with level filter + search |
| `/settings` | API base URL, theme toggle, auth placeholder (disabled) |

## Project structure
```
src/
  app/                      # App Router (route group "(app)" holds the shell + pages)
    (app)/...               # dashboard, runs, agents, projects, etc.
    api/[[...path]]/route.ts # health check only (control plane is read-only)
    layout.tsx, providers.tsx, globals.css
  components/
    common/                 # StatusBadge, PageHeader, EmptyState, DataTable, AgentCard, ThemeToggle
    shell/                  # Sidebar, Topbar, AppShell
  features/                 # (reserved for feature-specific composition)
  lib/                      # api (mock service layer), queries (TanStack hooks), nav, format
  mocks/                    # typed fixtures: agents, projects, runs, artifacts, checkpoints, mcp, context, logs
  store/                    # zustand UI store
  types/                    # domain interfaces (AgentName, RunStatus, StepStatus, SdlcPhase, ...)
```
> shadcn/ui primitives live in `components/ui` (imported via `@/components/ui/*`).

## Getting started
```bash
yarn install     # or: npm install
yarn dev         # starts Next.js on 0.0.0.0:3000
```
Open the app — `/` redirects to `/dashboard`.

## Environment variables
| Var | Purpose |
|-----|---------|
| `NEXT_PUBLIC_API_BASE_URL` | Base URL of the future platform REST API. **Unset → the UI serves typed mock data.** When set, swap the mock branch in `src/lib/api.ts` for `fetch()`. |

## Swapping mocks for the real API
All data flows through `src/lib/api.ts`. Each method returns a `Promise`. To go live, replace
the mock return with a `fetch(\`${API_BASE_URL}/...\`)` call — the TanStack Query hooks in
`src/lib/queries.ts` and every page remain unchanged.

## Constraints honored
- No agent execution / fake "LLM running" animations in the frontend.
- No secrets in `localStorage`.
- All data via a swappable mock API service layer.
