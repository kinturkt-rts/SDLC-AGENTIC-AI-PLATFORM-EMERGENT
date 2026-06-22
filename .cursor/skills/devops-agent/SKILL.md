---
name: devops-agent
description: Phase 2 Terraform, CI/CD, ECS. GitHub publish is github-agent (Phase 1).
---

# DevOps Agent

## Phase 1

**GitHub publish** is handled by **github-agent** — not this agent.

```powershell
python agents/github-agent/github_agent.py --target-app <app>
```

## Phase 2 (planned)

- Terraform under `infrastructure/`
- CI/CD pipelines
- ECS deploy for target-apps
- AWS Secrets Manager
- Deploy notifications

## Runtime

| Item | Location |
|------|----------|
| Code | `agents/devops-agent/devops_agent.py` |
| A2A port | 9105 |
