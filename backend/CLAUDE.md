# backend

> **Scope:** This file documents `backend/`. See the root `CLAUDE.md` for setup, pipeline commands, agent CLI, architecture, env vars, A2A ports, and adding a new agent.

## Purpose

Python Strands specialist agents, pipeline orchestration, shared infrastructure libraries, Terraform target-app deployments, and the platform pytest suite.

## Directory structure

```
backend/
├── agents/
│   ├── _shared/        # Shared Python library used by every agent
│   ├── pipeline/       # Per-run context.json, handoff JSONs, and telemetry files
│   └── <name>/         # One directory per specialist agent
├── a2a/                # Agent registry (ports) and agent cards
├── config/
│   ├── agentcore/      # runtimes.json (ARNs, no secrets) + .bedrock_agentcore.yaml
│   └── mcp/            # MCP server catalog (servers.json)
├── deploy/
│   └── agentcore/      # Single shared entrypoint + Dockerfile for all AgentCore runtimes
├── infrastructure/     # Terraform modules for ECS Fargate target-app deployments
├── inputs/             # Plain-text requirement briefs (one .txt per app)
├── scripts/            # PowerShell + Python helper scripts
├── target-apps/        # FastAPI apps built by developer-agent (git-ignored output)
├── tests/              # Platform pytest suite (not per-app tests)
├── .bedrock_agentcore.yaml  # Toolkit state: per-agent ARNs, CodeBuild projects
├── Dockerfile          # Root copy of deploy/agentcore/Dockerfile (keep in sync)
└── requirements.txt    # Platform dependencies
```

## `_shared/` library

All specialist agents import from `agents/_shared/`. Key modules:

| Module | Role |
|--------|------|
| `runner.py` | `entrypoint()` — thin-agent scaffold; builds Bedrock model, MCP clients, A2A server |
| `sdlc_pipeline.py` | Deterministic pipeline runner; mirrors `run-sdlc-local.ps1` |
| `artifact_store.py` | Local/S3 read-write with DynamoDB run index; `put_artifact`, `materialize_run`, `new_run_id` |
| `pipeline_context.py` | Path helpers (`prd_rel_path_for_app`, `design_doc_rel_for_app`, etc.) that switch on `ARTIFACT_STORE` |
| `env.py` | `load_repo_env()` — merges `.env` + `.env.local`; SSO-safe (never set static keys when `AWS_PROFILE` is set) |
| `schemas.py` | `AgentMessage`, `TaskPayload`, `ResultPayload` inter-agent envelopes |
| `mcp_clients.py` | `MCP_FACTORIES` dict; `MCPClient` wrappers for Postgres, GitLab, Atlassian, Firecrawl, Terraform |
| `a2a_invoke.py` | `invoke_agent()` — A2A HTTP call with retries |
| `a2a_registry.py` | `agent_port()`, `known_agent_urls()` from `a2a/agent-registry.json` |
| `agentcore_serve.py` | FastAPI + `A2AServer` wrapper for AgentCore runtimes |
| `agentcore_invoke.py` | Invoke a deployed AgentCore runtime via SigV4 |
| `handoff_schemas.py` | Pydantic models for developer/devops/gitlab/qa handoff JSONs |
| `pipeline_telemetry.py` | Read/write `<app>.<agent>-telemetry.json`; `pipeline-telemetry.json` summary |
| `delivery_profile.py` | Per-app delivery profile (UI enabled, DB type, etc.) |
| `db_handoff.py` | `write_db_handoff()` — writes `agents/pipeline/<app>.database-handoff.md` to local or S3 |
| `validate_sql_artifacts.py` | Guards nullable-column drift before RDS apply |
| `materialize_seed_passwords.py` | Replaces `__BCRYPT_PLACEHOLDER__` in seed SQL before apply |
| `gitlab_mcp_client.py` | Typed wrappers around GitLab MCP actions |
| `gitlab_mcp_actions.py` | Higher-level GitLab operations (branch, commit, MR) |
| `cloudwatch_logs.py` | Fetch and parse ECS task logs from CloudWatch |
| `background_tasks.py` | Fire-and-forget async task runner (15-min cap) |
| `diagram_tools.py` | `diagrams`-library helpers for architecture PNGs |
| `paths.py` | `repo_root()`, `backend_root()` — absolute path resolution |
| `seed_credentials.py` | Parse seeded credentials from SQL |
| `verify_seed_bcrypt.py` | Verify bcrypt hashes in seed SQL |
| `control_plane_health.py` | Health-check helpers for the control-plane API surface |
| `api_surface.py` | Introspect FastAPI route tables for parity validation |
| `template_store.py` | Publish/fetch `_template/` scaffold to/from S3 |
| `rds_env.py` | Build `DATABASE_URL` from `POSTGRES_MCP_*` env vars |

