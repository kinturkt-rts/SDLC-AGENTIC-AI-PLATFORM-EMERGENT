# Control-plane frontend (Next.js on ECS)

Hosts the SDLC control-plane UI with live S3 / CloudWatch / AgentCore data via Next.js `/api/v1/*` routes.

## Hosted URLs

| Use | URL |
|-----|-----|
| **CloudFront (preferred)** | https://d14mr4f4z1bscv.cloudfront.net |
| Login | https://d14mr4f4z1bscv.cloudfront.net/login |
| Dashboard | https://d14mr4f4z1bscv.cloudfront.net/dashboard |
| **ALB (direct, HTTP)** | http://sdlc-control-plane-alb-804473930.us-east-2.elb.amazonaws.com |
| Health | `…/api/health` on either host |

CloudFront sits in front of the ALB. Use CloudFront for day-to-day access; use the ALB for debugging or bypassing CDN cache.

Login is UI-only for now (no Cognito yet) — `/dashboard` is still reachable directly without signing in.

## Redeploy (after frontend code changes)

**Prereqs:** Docker Desktop running, AWS SSO session active.

```powershell
aws sso login --profile "eks-admin-user"
cd backend
```

### Full redeploy (build + push + ECS)

```powershell
.\scripts\push-frontend-ecr.ps1
.\scripts\deploy-frontend-ecs.ps1
```

If `deploy-frontend-ecs.ps1` fails on duplicate security-group rules (infra already exists), force a rollout instead:

```powershell
aws ecs update-service `
  --cluster sdlc-agentic-ai `
  --service sdlc-control-plane `
  --force-new-deployment `
  --region us-east-2 `
  --profile "eks-admin-user"
```

### Faster image-only redeploy (typical for UI tweaks)

```powershell
.\scripts\push-frontend-ecr.ps1
```

The script verifies the existing ECR repo (`061836593297.dkr.ecr.us-east-2.amazonaws.com/sdlc-control-plane`) — it does not create one.

```powershell
aws ecs update-service `
  --cluster sdlc-agentic-ai `
  --service sdlc-control-plane `
  --force-new-deployment `
  --region us-east-2 `
  --profile "eks-admin-user"
```

Push only (skip rebuild if image already built locally):

```powershell
.\scripts\push-frontend-ecr.ps1 -SkipBuild
# then force-new-deployment as above
```

### Verify rollout

```powershell
aws ecs describe-services `
  --cluster sdlc-agentic-ai `
  --services sdlc-control-plane `
  --region us-east-2 `
  --profile "eks-admin-user" `
  --query "services[0].deployments"

Invoke-WebRequest -Uri "http://sdlc-control-plane-alb-804473930.us-east-2.elb.amazonaws.com/api/health" -UseBasicParsing
```

Wait until the primary deployment shows `rolloutState: COMPLETED` and `/login` returns 200.

### AWS resources (reference)

| Item | Value |
|------|-------|
| Account | `061836593297` |
| Region | `us-east-2` |
| Profile | `eks-admin-user` |
| ECR image | `061836593297.dkr.ecr.us-east-2.amazonaws.com/sdlc-control-plane:latest` |
| ECS cluster | `sdlc-agentic-ai` |
| ECS service | `sdlc-control-plane` |
| Task family | `sdlc-control-plane` |
| ALB | `sdlc-control-plane-alb` |

Preview deploy without changes: `.\scripts\deploy-frontend-ecs.ps1 -WhatIf`

## Local dev (before deploy)

```powershell
cd frontend
npm run dev
```

Open http://localhost:3000/login

## What the container needs

| Requirement | Notes |
|-------------|--------|
| **IAM task role** | `sdlc-control-plane-task` — S3 artifact bucket, CloudWatch Logs, `bedrock-agentcore:InvokeAgentRuntime` |
| **Env vars** | `ARTIFACT_STORE=s3`, `ARTIFACT_S3_BUCKET`, `AWS_REGION`, `GITLAB_URL` — set in ECS task definition (not in image) |
| **Secrets** | `GITLAB_PERSONAL_ACCESS_TOKEN` from Secrets Manager `sdlc/control-plane/gitlab-pat` (synced from `.env.local` by `deploy-frontend-ecs.ps1`) — used to mark Deploy failed when apps-repo CI fails |
| **Transport** | `SDLC_PIPELINE_TRANSPORT=a2a` (default in Dockerfile) |

Do **not** bake `.env` or `.env.local` into the image.

## Local Docker smoke

From monorepo root (after `aws sso login`):

```powershell
docker build -f frontend/Dockerfile -t sdlc-control-plane:local .
docker run --rm -p 3000:3000 `
  -e ARTIFACT_STORE=s3 `
  -e ARTIFACT_S3_BUCKET=sdlc-agentic-ai-app-artifacts `
  -e AWS_REGION=us-east-2 `
  -e AWS_PROFILE="eks-admin-user" `
  -v "$env:USERPROFILE\.aws:/root/.aws:ro" `
  sdlc-control-plane:local
```

## Architecture

```
Browser → CloudFront → ALB → ECS (Next.js standalone)
                                  ├─ S3 artifact store (runs/*)
                                  ├─ CloudWatch Logs
                                  └─ Bedrock AgentCore invoke (orchestrator)
```
