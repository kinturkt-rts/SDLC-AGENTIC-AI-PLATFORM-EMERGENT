# GitLab MCP on ECS (HTTP) + CloudFront + AgentCore

Shared [jmrplens/gitlab-mcp-server](https://github.com/jmrplens/gitlab-mcp-server) in HTTP mode for **gitlab-agent** and **qa-agent** on AgentCore. Cursor local dev still uses stdio (`backend/scripts/gitlab_mcp_server.py`).

## Architecture

```
AgentCore gitlab-agent  ──►  CloudFront (HTTPS)  ──►  ALB (HTTP)  ──►  ECS Fargate :8080/mcp
Cursor (local dev)      ──►  stdio binary (not CloudFront)
```

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
| Task SG | `mcp-allow-sg-group` |
| ALB SG | `mcp-alb-sg-1` |
| Service SG | `mcp-sg-allow-8080` |

VPC: default `vpc-036155f359e2e940c`, public subnets `us-east-2a/b/c`.

Wait until the ECS task is **healthy** in the target group before CloudFront.

## Step 2 — CloudFront distribution (console)

Match teammate setup:

1. **Create distribution**
   - **Origin type:** Elastic Load Balancer → select `gitlab-mcp-alb`
   - **Origin protocol:** HTTP only (SSL termination at CloudFront)
2. **Behaviors**
   - Cache policy: **CachingDisabled**
   - Origin request policy: **AllViewer** (forward auth headers)
   - Optional: response headers policy for CORS if browser clients need it
3. **Viewer**
   - Redirect HTTP → HTTPS
4. Note the distribution domain, e.g. `d1234abcd.cloudfront.net`

Smoke test (expect MCP protocol response, not HTML):

```powershell
curl -I "https://<cloudfront-domain>/mcp"
```

## Step 3 — AgentCore Gateway

1. Add MCP target: `https://<cloudfront-domain>/mcp`
2. Update gateway IAM role with the **gateway resource ARN**
3. Deploy / update **gitlab-agent** runtime with gateway URL
4. After runtime deploy, add gateway resource ARN to the role again if required

## Step 4 — Agent runtime env

In `backend/.env.local`:

```env
GITLAB_MCP_HTTP_URL=https://<cloudfront-domain>/mcp
GITLAB_PERSONAL_ACCESS_TOKEN=glpat_...
GITLAB_URL=https://code.junodev.net
```

Redeploy:

```powershell
.\scripts\deploy-agentcore-agents.ps1 -Agents gitlab_agent -SkipConfigure
```

`gitlab_mcp_client.py` sends `PRIVATE-TOKEN` and `GITLAB-URL` on each HTTP request (token not baked into the MCP container image).

## Step 5 — Verify

```powershell
$env:GITLAB_MCP_HTTP_URL="https://<cloudfront-domain>/mcp"
.\.venv\Scripts\python.exe -c "
import asyncio, sys
sys.path.insert(0, 'agents')
from _shared.env import load_repo_env
load_repo_env()
from _shared.gitlab_mcp_client import gitlab_mcp_session, call_gitlab_mcp_tool

async def main():
    async with gitlab_mcp_session() as s:
        d = await call_gitlab_mcp_tool(s, 'gitlab_project_list', {'per_page': 2})
        print('OK', d.get('projects', [])[:2])

asyncio.run(main())
"
```

## Not in `.cursor/mcp.json`

CloudFront URL is for **AWS agents** (`GITLAB_MCP_HTTP_URL`), not Cursor IDE. Keep Cursor on local stdio unless you intentionally switch to remote HTTP MCP.
