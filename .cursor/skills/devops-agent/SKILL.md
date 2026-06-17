---
name: devops-agent
description: Manages CI/CD and Terraform-aligned infra via GitLab MCP. Use when working on devops-agent, pipelines, or infrastructure/.
---

# DevOps Agent

## What this agent does

Proposes CI/CD and infrastructure changes using GitLab MCP. Aligns with `infrastructure/` Terraform modules. Documents rollout steps.

## Runtime

| Item | Location |
|------|----------|
| Code | `agents/devops-agent/agent.py` → `_shared/runner.py` |
| System prompt | `DEVOPS_SYS_PROMPT` in `devops_agent.py` |
| A2A port | 9105 |

## MCP tools

- **GitLab**: `.cursor/mcp.json` → `gitlab` (`config/mcp/servers.json`)
- **Terraform** (optional): `config/mcp/servers.json` → `terraform`

## Env vars

`GITLAB_PERSONAL_ACCESS_TOKEN`, `GITLAB_API_URL` (see `.env`)

## Run standalone

```bash
python agents/devops-agent/agent.py --task "Add CI job for pytest on merge requests"
```