## AgentCore deployment

> See root `CLAUDE.md — AgentCore (cloud) deployed agents` for the list of deployed runtimes and `deploy/agentcore/README.md` for full deploy instructions.

**Single Dockerfile for all agents** — `deploy/agentcore/Dockerfile` (and its root-level copy `backend/Dockerfile`) is parameterised by build args:

| Build arg | Default | Purpose |
|-----------|---------|---------|
| `AGENTCORE_AGENT` | `orchestrator-agent` | Which agent to activate |
| `INSTALL_NODE` | `false` | Required for product, devops, web-crawler (Atlassian/GitLab/Firecrawl `npx`) |
| `INSTALL_TERRAFORM` | `false` | Required for devops-agent only |
| `INSTALL_GITLAB_MCP_BINARY` | `false` | Local stdio fallback; prefer `GITLAB_MCP_HTTP_URL` instead |

**Node requirement per agent:**

| Agent | `INSTALL_NODE` |
|-------|----------------|
| product-agent | `true` |
| devops-agent | `true` |
| web-crawler-agent | `true` |
| all others | `false` |

**After editing the shared Dockerfile**, regenerate per-agent copies:
```powershell
.\scripts\sync-agentcore-dockerfiles.ps1
```

**CodeBuild source context** — `source_path` in `.bedrock_agentcore.yaml` must be `backend/` (the build context root), not `deploy/agentcore/` — otherwise CodeBuild fails with `"/agents": not found`.

**AgentCore-specific env vars** (supplement root CLAUDE.md table):

| Variable | Purpose |
|----------|---------|
| `AGENTCORE_AGENT` | Which agent to load (required in container) |
| `AGENTCORE_RUNTIME_URL` | Set by AgentCore post-deploy; used in agent card |
| `AGENTCORE_ENABLE_A2A_PEERS` | Set `false` to disable peer A2A tools on orchestrator |
| `AGENTCORE_DATABASE_USE_POSTGRES` | Attach Postgres MCP to database-agent runtime |
| `AGENTCORE_DATABASE_USE_MONGODB` | Attach MongoDB MCP to database-agent runtime |
| `AGENTCORE_WEBCRAWLER_WITH_POSTGRES` | Enable Postgres MCP on web-crawler-agent (default `true`) |
| `GITLAB_MCP_HTTP_URL` | Shared ECS GitLab MCP endpoint (`http://<dns>:8080/mcp`) for gitlab-agent/qa-agent |

**Ephemeral disk** — `developer-agent` and `architect-agent` file writes do not persist on AgentCore; use `ARTIFACT_STORE=s3` or GitLab for all durable artifacts.

**VPC** — `orchestrator-agent` needs VPC access (port 5432) to RDS for the SQL-apply step. Other agents run `PUBLIC` unless they use Postgres MCP directly.

**GitLab MCP — two separate ECR images:**

| Image tag | Purpose |
|-----------|---------|
| `bedrock-agentcore-gitlab_agent:latest` | gitlab-agent AgentCore runtime |
| `bedrock-agentcore-gitlab_agent:gitlab_mcp` | Shared HTTP MCP server on ECS; push via `scripts/push-gitlab-mcp-ecr.ps1` |

## Infrastructure (Terraform)

Deploys target-apps to ECS Fargate behind a shared ALB in `us-east-2`.

```
infrastructure/
├── bootstrap/                  # One-time S3 remote-state bucket (local state)
├── modules/target-app-ecs/     # Reusable: ECR + task def + service + ALB rule + SG
└── environments/dev/
    ├── _shared/                # ECS cluster + shared ALB + listener (one-time)
    ├── control-plane-auth/     # Cognito User Pool for control-plane UI login
    └── <app>/                  # Per-app root (devops-agent generates these in Phase B)
```

**State:** S3 bucket `sdlc-tfstate-061836593297-us-east-2` (KMS, S3-native locking — no DynamoDB table needed).

**Deploy a target-app:**
```powershell
cd backend
.\scripts\deploy-target-app.ps1 -Feature <app>           # build + push + apply + wait
.\scripts\deploy-target-app.ps1 -Feature <app> -PlanOnly # review only
.\scripts\deploy-target-app.ps1 -Feature <app> -Destroy  # tear down (keeps _shared)
```

Prereqs: `aws sso login --profile eks-admin-user` and Docker Desktop running.

**App shape signals:**

