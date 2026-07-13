---
name: devops-agent
description: Generates per-app Terraform deploy roots (ECS Fargate + shared ALB) and deploys target-apps to AWS. GitLab publish stays with gitlab-agent.
---

# DevOps Agent

Runs **after gitlab-agent**. Derives a deploy manifest from `target-apps/<app>/` +
pipeline context, authors `infrastructure/environments/dev/<app>/main.tf` (calling
`modules/target-app-ecs`), validates it, and optionally deploys via the
deterministic script. Apps go live at `http://<shared-alb>/<app>/`.

```powershell
# Generate + validate the TF root only
python agents/devops-agent/devops_agent.py --target-app <app>

# Generate + validate + build/push images + terraform apply + wait (live URL at end)
python agents/devops-agent/devops_agent.py --target-app <app> --deploy

# Plan without changing AWS / tear down
python agents/devops-agent/devops_agent.py --target-app <app> --plan-only
python agents/devops-agent/devops_agent.py --target-app <app> --destroy
```

## How app shape is derived (`_shared/deploy_manifest.py`)

| Signal | Effect |
|--------|--------|
| `ui/streamlit_app.py` exists (or deliveryProfile.requiresStreamlit) | `enable_ui = true`, UI container is ALB target |
| `db/sql/*.sql` exists | Secrets Manager `DATABASE_URL` secret + RDS SG rule (needs `POSTGRES_MCP_*` env) |
| `<app>.gitlab-handoff.json` | branch/project recorded in devops-handoff for traceability |

## Guardrails

- Agent writes **only** `infrastructure/environments/dev/<app>/*.tf`; never modules/_shared.
- `terraform apply` is owned by `scripts/deploy-target-app.ps1`, never the LLM.
- Terraform MCP (`hashicorp/terraform-mcp-server` via Docker) provides provider docs;
  degrades gracefully to the built-in template if Docker is down.
- Publish to GitLab = gitlab-agent (`python agents/gitlab-agent/gitlab_agent.py --target-app <app>`).

## Runtime

| Item | Location |
|------|----------|
| Code | `agents/devops-agent/devops_agent.py` |
| Deploy script | `scripts/deploy-target-app.ps1` |
| Infra | `infrastructure/` (see its README) |
| Handoff | `agents/pipeline/<app>.devops-handoff.json` (includes `appUrl`) |
| A2A port | 9105 |
