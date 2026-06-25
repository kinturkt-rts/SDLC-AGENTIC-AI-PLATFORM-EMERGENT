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

**Run the automated chain (repo root):**

```powershell
aws sso login --profile eks-admin-user
.\scripts\run-sdlc.ps1 -Feature platform-desk -InputFile inputs\platform-desk.txt
```

With QA and without GitLab publish:

```powershell
.\scripts\run-sdlc.ps1 -Feature platform-desk -InputFile inputs\platform-desk.txt -WithQa -SkipGitlab
```

Full flag reference: `scripts/PIPELINE.md`. Flow diagram and handoff details: `docs/SDLC_PIPELINE_FLOW.md`.

**Pipeline telemetry:** each agent run writes `agents/pipeline/<app>.<agent>-telemetry.json`; the script prints a token summary at the end via `agents/_shared/pipeline_telemetry.py`.

## Stack

| Layer | Technology |
|---|---|
| IDE & context | Cursor (`.cursor/rules/`, `.cursor/skills/`, `README.md`) |
| Agent runtime | [AWS Strands Agents SDK](https://strandsagents.com/) (Python 3.12+) |
| LLM | Amazon Bedrock via Strands model providers |
| Message bus | BullMQ on Redis (orchestrator in TypeScript — **planned**, not scaffolded yet) |
| MCP tools | Open-source servers (Atlassian, GitLab, Terraform) — see `config/mcp/servers.json` |
| Target services | Python / FastAPI (scaffolded from `target-apps/_template/`) |
| Infra | Terraform — dev / staging / prod (**planned**, see `infrastructure/README.md`) |

## Folder map

```
AutonomousSDLC/
├── README.md                   # Master context (this file)
├── .cursor/
│   ├── mcp.json                # Cursor MCP server config
│   ├── rules/                  # Persistent Cursor rules (.mdc)
│   └── skills/                 # Project-scoped agent skills (SKILL.md)
├── .env                        # Secrets — git-ignored
├── requirements.txt            # Python deps (Strands + shared)
├── scripts/                    # setup.sh, run-sdlc.ps1, RDS/MCP helpers
│
├── agents/                     # Strands specialist agents (Python)
│   ├── _shared/                # runner, schemas, MCP helpers, pipeline context
│   ├── orchestrator-agent/     # orchestrator_agent.py
│   ├── product-agent/          # product_agent.py (+ Jira via Atlassian MCP)
│   ├── architect-agent/        # architect_agent.py
│   ├── web-crawler/            # web_crawler_agent.py
│   ├── database-agent/         # database_agent.py
│   ├── developer-agent/        # developer_agent.py
│   ├── gitlab-agent/           # gitlab_agent.py (MCP publish to sdlc/<app>)
│   ├── qa-agent/               # qa_agent.py
│   ├── devops-agent/           # devops_agent.py
│   ├── security-agent/         # security_agent.py
│   └── pipeline/               # per-feature *.context.json + *-handoff.json + telemetry
│
├── orchestrator/               # Planned BullMQ router (README only today)
├── target-apps/                # FastAPI services built by the platform
│   ├── _template/              # canonical scaffold
│   ├── demo-api/               # minimal working example
│   └── <feature>/              # e.g. finops-web-app (db/sql + HANDOFF during pipeline)
│
├── inputs/                     # plain-text requirement briefs for product-agent
├── a2a/                        # Agent-to-Agent registry + agent cards
├── config/
│   ├── guardrails/
│   └── mcp/                    # Open-source MCP catalog + env reference
├── infrastructure/             # Terraform (README only today)
├── tests/                      # pytest at repo root
├── docs/                       # PRD, design/<app>.md, diagrams, SDLC_PIPELINE_FLOW.md
└── monitoring/                 # Planned Grafana dashboards (README only today)
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

Inter-agent messages are JSON envelopes on BullMQ queues (when the TypeScript orchestrator is added). See `agents/_shared/schemas.py` for `AgentMessage`, `TaskPayload`, and `ResultPayload`. Today agents run via CLI and **A2A** HTTP (`a2a/agent-registry.json`).

## Strands agents

Each agent is a **Strands `Agent`** on **Bedrock** in `agents/<name>/*_agent.py` with:

- System prompt as `{NAME}_SYS_PROMPT` in the same file (runner-based agents pass it to `_shared/runner.py`)
- MCP tools via `agents/_shared/mcp_clients.py` (Atlassian SSE, GitLab stdio, AWS Postgres MCP, MongoDB MCP)
- **A2A** peer tools + optional `--serve-a2a` HTTP server (`a2a/agent-registry.json`)

```bash
pip install -r requirements.txt
python agents/product-agent/product_agent.py --task "Your requirement" --project PAY
python agents/product-agent/product_agent.py --serve-a2a   # A2A on :9101
```

See `agents/README.md`, `docs/SDLC_PIPELINE_FLOW.md`, and `a2a/README.md`.

## MCP (open source)

| Scope | File | Servers |
|-------|------|---------|
| Project | `.cursor/mcp.json` | Atlassian, GitLab, MySQL |
| User | `~/.cursor/mcp.json` | ServiceNow, AWS (CloudWatch, DocumentDB), Sentry |

Catalog and env reference: `config/mcp/servers.json`.

**GitLab (Juno):** use jmrplens MCP via `scripts/gitlab_mcp_server.py` (install: `.\scripts\install-jmrplens-gitlab-mcp.ps1`). Set `GITLAB_PERSONAL_ACCESS_TOKEN` and `GITLAB_URL` in `.env`. Native `https://code.junodev.net/api/v4/mcp` needs GitLab Duo Premium (404 until enabled).

```bash
cp .env.example .env   # set GITLAB_PERSONAL_ACCESS_TOKEN, ATLASSIAN_MCP_TOKEN, AWS_*
```

Reload MCP in **Cursor Settings → Tools & MCP** after editing config.

Never commit secrets; use `.env` (git-ignored via `.gitignore`).

## Key conventions

- Python for Strands agents; TypeScript for the orchestrator (planned)
- AWS credentials: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`
- Bedrock model IDs via `MODEL_ID` (product/architect) and `CODING_MODEL_ID` (database/developer) in `.env`
- Target apps scaffold from `target-apps/_template/`; each may add `target-apps/{service}/.cursor/rules/`
- Requirement briefs live under `inputs/`; pipeline handoff under `agents/pipeline/<feature>.context.json`
- GitLab publish: `GITLAB_PERSONAL_ACCESS_TOKEN`, `GITLAB_PROJECT_PATH` in `.env` — see `agents/gitlab-agent/`
- RDS apply: `python scripts/apply_sql_to_rds.py --target-app <app>` (validates seed nullability before apply)
- Terraform remote state per `config/mcp/servers.json` → terraform server section
