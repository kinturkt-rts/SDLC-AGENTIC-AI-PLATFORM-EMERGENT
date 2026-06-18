---
name: devops-agent
description: Publishes SDLC artifacts to GitHub (git branch + PR) via devops-agent. Use for pipeline publish steps or CI/CD planning.
---

# DevOps Agent

## What this agent does

Mirrors a **developer pushing a feature branch** after codegen:

1. Collects pipeline artifacts (`target-apps/<app>/`, PRD, design, handoffs)
2. Commits on `sdlc/<app>` and pushes to `origin` (monorepo)
3. Opens a GitHub pull request (`gh` CLI or GitHub MCP)
4. Writes `agents/pipeline/<app>.devops-handoff.json` for **qa-agent**

## Real SDLC mirror

| Human role | Agent | Action |
|------------|-------|--------|
| Developer | developer-agent | Writes code + baseline tests |
| Developer | devops-agent | `git push` + open PR |
| QA | qa-agent | Run pytest locally + comment on PR |

QA tests the **local checkout** (same bytes as the branch). GitHub holds the review surface.

## Runtime

| Item | Location |
|------|----------|
| Code | `agents/devops-agent/devops_agent.py` |
| Git helpers | `agents/_shared/github_publish.py` |
| A2A port | 9105 |

## Env vars

| Variable | Purpose |
|----------|---------|
| `GITHUB_PERSONAL_ACCESS_TOKEN` | GitHub MCP + optional `GH_TOKEN` |
| `GITHUB_OWNER` | Org or user |
| `GITHUB_REPO` | Repository name |
| `GITHUB_BASE_BRANCH` | PR target (default `main`) |

Also: `gh auth login` for `devops_create_pull_request` via CLI.

## Pipeline

```powershell
.\scripts\run-sdlc.ps1 `
  -Feature meeting-action-tracker `
  -InputFile inputs\meeting-action-tracker.txt `
  -WithGithub `
  -GithubOwner your-org `
  -GithubRepo your-monorepo
```

## Run standalone

```bash
python agents/devops-agent/devops_agent.py --target-app meeting-action-tracker
```
