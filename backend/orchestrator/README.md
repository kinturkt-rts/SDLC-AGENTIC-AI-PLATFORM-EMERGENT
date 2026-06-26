# Orchestrator

Python module that drives the SDLC pipeline. Replaces `scripts/run-sdlc.ps1`
as the primary trigger so the dashboard upload (`POST /api/v1/runs/start`) can
launch a run on any platform (Windows, macOS, Linux, Lambda, container).

## Layout

```
orchestrator/
├── __init__.py
├── config.py           # Loads config/orchestrator/agents.json + env overrides
├── agent_invoker.py    # Pluggable transport: cli | a2a-http | dry-run
├── run_state.py        # Reads/writes agents/pipeline/<feature>.run.json
└── sdlc_pipeline.py    # Sequential 5-step pipeline (product → ... → gitlab)
```

## Sequential pipeline (today)

The orchestrator runs these five steps in order and stops on the first failure:

| # | Step | Agent | Produces |
|---|------|-------|----------|
| 1 | Product (PRD) | `product-agent` | `docs/PRD/<feature>.md`, `agents/pipeline/<feature>.context.json` |
| 2 | Architect (design + diagram) | `architect-agent` | `docs/design/<feature>.md`, `docs/diagrams/generated-diagrams/<feature>.png` |
| 3 | Database (SQL migrations) | `database-agent` | `target-apps/<feature>/db/sql/*.sql`, `db/HANDOFF.md` |
| 4 | Developer (FastAPI) | `developer-agent` | `target-apps/<feature>/app/` + tests |
| 5 | GitLab publish | `gitlab-agent` | `sdlc/<feature>` branch + `<feature>.gitlab-handoff.json` |

Live run state lands in `agents/pipeline/<feature>.run.json` and is merged into
the frontend's `/api/v1/runs/<runId>` response so the dashboard shows
step-by-step progress without polling each agent directly.

## Transport modes

Each agent has its own transport, set in `config/orchestrator/agents.json` and
overridable per-agent with env vars:

| Mode | When | How |
|------|------|-----|
| `cli` | Local dev today | Spawn `python agents/<name>/<name>_agent.py …` as a subprocess |
| `a2a-http` | Agent deployed to Bedrock AgentCore | POST JSON-RPC `message/send` to the AgentCore runtime URL |
| `dry-run` | Smoke-testing wiring without Bedrock | Write placeholder artifacts so downstream steps can proceed |

### Env overrides

For agent `product-agent`:

```bash
AGENT_MODE_PRODUCT_AGENT=a2a-http
AGENT_URL_PRODUCT_AGENT=https://<runtime-id>.bedrock-agentcore.us-east-2.amazonaws.com/
```

Pattern: `AGENT_MODE_<UPPER_WITH_UNDERSCORES>` and `AGENT_URL_<UPPER_WITH_UNDERSCORES>`.

## CLI

```bash
python -m orchestrator.sdlc_pipeline \
    --feature inventory-app \
    --input-file inputs/inventory-app.txt
```

`--json` emits the final run record on stdout.

## AWS rollout checklist

When deploying agents to Bedrock AgentCore one by one:

1. `bash deploy/agentcore/build.sh <agent-name>` → produces the runtime URL.
2. Set `AGENT_MODE_<NAME>=a2a-http` and `AGENT_URL_<NAME>=https://…/` (in `.env` or wherever the frontend/orchestrator runs).
3. Restart the frontend (`npm run dev`) so the spawned orchestrator subprocess inherits the new env.
4. Trigger a run from the dashboard — that step now hits AgentCore; the rest still run locally via CLI.

Repeat per agent until all five are on AgentCore.

### Shared-storage caveat (important when all five go to AgentCore)

Agents today read/write monorepo files directly (`docs/PRD/<feature>.md`,
`target-apps/<feature>/db/sql/*.sql`, …). On AgentCore each runtime has its
own ephemeral disk, so once an agent runs in `a2a-http` mode it cannot see
files written by an earlier `cli`/`a2a-http` step unless they share storage.

Pick one before flipping the last agents to `a2a-http`:

* **GitLab branch as the shared filesystem** — `gitlab-agent` already pushes to
  `sdlc/<feature>`; extend each agent to clone/push between steps (or run them
  on a single AgentCore instance with sticky session).
* **EFS / S3 sync** — mount a shared volume into every AgentCore runtime.
* **Single co-located runtime** — bundle all five agents into one AgentCore
  deployment via `deploy/agentcore/a2a_server.py --agent <name>` so they share
  a disk. Cheapest option for the MVP.

Until that's resolved, run **at most one** agent in `a2a-http` mode at a time
and keep the others in `cli`.
