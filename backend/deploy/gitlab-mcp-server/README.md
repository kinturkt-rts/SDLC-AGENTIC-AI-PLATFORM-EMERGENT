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
| **Fallback** (403 before WAF fix) | `GITLAB_MCP_HTTP_DIRECT_URL` | ALB `/mcp` |

## One-time WAF fix (required for CloudFront publish)

CloudFront ships with managed WAF. `GenericLFI_BODY` blocks MCP publish POST bodies (e.g. `http://localhost` in README).

```powershell
cd backend
aws sso login --profile "Juno Developers"
.\scripts\update-gitlab-mcp-waf.ps1
```

This scopes `AWSManagedRulesCommonRuleSet` away from URI `/mcp` only. IP reputation and known-bad-inputs rules still apply.

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
