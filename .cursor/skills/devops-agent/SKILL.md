---
name: devops-agent
description: Phase 2 Terraform, CI/CD, ECS. GitLab publish via gitlab-agent.
---

# DevOps Agent

## Phase 1

**GitLab publish** (primary `origin`) is **gitlab-agent**.

```powershell
python agents/gitlab-agent/gitlab_agent.py --target-app <app>
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