| Context signal | Module input |
|---|---|
| Has Streamlit UI | `enable_ui = true` → UI container is ALB target |
| API-only | `enable_ui = false` → FastAPI health: `/health` |
| Uses RDS | `db_secret_arn` + `db_security_group_id` |
| No DB | Both `null`; task runs with `SKIP_STARTUP_CHECKS=1` |

## Scripts

| Script | Purpose |
|--------|---------|
| `run-sdlc-local.ps1` | Full local pipeline (see root CLAUDE.md) |
| `deploy-agentcore-agents.ps1` | Deploy one or more AgentCore runtimes |
| `deploy-target-app.ps1` | Build + Terraform-apply a target-app to ECS |
| `deploy-frontend-ecs.ps1` | Push control-plane frontend to ECS |
| `deploy-gitlab-mcp-ecs.ps1` | Deploy shared GitLab MCP server to ECS |
| `sync-agentcore-dockerfiles.ps1` | Regenerate per-agent Dockerfiles from shared source |
| `push-frontend-ecr.ps1` | Build + push frontend ECR image |
| `push-gitlab-mcp-ecr.ps1` | Build + push GitLab MCP ECR image |
| `apply_sql_to_rds.py` | Standalone RDS SQL apply (also called by orchestrator) |
| `create-control-plane-user.ps1` | Create Cognito user for control-plane UI |
| `postgres_mcp_smoke.py` | Postgres MCP connect + query smoke test (not in pytest suite) |
| `check_rds_network.py` | RDS network reachability check |
| `fetch-cloudwatch-logs.py` | Dump ECS task CloudWatch logs to stdout |
| `invoke-orchestrator-smoke.py` | Smoke-invoke the orchestrator AgentCore runtime |
| `publish-template-to-s3.py` | Publish `target-apps/_template/` scaffold to S3 |
| `analyze_agent_timing.py` | Parse telemetry JSON to report per-agent durations |
| `PIPELINE.md` | Pipeline flag reference and preset definitions |

## Tests

> See root `CLAUDE.md — Tests` for how to run and the conftest isolation pattern.

**Coverage map** (`tests/`):

| Area | Files |
|------|-------|
| Pipeline orchestration + RDS apply | `test_sdlc_pipeline.py`, `test_apply_sql_to_rds.py` |
| Artifact store (local + S3) | `test_artifact_store.py`, `test_architect_agent_s3.py`, `test_database_agent_s3_write.py` |
| GitLab publish | `test_gitlab_agent.py`, `test_gitlab_mcp_actions.py`, `test_gitlab_mcp_client.py` |
| AgentCore deploy / invoke | `test_agentcore_deploy.py`, `test_agentcore_invoke.py`, `test_agentcore_dockerfile.py` |
| CloudWatch log parsing | `test_cloudwatch_logs.py` |
| DB schema validation | `test_validate_sql_artifacts.py`, `test_validate_conftest.py`, `test_database_agent_postgres_context.py` |
| UI / API parity | `test_pipeline_telemetry_ui.py` |
| Seed credentials | `test_seed_credentials.py`, `test_verify_seed_bcrypt.py`, `test_db_handoff_seed_credentials.py` |
| Agent modules | `test_developer_agent.py`, `test_qa_agent.py`, `test_web_crawler_agent.py` |
| Shared helpers | `test_pipeline_context.py`, `test_telemetry.py`, `test_async_pipeline.py`, `test_delivery_profile.py`, `test_diagram_tools.py` |

**Not in pytest suite** — use manual scripts:
- RDS connect/query: `scripts/postgres_mcp_smoke.py`
- RDS network: `scripts/check_rds_network.py`

**Conftest isolation** — sets `SDLC_SKIP_REPO_ENV=1` and stubs `load_repo_env()` so `.env.local` Postgres credentials never affect unit tests.

## Pipeline handoff files

`agents/pipeline/` holds per-run state for local runs (S3 stores the equivalent under `runs/<runId>/`):

| File pattern | Written by | Consumed by |
|---|---|---|
| `<app>.context.json` | orchestrator / product-agent | every downstream agent |
| `<app>.database-handoff.md` | host (after database-agent run) | developer-agent |
| `<app>.developer-handoff.json` | developer-agent | gitlab-agent, devops-agent |
| `<app>.gitlab-handoff.json` | gitlab-agent | devops-agent |
| `<app>.devops-handoff.json` | devops-agent | (terminal) |
| `<app>.qa-handoff.json` | qa-agent | (terminal) |
| `<app>.<agent>-telemetry.json` | each agent | `pipeline_telemetry.py` summary |
| `<app>.pipeline-telemetry.json` | orchestrator | frontend UI |

Handoff schema types live in `_shared/handoff_schemas.py`.
