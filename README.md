# SDLC Agentic AI Platform

Agentic AI Platform that automates the full software development lifecycle (SDLC):
requirements → architecture → code → tests → CI/CD → deployment → monitoring.

Built with **Cursor** for IDE-assisted development and **AWS Strands Agents** for runtime agent orchestration.

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
│   ├── qa-agent/               # qa_agent.py
│   ├── devops-agent/           # devops_agent.py
│   ├── security-agent/         # security_agent.py
│   └── pipeline/               # per-feature *.context.json handoff files
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

| Agent | Role |
|---|---|
| orchestrator-agent | Receives tasks, plans, delegates to specialist agents |
| product-agent | Converts business requirements into PRDs, user stories, and Jira epics (Atlassian MCP) |
| architect-agent | AWS architecture diagrams, `docs/design/<app>.md`, ADRs |
| web-crawler-agent | Scrapes web/PRD sources via Firecrawl MCP |
| database-agent | Designs SQL/NoSQL schemas, migrations, and DB script handoff |
| developer-agent | Implements FastAPI under `target-apps/` |
| qa-agent | Generates & runs tests, reports coverage |
| devops-agent | Provisions infra via Terraform, manages CI/CD pipelines |
| security-agent | Static analysis, dependency audit, compliance checks |

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
- Bedrock model IDs via `MODEL_ID` / `CODING_MODEL_ID` in `.env`
- Target apps scaffold from `target-apps/_template/`; each may add `target-apps/{service}/.cursor/rules/`
- Requirement briefs live under `inputs/`; pipeline handoff under `agents/pipeline/<feature>.context.json`
- Terraform remote state per `config/mcp/servers.json` → terraform server section
