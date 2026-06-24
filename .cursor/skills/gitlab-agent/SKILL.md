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
| CLI publish | `agents/gitlab-agent/gitlab_agent.py` → `gitlab_mcp_actions.publish_feature` |
| MCP client | `agents/_shared/gitlab_mcp_client.py` |
| MCP server | `scripts/gitlab_mcp_server.py` → `bin/gitlab-mcp-server.exe` |
| MCP actions | `agents/_shared/gitlab_mcp_actions.py` (env, publish, MR notes) |
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
# Publish
python agents/gitlab-agent/gitlab_agent.py --target-app training-compliance

# List projects
python agents/gitlab-agent/gitlab_agent.py --list-projects

# List files on a branch
python agents/gitlab-agent/gitlab_agent.py --list-branch-files sdlc/training-compliance

# List MR comments
python agents/gitlab-agent/gitlab_agent.py --list-mr-notes 3

# Post MR comment
python agents/gitlab-agent/gitlab_agent.py --mr-comment 3 --comment-body "QA passed"
```

## MCP tools used

| Operation | jmrplens tool |
|-----------|----------------|
| List projects | `gitlab_project_list` |
| List branch files | `gitlab_repository_tree` |
| List MR comments | `gitlab_mr_notes_list` |
| Post MR comment | `gitlab_mr_note_create` |

`qa-agent` posts QA summaries via `gitlab_mr_note_create` when `mergeRequestIid` is in `gitlab-handoff.json`.

## Not in scope

- Terraform / ECS (devops-agent Phase 2)
