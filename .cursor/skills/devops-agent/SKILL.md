---
name: devops-agent
description: Phase 2 Terraform, CI/CD, ECS. GitLab/GitHub publish via gitlab-agent and github-agent.
---

# DevOps Agent

## Phase 1

**GitHub publish** is handled by **github-agent**. **GitLab publish** (primary `origin`) is **gitlab-agent**.

```powershell
python agents/gitlab-agent/gitlab_agent.py --target-app <app>
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
