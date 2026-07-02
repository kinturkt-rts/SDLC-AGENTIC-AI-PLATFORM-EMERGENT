# GitLab MCP on ECS (HTTP) + CloudFront + AgentCore

Shared [jmrplens/gitlab-mcp-server](https://github.com/jmrplens/gitlab-mcp-server) in HTTP mode for **gitlab-agent** and **qa-agent** on AgentCore. Cursor local dev can use stdio (`backend/scripts/gitlab_mcp_server.py`) or CloudFront for read-only MCP.

**Canonical platform URLs** (no secrets): [`config/agentcore/gitlab-mcp-endpoints.json`](../../config/agentcore/gitlab-mcp-endpoints.json)

## Architecture

```
Pipeline (A2A)  orchestrator-agent ──► gitlab-agent (AgentCore)
                                              │
                                              ▼
                         GITLAB_MCP_HTTP_DIRECT_URL (ALB, no WAF)
                                              │
                                              ▼
                                    ECS Fargate :8080/mcp

Cursor IDE / Gateway  ──►  CloudFront (HTTPS + WAF)  ──►  ALB  ──►  ECS
                              read OK; publish often 403 (GenericLFI_BODY)
```

| Client | MCP URL env | Endpoint |
|--------|-------------|----------|
| **gitlab-agent publish** (AgentCore, pipeline) | `GITLAB_MCP_HTTP_DIRECT_URL` | ALB `/mcp` |
| **qa-agent** GitLab tools | `GITLAB_MCP_HTTP_DIRECT_URL` | ALB `/mcp` |
| **Cursor IDE** (optional HTTP) | `GITLAB_MCP_URL` | CloudFront `/mcp` |
| **AgentCore Gateway** | CloudFront `/mcp` | HTTPS front door |

## ECR image (canonical)

```
061836593297.dkr.ecr.us-east-2.amazonaws.com/bedrock-agentcore-gitlab_agent:gitlab_mcp
```

Push / rebuild:

```powershell
cd backend
.\scripts\push-gitlab-mcp-ecr.ps1 -BuildFromDockerfile
```

## Step 1 — ECS + ALB (scripted)

```powershell
cd backend
aws sso login --profile "Juno Developers"
.\scripts\deploy-gitlab-mcp-ecs.ps1
```

Creates (if missing):

| Resource | Name |
|----------|------|
| ECS cluster | `sdlc-agentic-ai` |
| ECS service | `gitlab-mcp-server` |
| ALB | `gitlab-mcp-alb` |
| Target group | `gitlab-mcp-tg` (IP, port 8080) |

After deploy, update `config/agentcore/gitlab-mcp-endpoints.json` if the ALB DNS name changed.

## Step 2 — CloudFront distribution (console)

1. Origin: ALB `gitlab-mcp-alb` (HTTP only)
2. Cache: **CachingDisabled**; origin request: **AllViewer**
3. Note domain → update `gitlab-mcp-endpoints.json` → `cloudFront.domain` / `cloudFront.mcpUrl`

## Step 3 — AgentCore gitlab-agent (pipeline publish)

Deploy reads `gitlab-mcp-endpoints.json` and sets `GITLAB_MCP_HTTP_DIRECT_URL` on the runtime:

```powershell
.\scripts\deploy-agentcore-agents.ps1 -Agents gitlab_agent -SkipConfigure
```

Optional overrides in `backend/.env.local` (secrets only — URLs come from config by default):

```env
GITLAB_PERSONAL_ACCESS_TOKEN=glpat_...
GITLAB_URL=https://code.junodev.net
GITLAB_PROJECT_PATH=junolabs/sdlc-agentic-ai-platform/sdlc-agentic-ai-platform-apps
```

`gitlab_mcp_client.py` prefers `GITLAB_MCP_HTTP_DIRECT_URL` over `GITLAB_MCP_URL`.

## Step 4 — Verify publish (AgentCore path)

```powershell
.\.venv\Scripts\python.exe agents/gitlab-agent/gitlab_agent.py `
  --target-app gitlab-pipeline-smoke `
  --context-file agents/pipeline/gitlab-pipeline-smoke.context.json
```

Expect `## status` → `published`. Uses direct ALB from config / `.env.local`.

## WAF note

CloudFront distribution has managed WAF (`GenericLFI_BODY` blocks POST bodies with `http://localhost` etc.). **Do not** point gitlab-agent publish at CloudFront only — use `directMcpUrl` in `gitlab-mcp-endpoints.json`.
