# AgentCore Runtime deployment (A2A)

Deploy SDLC specialist agents to [Amazon Bedrock AgentCore Runtime](https://docs.aws.amazon.com/bedrock-agentcore/) using the **A2A protocol** on port **9000** (`linux/arm64`).

**You do not need a separate `a2a_server.py` per agent.** Agent logic stays in `agents/<name>/*_agent.py`. This folder adds a **single** AgentCore adapter plus one shared Dockerfile and requirements file.

## Why this folder exists (vs `*_agent.py`)

| | Local dev (`agents/*_agent.py`) | AgentCore (`deploy/agentcore/`) |
|---|--------------------------------|----------------------------------|
| Command | `python agents/architect-agent/architect_agent.py --serve-a2a` | `AGENTCORE_AGENT=architect-agent python deploy/agentcore/a2a_server.py` |
| Port | `9102` (per `a2a/agent-registry.json`) | **`9000`** (AgentCore requirement) |
| Server | `A2AServer(...).serve()` | FastAPI + `serve_at_root=True` + `/ping` |
| URL | `127.0.0.1` | `0.0.0.0` + `AGENTCORE_RUNTIME_URL` for agent card |

`agentcore_runtime/bundles.py` imports your existing `_build_agent`, MCP clients, and skills from `*_agent.py` — it does **not** duplicate agent prompts or tools.

## Layout

```
deploy/agentcore/
├── README.md
├── a2a_server.py              # ONE entrypoint — pick agent via env/CLI
├── requirements.txt           # ONE file for all agents
├── Dockerfile                 # ONE shared ARM64 image
├── .dockerignore
└── agentcore_runtime/
    ├── bootstrap.py           # repo paths + .env
    ├── bundles.py             # wires each *_agent.py for AgentCore
    ├── serve.py               # uvicorn on :9000
    └── requirements-base.txt
```

## Quick start (local)

From **repository root**:

```powershell
pip install -r deploy/agentcore/requirements.txt
$env:AGENTCORE_AGENT = "architect-agent"
python deploy/agentcore/a2a_server.py
```

Or:

```powershell
python deploy/agentcore/a2a_server.py --agent architect-agent
```

```powershell
curl http://localhost:9000/ping
curl http://localhost:9000/.well-known/agent-card.json
```

## Deploy with AgentCore CLI

Install once:

```powershell
pip install bedrock-agentcore-starter-toolkit
```

### Do you need Docker?

| Question | Answer |
|----------|--------|
| Does AgentCore run agents in containers? | **Yes** — every AgentCore Runtime is a container on AWS (ARM64). |
| Do **you** need Docker on your laptop? | **No**, for the default path: `agentcore deploy` builds the image in **AWS CodeBuild**. |
| When is local Docker needed? | Only for `agentcore deploy --local`, `--local-build`, or manual `docker buildx` + ECR push. |
| Do you need a Dockerfile in the repo? | **Yes** for this monorepo — `deploy/agentcore/Dockerfile` bundles `agents/`, MCP helpers, and the entrypoint. |

**Recommended for this project:** `--deployment-type container` (not `direct_code_deploy`), because agents import from `agents/` and spawn MCP subprocesses (`uv`, `npx`).

### Prerequisites (once)

1. AWS CLI credentials with permission to create AgentCore runtimes, ECR, IAM roles.
2. Bedrock model access enabled in your region (e.g. `us-east-2`).
3. Repo `.env` values ready to pass as runtime env vars (never commit secrets).

### Deploy one agent (copy-paste)

From **repository root**. Replace region/name as needed.

```powershell
# 1. Toolkit + Python deps (local test optional)
pip install bedrock-agentcore-starter-toolkit
pip install -r deploy/agentcore/requirements.txt

# 2. Configure runtime (once per agent)
agentcore configure `
  --entrypoint deploy/agentcore/a2a_server.py `
  --requirements-file deploy/agentcore/requirements.txt `
  --protocol A2A `
  --deployment-type container `
  --name architect-agent `
  --region us-east-2 `
  --disable-memory `
  --non-interactive

# 3. Deploy (CodeBuild creates ARM64 image — no local Docker)
agentcore deploy --agent architect-agent `
  --env AGENTCORE_AGENT=architect-agent `
  --env AWS_REGION=us-east-2 `
  --env MODEL_ID=us.anthropic.claude-sonnet-4-20250514-v1:0
```

After deploy you get a **runtime ARN**. Agents run on **Amazon Bedrock AgentCore** (managed HTTP A2A on port 9000 behind AWS auth).

### Deploy all 9 agents

Same entrypoint and requirements every time — only `--name`, `AGENTCORE_AGENT`, and extra env vars change:

```powershell
$agents = @(
  @{ name = "orchestrator-agent"; node = $false },
  @{ name = "product-agent";      node = $true  },
  @{ name = "architect-agent";     node = $false },
  @{ name = "developer-agent";     node = $false },
  @{ name = "qa-agent";            node = $false },
  @{ name = "devops-agent";        node = $true  },
  @{ name = "security-agent";      node = $false },
  @{ name = "database-agent";      node = $false },
  @{ name = "web-crawler-agent";   node = $true  }
)

foreach ($a in $agents) {
  agentcore configure `
    --entrypoint deploy/agentcore/a2a_server.py `
    --requirements-file deploy/agentcore/requirements.txt `
    --protocol A2A `
    --deployment-type container `
    --name $a.name `
    --region us-east-2 `
    --disable-memory `
    --non-interactive

  agentcore deploy --agent $a.name --env AGENTCORE_AGENT=$($a.name)
}
```

Add MCP secrets per agent on the `deploy` line, e.g. `--env FIRECRAWL_API_KEY=...` for web-crawler, `--env GITLAB_PERSONAL_ACCESS_TOKEN=...` for devops.

## Docker (ARM64) — optional local build

One Dockerfile; set which agent at build time:

```powershell
docker buildx build --platform linux/arm64 `
  -f deploy/agentcore/Dockerfile `
  --build-arg AGENTCORE_AGENT=architect-agent `
  --build-arg INSTALL_NODE=false `
  -t sdlc-architect-agent:latest .
```

| Agent | `AGENTCORE_AGENT` | `INSTALL_NODE` |
|-------|-------------------|----------------|
| orchestrator-agent | `orchestrator-agent` | false |
| product-agent | `product-agent` | **true** (Atlassian `npx`) |
| architect-agent | `architect-agent` | false (`uv` in requirements) |
| developer-agent | `developer-agent` | false |
| qa-agent | `qa-agent` | false |
| devops-agent | `devops-agent` | **true** (GitLab `npx`) |
| security-agent | `security-agent` | false |
| database-agent | `database-agent` | false |
| web-crawler-agent | `web-crawler-agent` | **true** (Firecrawl `npx`) |

You still create **one AgentCore runtime per agent** in AWS (separate scaling/IAM/MCP config). You do **not** need one Dockerfile or entrypoint file per agent.

## Environment variables

| Variable | Purpose |
|----------|---------|
| `AGENTCORE_AGENT` | Which agent to run (required) |
| `AWS_REGION`, `MODEL_ID` | Bedrock |
| `AGENTCORE_RUNTIME_URL` | Set by AgentCore after deploy (agent card) |
| `AGENTCORE_DATABASE_USE_POSTGRES` | database-agent: attach Postgres MCP |
| `AGENTCORE_DATABASE_USE_MONGODB` | database-agent: attach MongoDB MCP |
| `AGENTCORE_WEBCRAWLER_WITH_POSTGRES` | web-crawler-agent (default true) |
| `AGENTCORE_A2A_PEER_URLS` | orchestrator: deployed peer runtime URLs |
| `AGENTCORE_ENABLE_A2A_PEERS` | orchestrator: set `false` to disable peer tools |

See `agents/README.md` for MCP credentials (`ATLASSIAN_*`, `GITLAB_*`, `FIRECRAWL_*`, `POSTGRES_MCP_*`, etc.).

## Operational notes

- **Ephemeral disk** — `developer-agent` / `architect-agent` file writes do not persist; use S3, EFS, or git for artifacts.
- **VPC** — use `--vpc` on `agentcore configure` for private RDS (Postgres MCP).
- **Auth** — production endpoints need OAuth or SigV4 ([A2A deploy guide](https://aws.github.io/bedrock-agentcore-starter-toolkit/user-guide/runtime/a2a.md)).

## Adding a new agent

1. Implement `agents/<name>/*_agent.py` with `serve_a2a()` (local dev).
2. Add a bundle factory in `agentcore_runtime/bundles.py` and register in `BUNDLE_FACTORIES`.
3. Register local A2A port in `a2a/agent-registry.json`.
4. Deploy with `AGENTCORE_AGENT=<name>` — no new entrypoint file needed.

## Related

- `agents/README.md` — local CLI and `--serve-a2a`
- `agents/_shared/agentcore_serve.py` — FastAPI + `A2AServer` wrapper
