---
name: gitlab-agent
description: Publishes SDLC artifacts to GitLab via self-hosted MCP after developer-agent. Primary publish path for Juno GitLab.
---

# GitLab Agent

## Role

Runs **after developer-agent** when publishing to your **GitLab monorepo** (`origin` on `code.junodev.net`).
Uses **jmrplens/gitlab-mcp-server** in Cursor (GitLab Free via REST API v4).

- Branch per app: `sdlc/<app>` (reused per app; republish updates files)
- MR to `main` is opt-in (`--open-mr` on gitlab-agent CLI)
- Layout: monorepo paths (`target-apps/<app>/`, `docs/PRD/`, etc.)

## Runtime

| Item | Location |
|------|----------|
| CLI publish | `agents/gitlab-agent/gitlab_agent.py` → jmrplens MCP (`gitlab_commit_create`) |
| MCP (Cursor) | `scripts/gitlab_jmrplens_stdio.py` → `bin/gitlab-mcp-server.exe` |
| REST helpers | `agents/_shared/gitlab_api.py` (legacy/tests; publish uses MCP) |
| A2A port | 9110 |
| Handoff | `agents/pipeline/<app>.gitlab-handoff.json` |

## Env

```env
GITLAB_PERSONAL_ACCESS_TOKEN=glpat_...   # gitlab-agent CLI
GITLAB_TOKEN=glpat_...                   # jmrplens MCP (optional if PAT set — wrapper maps it)
GITLAB_URL=https://code.junodev.net
GITLAB_API_URL=https://code.junodev.net/api/v4
GITLAB_PROJECT_PATH=junolabs/sdlc-agentic-ai-platform/sdlc-agentic-ai-platform
GITLAB_BASE_BRANCH=main
```

Install MCP binary once: `.\scripts\install-jmrplens-gitlab-mcp.ps1`

## Pipeline

```powershell
.\scripts\run-sdlc.ps1 `
  -Feature training-compliance `
  -InputFile inputs\training-compliance.txt `
  -WithGitlab
```

## Standalone

```powershell
python agents/gitlab-agent/gitlab_agent.py --target-app training-compliance
```

## Not in scope

- GitHub showcase repo (use **github-agent** with `-WithGithub`)
- Terraform / ECS (devops-agent Phase 2)
