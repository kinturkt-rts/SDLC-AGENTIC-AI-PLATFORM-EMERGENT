# GitLab MCP on ECS (HTTP) + CloudFront + AgentCore

Shared [jmrplens/gitlab-mcp-server](https://github.com/jmrplens/gitlab-mcp-server) in HTTP mode for **gitlab-agent**, **qa-agent**, Cursor, and AgentCore Gateway.

**Canonical URLs:** [`config/agentcore/gitlab-mcp-endpoints.json`](../../config/agentcore/gitlab-mcp-endpoints.json)

## Architecture

```
Apps-repo PUBLISH (gitlab-agent)
              │
              ▼
    Direct ALB HTTP  (GITLAB_MCP_HTTP_DIRECT_URL)  ← required
              │
              ▼
         ECS Fargate :8080/mcp  →  one gitlab_commit_create (all files)

IDE / qa reads
              │
              ▼
    CloudFront HTTPS  (GITLAB_MCP_URL)
              │
              ▼
         ALB HTTP  ──►  ECS Fargate :8080/mcp
```

| Client | Env var | URL |
|--------|---------|-----|
| **gitlab-agent publish** | `GITLAB_MCP_URL` + `GITLAB_MCP_HTTP_DIRECT_URL` | **ALB `/mcp` only** (both set to direct) |
| **IDE / qa reads** | `GITLAB_MCP_URL` | CloudFront HTTPS |
| **Emergency only** | `GITLAB_MCP_PUBLISH_ALLOW_CLOUDFRONT=true` | Allows CloudFront in publish candidate list |

## Sidekiq-safe publish (mandatory)

- `GITLAB_PUBLISH_SINGLE_COMMIT=true` (default): **one Git commit** per app = **one** Sidekiq `PostReceive`.
- Never publish via CloudFront for apps-repo: the old WAF path used one-file-per-commit and saturated org Sidekiq (~18–21s PostReceive × N files).
- `[skip ci]` does **not** stop `PostReceive` — only CI pipelines.

## CloudFront WAF

WAF is configured on the CloudFront distribution: `GenericLFI_BODY` is excluded for large MCP POST bodies on read paths. **Publish still must use ALB** — do not re-enable CloudFront publish.

## Deploy ECS + ALB

```powershell
.\scripts\deploy-gitlab-mcp-ecs.ps1
```

Update `gitlab-mcp-endpoints.json` if ALB DNS changes.

## Deploy gitlab-agent (AgentCore)

```powershell
.\scripts\deploy-agentcore-agents.ps1 -Agents gitlab_agent -SkipConfigure
```

Sets both MCP URLs to the ALB direct endpoint, plus `GITLAB_PUBLISH_SINGLE_COMMIT=true`.
