---
name: github-agent
description: Publishes SDLC artifacts to GitHub showcase repo via MCP after developer-agent. Phase 1 MVP publish step.
---

# GitHub Agent

## Role

Runs **after developer-agent** in Phase 1 MVP. Pushes generated apps to
[kinturkt-rts/SDLC-Agentic-AI-Platform](https://github.com/kinturkt-rts/SDLC-Agentic-AI-Platform)
using **GitHub MCP** (`push_files`, `create_pull_request`).

- One **branch per app** (e.g. `training-compliance`)
- PR into `main`
- Layout: `<app>/`, `docs/PRD/`, `docs/design/`, `agents/pipeline/`

## Runtime

| Item | Location |
|------|----------|
| Code | `agents/github-agent/github_agent.py` |
| MCP publish | `agents/_shared/github_mcp_publish.py` |
| Path helpers | `agents/_shared/github_publish.py` |
| A2A port | 9107 |
| Handoff | `agents/pipeline/<app>.github-handoff.json` |

## Env

```env
GITHUB_PERSONAL_ACCESS_TOKEN=ghp_...
GITHUB_OWNER=kinturkt-rts
GITHUB_REPO=SDLC-Agentic-AI-Platform
GITHUB_BASE_BRANCH=main
```

Uses `@modelcontextprotocol/server-github` via stdio (same as Cursor GitHub MCP).

## Pipeline

```powershell
.\scripts\run-sdlc.ps1 `
  -Feature training-compliance `
  -InputFile inputs\training-compliance.txt `
  -WithGithub
```

## Standalone

```powershell
python agents/github-agent/github_agent.py --target-app training-compliance
```

## Not in scope

- Git push to GitLab `origin` (use devops/git only if needed locally)
- Terraform / ECS (devops-agent Phase 2)
- pytest (qa-agent Phase 3)
