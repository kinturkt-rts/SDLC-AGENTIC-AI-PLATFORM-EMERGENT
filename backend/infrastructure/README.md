# Infrastructure (Terraform)

Deploys SDLC target-apps to **ECS Fargate** behind one **shared ALB** in `us-east-2`.
Each app is reachable at `http://<alb-dns>/<app-name>/`.

## Layout

```
infrastructure/
├── bootstrap/                     # One-time: S3 remote-state bucket (local state)
├── modules/
│   └── target-app-ecs/            # Reusable: ECR + task def (api [+ ui]) + service
│                                  #   + target group + ALB path rule + SG + logs
└── environments/
    └── dev/
        ├── _shared/               # One-time: ECS cluster + shared ALB + listener
        ├── control-plane-auth/    # Cognito User Pool for control-plane UI login
        └── <app>/                 # Per-app root calling the module
                                   #   (hello-fastapi is the hand-written example;
                                   #    devops-agent generates these in Phase B)
```

## Control-plane UI auth (Cognito)

Standalone from agents/pipeline. Users + password hashes live in Cognito only.

```powershell
cd backend/infrastructure/environments/dev/control-plane-auth
terraform init
terraform apply
terraform output frontend_env
# Set COGNITO_USER_POOL_ID / COGNITO_CLIENT_ID / COGNITO_REGION on the ECS task
# (see deploy/control-plane-frontend/task-definition.json), then:
cd ../../../../
.\scripts\create-control-plane-user.ps1 -Email you@company.com
```

Cost (dev): Cognito free tier (50k MAU) — typically $0 for internal demos.

## State

- Bucket: `sdlc-tfstate-061836593297-us-east-2` (versioned, KMS, S3-native locking — no DynamoDB)
- Keys: `dev/_shared/terraform.tfstate`, `dev/apps/<app>/terraform.tfstate`
- Per-app roots read `_shared` outputs via `terraform_remote_state`.

## Deploy an app

```powershell
cd backend
.\scripts\deploy-target-app.ps1 -Feature <app>              # build + push + apply + wait
.\scripts\deploy-target-app.ps1 -Feature <app> -PlanOnly    # review changes only
.\scripts\deploy-target-app.ps1 -Feature <app> -Destroy     # tear down (keeps _shared)
```

Prereqs: `aws sso login --profile eks-admin-user`, Docker Desktop running,
and a per-app root under `environments/dev/<app>/`.

## App shape → module inputs

| Pipeline context signal | Module input |
|---|---|
| App has Streamlit UI | `enable_ui = true` → UI container is the ALB target (`STREAMLIT_SERVER_BASE_URL_PATH=<app>`) |
| API-only app | `enable_ui = false` → FastAPI container is the ALB target (health: `/health`) |
| App uses RDS Postgres | `db_secret_arn` (Secrets Manager `DATABASE_URL`) + `db_security_group_id` (opens 5432 from task SG) |
| No DB | leave both `null` — task runs with `SKIP_STARTUP_CHECKS=1` |

## Costs (dev)

Shared: 1 ALB (~$16/mo). Per app: 1 Fargate task 0.5 vCPU / 1 GB (~$18/mo if left
running 24/7) + ECR storage. Destroy apps you are not demoing; `_shared` can also be
destroyed when nothing is deployed.

MCP-driven Terraform authoring (devops-agent, Phase B): see `config/mcp/servers.json` → `terraform`.
