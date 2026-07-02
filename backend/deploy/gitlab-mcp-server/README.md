# GitLab MCP on ECS (HTTP) + CloudFront + AgentCore

Shared [jmrplens/gitlab-mcp-server](https://github.com/jmrplens/gitlab-mcp-server) in HTTP mode for **gitlab-agent**, **qa-agent**, Cursor, and AgentCore Gateway.

**Canonical URLs:** [`config/agentcore/gitlab-mcp-endpoints.json`](../../config/agentcore/gitlab-mcp-endpoints.json)

## Architecture

```
gitlab-agent / qa-agent / Cursor / Gateway
              │
              ▼
    CloudFront HTTPS  (GITLAB_MCP_URL)  ← canonical
              │
              ▼
         ALB HTTP  ──►  ECS Fargate :8080/mcp
```

| Client | Env var | URL |
|--------|---------|-----|
| **All agents + IDE** (primary) | `GITLAB_MCP_URL` | `https://d1cvmpnnohwpj8.cloudfront.net/mcp` |
| **Fallback** (403 from CloudFront) | `GITLAB_MCP_HTTP_DIRECT_URL` | ALB `/mcp` |

## CloudFront WAF

WAF is configured on the CloudFront distribution: `GenericLFI_BODY` is excluded so MCP publish POST bodies are not blocked. If you recreate the distribution, exclude that rule on Web ACL `CreatedByCloudFront-0a676d76` or rely on `GITLAB_MCP_HTTP_DIRECT_URL` (ALB fallback; gitlab-agent retries automatically on 403).

## Deploy ECS + ALB

```powershell
.\scripts\deploy-gitlab-mcp-ecs.ps1
```

Update `gitlab-mcp-endpoints.json` if ALB DNS changes.

## Deploy gitlab-agent (AgentCore)

```powershell
.\scripts\deploy-agentcore-agents.ps1 -Agents gitlab_agent -SkipConfigure
```

Sets `GITLAB_MCP_URL` (CloudFront) and optional `GITLAB_MCP_HTTP_DIRECT_URL` (ALB fallback) from config.

## Verify CloudFront publish

```powershell
.\.venv\Scripts\python.exe agents/gitlab-agent/gitlab_agent.py `
  --target-app gitlab-pipeline-smoke `
  --context-file agents/pipeline/gitlab-pipeline-smoke.context.json
```

Uses CloudFront first; retries via ALB if WAF returns 403.
