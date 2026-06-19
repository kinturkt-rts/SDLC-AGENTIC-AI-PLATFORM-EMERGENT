"""DevOps agent — Strands + Bedrock + scoped infra tools + A2A.

Generates deployable artifacts for target-apps/<service>/:
  - Dockerfile (multi-stage, slim Python base)
  - .dockerignore
  - .gitlab-ci.yml (lint → test → build → deploy stages with security gate)
  - infrastructure/<service>/main.tf  (Terraform — ECS Fargate skeleton)
  - DEPLOYMENT.md  (runbook the user can hand to a deploy engineer)

Reads upstream handoffs (developer, qa, security) and enforces a quality gate:
the agent refuses to produce deploy artifacts when security-handoff status is
`fail` unless `--force` is passed. Same shape as security-agent: scoped file
tools, structured handoff JSON, prompt caching, per-run telemetry.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TARGET_APPS = _REPO_ROOT / "target-apps"
_INFRA_DIR = _REPO_ROOT / "infrastructure"

sys.path.insert(0, str(_REPO_ROOT / "agents"))
from _shared.context_cli import load_context_extra, parse_context_args
from _shared.env import load_repo_env
from _shared.handoff_schemas import (
    DeveloperHandoff,
    HandoffValidationError,
    SecurityHandoff,
    load_handoff,
    write_handoff,
)
from _shared.pipeline_context import (
    TargetAppRequiredError,
    enrich_handoff_context,
    resolve_cli_context,
    resolve_design_doc_path,
    slugify,
)
from _shared.telemetry import RunTelemetry, usage_from_event

load_repo_env()
os.environ.setdefault("BYPASS_TOOL_CONSENT", "true")

import botocore.config
from a2a.types import AgentSkill
from strands import Agent
from strands.models import BedrockModel
from strands.models.model import CacheConfig
from strands.multiagent.a2a import A2AServer
from strands.tools.decorator import tool

AGENT_NAME = "devops-agent"
A2A_PORT = 9105

DEFAULT_PIPELINE_TASK = """\
Produce deployable infrastructure artifacts for targetApp using upstream handoff context.

**Step 1 — orient (read before writing)**
1a. devops_list_tree(targetApp) — inventory existing files; never overwrite Dockerfile, .gitlab-ci.yml,
    or infrastructure/<app>/main.tf if they already exist unless the user task says so.
1b. devops_read_file(developerHandoffPath) — port, env vars, run command, container entrypoint.
1c. devops_read_file(securityHandoffPath) when set — confirm status is `pass`. If `fail`,
    STOP and report blocking findings; do not write deploy artifacts unless `forceDeploy` is true.
1d. devops_read_file(qaHandoffPath) when set — note testCommand for the CI test stage.
1e. devops_read_file(designDocPath) — health endpoint, AWS region, any infra-specific rules.

**Step 2 — generate artifacts (in this order)**
2a. devops_write_dockerfile(targetApp) — multi-stage Dockerfile from upstream handoff.
2b. devops_write_dockerignore(targetApp) — standard Python/FastAPI .dockerignore.
2c. devops_write_gitlab_ci(targetApp) — .gitlab-ci.yml with lint → test → security-scan → build → deploy stages.
2d. devops_write_terraform(targetApp) — infrastructure/<app>/main.tf skeleton for ECS Fargate
    (ALB → ECS service → RDS Postgres). Variables only — no hardcoded account IDs or ARNs.
2e. devops_write_deployment_md(targetApp) — DEPLOYMENT.md runbook with: prerequisites, env vars,
    build command, deploy command, rollback steps, monitoring links to fill in.

**Step 3 — final response (LAST)**
Reply with sections in order:
1. **status** — ready | blocked
   - `ready` → all artifacts written, security gate passed
   - `blocked` → security gate failed; report findings, no artifacts written
2. **artifacts** — list of files written
3. **deploy_commands** — concrete shell commands (build, push, deploy)
4. **env_vars** — every variable that must be set in the deploy environment
5. **manual_steps** — anything a human must do (DNS, secrets, IAM trust policy, etc.)
6. **handoff_json** — fenced ```json block with keys:
   targetApp, status, artifacts, deployCommands, envVars, manualSteps, securityGate,
   jiraKey (or null). Consumed by the orchestrator and any future deploy automation.

Write ONLY:
- `target-apps/<service>/Dockerfile`
- `target-apps/<service>/.dockerignore`
- `target-apps/<service>/.gitlab-ci.yml`
- `target-apps/<service>/DEPLOYMENT.md`
- `infrastructure/<service>/main.tf`
- `infrastructure/<service>/variables.tf`
- `infrastructure/<service>/outputs.tf`

Never modify app/ code, tests/, or db/sql/. Those are upstream territory.
"""

_READ_PREFIXES = (
    _TARGET_APPS,
    _REPO_ROOT / "docs",
    _REPO_ROOT / "agents",
    _REPO_ROOT / "inputs",
    _INFRA_DIR,
)

_written_files: list[str] = []
_security_gate_status: str = "unknown"
_force_deploy: bool = False

DEVOPS_SYS_PROMPT = """\
You are the DevOps Agent for the Autonomous SDLC platform. You run **after security-agent**
as the eighth pipeline step: product → architect → web-crawler → database → developer → qa → security → **YOU**.

Your job is to take a working, tested, security-reviewed service from `target-apps/<service>/`
and produce the artifacts needed to **deploy it to AWS**. You do NOT modify app code; you wrap
it in container, CI/CD, and infrastructure configuration.

## MVP scope (current platform default)

- **In scope:**
  - Dockerfile (multi-stage Python build, slim runtime image)
  - .dockerignore (standard Python/FastAPI excludes)
  - GitLab CI/CD pipeline (`.gitlab-ci.yml`) with stages: lint → test → security-scan → build → deploy
  - Terraform skeleton under `infrastructure/<service>/` — ECS Fargate behind ALB + RDS Postgres + ECR + IAM task role
  - `DEPLOYMENT.md` runbook (env vars, build/deploy commands, rollback)
- **Out of scope (Phase 2+):** Helm charts, EKS, Lambda packaging, GitHub Actions, AWS CDK, Pulumi.

## Quality gate — refuse to proceed on security failure

Before writing any artifact, read `securityHandoffPath` if present:
- `status: "pass"` → proceed.
- `status: "fail"` with `criticalCount > 0` or `highCount > 0`:
  - If `forceDeploy` is true in context, write artifacts BUT include a prominent warning
    block in DEPLOYMENT.md listing the high/critical findings.
  - Otherwise, STOP. Report blocking findings in your response and do NOT write artifacts.
- `status: "error"` (all scanners failed): write artifacts but flag tooling-status in DEPLOYMENT.md.

## Inputs — read ALL that are present

| Context key | Read how | What it contains |
|-------------|----------|-----------------|
| `targetApp` | Context JSON | Service folder name |
| `developerHandoffPath` | `devops_read_file` | port, envVarNames, runCommand, deploymentHandoff |
| `qaHandoffPath` | `devops_read_file` | testCommand for the CI test stage |
| `securityHandoffPath` | `devops_read_file` | status, findings — drives the quality gate |
| `designDocPath` | `devops_read_file` | health path, AWS region, infra constraints |
| `forceDeploy` | Context JSON | When true, bypass security gate (write artifacts with warning) |

## Tools — use in this order

| Tool | Purpose |
|------|---------|
| `devops_list_tree` | Inventory the service |
| `devops_read_file` | Read PRD, design, app config (read-only) |
| `devops_write_file` | Generic writer scoped to allowed paths below |
| `devops_write_dockerfile` | Specialized: writes Dockerfile from handoff |
| `devops_write_dockerignore` | Specialized: standard Python .dockerignore |
| `devops_write_gitlab_ci` | Specialized: 5-stage GitLab CI pipeline |
| `devops_write_terraform` | Specialized: ECS Fargate Terraform skeleton |
| `devops_write_deployment_md` | Specialized: human-readable runbook |

## Generation principles

- **Idempotent**: never hardcode AWS account IDs, ARNs, or environment-specific URLs.
  Use Terraform variables and CI/CD job variables (set in GitLab project settings).
- **Slim images**: multi-stage builds; copy only what's needed; non-root user in runtime.
- **Health checks**: container HEALTHCHECK + ALB target group health-check both hit `/health`
  (or whatever design specifies). Match exactly — do not invent `/healthz` if design says `/health`.
- **Secrets**: never put real secrets in Dockerfile, CI YAML, or Terraform. Reference them
  via SSM Parameter Store / Secrets Manager / GitLab CI variables.
- **Database**: deploy artifacts reference RDS via DATABASE_URL env var. Do not embed credentials.
  When the app uses Bedrock (postgres-llm/rag patterns), the ECS task role gets `bedrock:InvokeModel`.
- **CI test stage**: use `testCommand` from qa-handoff verbatim. Do not invent a different command.
- **Rollback**: every deploy job has a documented rollback (image tag pin in DEPLOYMENT.md).

## Writing rules

- Write ONLY to:
  - `target-apps/<service>/Dockerfile`
  - `target-apps/<service>/.dockerignore`
  - `target-apps/<service>/.gitlab-ci.yml`
  - `target-apps/<service>/DEPLOYMENT.md`
  - `infrastructure/<service>/*.tf`
- Never edit `app/`, `tests/`, `db/sql/`, or `requirements.txt`. Those are upstream territory.

## Response format

Always end with **handoff_json** (fenced ```json) for orchestrator consumption.
Keep prose tight; put artifact paths in the structured arrays.
"""


# ── Helpers ──────────────────────────────────────────────────────────────────

def _resolve_repo_path(relative_path: str, *, write: bool) -> Path:
    raw = relative_path.strip().replace("\\", "/")
    if not raw:
        raise ValueError("path is required")
    candidate = (
        (_REPO_ROOT / raw).resolve()
        if not Path(raw).is_absolute()
        else Path(raw).resolve()
    )
    if not str(candidate).startswith(str(_REPO_ROOT.resolve())):
        raise ValueError(f"path must stay inside repo: {relative_path}")
    if write:
        allowed_roots = (_TARGET_APPS.resolve(), _INFRA_DIR.resolve())
        if not any(str(candidate).startswith(str(r)) for r in allowed_roots):
            raise ValueError("writes only allowed under target-apps/ or infrastructure/")
        return candidate
    allowed = (
        any(str(candidate).startswith(str(p.resolve())) for p in _READ_PREFIXES)
        or candidate == _REPO_ROOT.resolve()
    )
    if not allowed:
        raise ValueError(f"read not allowed for path: {relative_path}")
    return candidate


def _service_dir(service: str) -> Path:
    return _TARGET_APPS / slugify(service)


def _ensure_service_exists(service: str) -> Path:
    dest = _service_dir(service)
    if not dest.is_dir():
        raise ValueError(f"service not found: target-apps/{slugify(service)}/")
    return dest


def _infra_dir_for(service: str) -> Path:
    return _INFRA_DIR / slugify(service)


def _allowed_write_path(file_path: Path) -> bool:
    rel = file_path.resolve()
    return str(rel).startswith(str(_TARGET_APPS.resolve())) or str(rel).startswith(
        str(_INFRA_DIR.resolve())
    )


def _record_written(path: Path) -> None:
    rel = path.relative_to(_REPO_ROOT).as_posix()
    if rel not in _written_files:
        _written_files.append(rel)


# ── File tools ───────────────────────────────────────────────────────────────

@tool
def devops_list_tree(service: str, subpath: str = "") -> str:
    """List files under target-apps/<service>/ (optionally under subpath)."""
    try:
        root = _ensure_service_exists(service)
    except ValueError as exc:
        return f"Error: {exc}"
    base = (root / subpath).resolve()
    if not str(base).startswith(str(root.resolve())):
        return "Error: subpath escapes service directory"
    if not base.exists():
        return f"Error: not found: {base.relative_to(_REPO_ROOT).as_posix()}"
    lines: list[str] = []
    for path in sorted(base.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and ".venv" not in path.parts:
            lines.append(path.relative_to(_REPO_ROOT).as_posix())
    return "\n".join(lines) if lines else "(no files)"


@tool
def devops_read_file(path: str) -> str:
    """Read a repo file. Allowed: target-apps/, docs/, agents/, inputs/, infrastructure/."""
    try:
        file_path = _resolve_repo_path(path, write=False)
    except ValueError as exc:
        return f"Error: {exc}"
    if not file_path.is_file():
        return f"Error: not a file: {path}"
    try:
        text = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return f"Error: binary or non-utf8 file: {path}"
    if len(text) > 120_000:
        return text[:120_000] + "\n\n... (truncated)"
    return text


@tool
def devops_write_file(path: str, content: str) -> str:
    """Generic writer. Allowed paths: target-apps/<svc>/ and infrastructure/<svc>/."""
    try:
        file_path = _resolve_repo_path(path, write=True)
    except ValueError as exc:
        return f"Error: {exc}"
    if not _allowed_write_path(file_path):
        return "Error: writes limited to target-apps/ and infrastructure/"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8", newline="\n")
    _record_written(file_path)
    return f"wrote {file_path.relative_to(_REPO_ROOT).as_posix()} ({len(content)} chars)"


# ── Specialized generators ───────────────────────────────────────────────────

_DEFAULT_DOCKERFILE = """\
# Multi-stage build for FastAPI services.
# Stage 1 builds wheels into a venv; stage 2 ships only the venv + app code.

FROM python:3.12-slim AS builder
WORKDIR /build
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \\
    && pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim AS runtime
RUN groupadd --system app && useradd --system --gid app --home /home/app app \\
    && mkdir -p /app && chown -R app:app /app
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --chown=app:app . /app
ENV PATH="/opt/venv/bin:$PATH" \\
    PYTHONUNBUFFERED=1 \\
    PYTHONDONTWRITEBYTECODE=1 \\
    PORT=8000
EXPOSE 8000
USER app
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \\
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=3).status==200 else 1)"
CMD ["sh","-c","uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
"""

_DEFAULT_DOCKERIGNORE = """\
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
.venv/
venv/
env/
.git/
.gitignore
.gitlab-ci.yml
.dockerignore
Dockerfile
DEPLOYMENT.md
SECURITY_REPORT.md
QA_REPORT.md
.env
.env.*
!.env.example
tests/
.pytest_cache/
.mypy_cache/
.ruff_cache/
*.md
docs/
node_modules/
.idea/
.vscode/
"""

_DEFAULT_GITLAB_CI = """\
# GitLab CI/CD pipeline for the {service} service.
# Stages run sequentially; a failed stage blocks the next.
# Set the following GitLab CI/CD variables (Settings → CI/CD → Variables):
#   AWS_ACCOUNT_ID, AWS_DEFAULT_REGION, ECR_REPO_URL,
#   DATABASE_URL (masked, environment-scoped), API_KEY (masked),
#   plus any service-specific vars listed in DEPLOYMENT.md.

stages:
  - lint
  - test
  - security-scan
  - build
  - deploy

variables:
  PYTHON_IMAGE: python:3.12-slim
  IMAGE_TAG: $CI_COMMIT_SHORT_SHA
  IMAGE_URL: $ECR_REPO_URL:$IMAGE_TAG

# ── Lint ──────────────────────────────────────────────────────────────────
lint:
  stage: lint
  image: $PYTHON_IMAGE
  script:
    - cd target-apps/{service}
    - pip install --no-cache-dir ruff
    - ruff check app schemas tests
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH

# ── Unit tests (qa-agent's testCommand) ───────────────────────────────────
test:
  stage: test
  image: $PYTHON_IMAGE
  script:
    - cd target-apps/{service}
    - pip install --no-cache-dir -r requirements.txt
    - {test_command}
  artifacts:
    when: always
    reports:
      junit: target-apps/{service}/pytest-report.xml
    expire_in: 1 week

# ── Security scan (bandit + pip-audit) ────────────────────────────────────
security-scan:
  stage: security-scan
  image: $PYTHON_IMAGE
  script:
    - cd target-apps/{service}
    - pip install --no-cache-dir bandit pip-audit
    - bandit -r app -q
    - pip-audit -r requirements.txt --strict
  allow_failure: false

# ── Build & push container ────────────────────────────────────────────────
build:
  stage: build
  image: docker:24
  services:
    - docker:24-dind
  script:
    - apk add --no-cache aws-cli
    - aws ecr get-login-password --region $AWS_DEFAULT_REGION | docker login --username AWS --password-stdin $ECR_REPO_URL
    - docker build -t $IMAGE_URL target-apps/{service}
    - docker push $IMAGE_URL
  only:
    - main

# ── Deploy to AWS (ECS Fargate force-new-deployment) ──────────────────────
deploy:
  stage: deploy
  image: amazon/aws-cli:latest
  script:
    - aws ecs update-service --cluster $ECS_CLUSTER --service {service} --force-new-deployment --region $AWS_DEFAULT_REGION
  environment:
    name: dev
    url: https://{service}.dev.internal
  rules:
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
      when: manual   # human-gated deploy per SDLC governance model
"""

_DEFAULT_TERRAFORM_MAIN = """\
# Terraform skeleton for the {service} service on AWS ECS Fargate.
# This is a starting point — adjust networking, capacity, and IAM policies for
# your environment. Run `terraform init && terraform plan` to review before apply.

terraform {{
  required_version = ">= 1.5"
  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }}
  }}
}}

provider "aws" {{
  region = var.aws_region
}}

# ── ECR repository for the service image ───────────────────────────────────
resource "aws_ecr_repository" "service" {{
  name                 = "{service}"
  image_tag_mutability = "MUTABLE"
  force_delete         = false

  image_scanning_configuration {{
    scan_on_push = true
  }}

  tags = var.common_tags
}}

# ── ECS cluster + service (Fargate) ────────────────────────────────────────
resource "aws_ecs_cluster" "main" {{
  name = "{service}-cluster"
  tags = var.common_tags
}}

resource "aws_iam_role" "task_execution" {{
  name = "{service}-task-execution"
  assume_role_policy = jsonencode({{
    Version = "2012-10-17"
    Statement = [{{
      Effect = "Allow"
      Principal = {{ Service = "ecs-tasks.amazonaws.com" }}
      Action = "sts:AssumeRole"
    }}]
  }})
}}

resource "aws_iam_role_policy_attachment" "task_execution_managed" {{
  role       = aws_iam_role.task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}}

# Task role — extend with Bedrock / Secrets Manager access as needed.
resource "aws_iam_role" "task" {{
  name = "{service}-task"
  assume_role_policy = jsonencode({{
    Version = "2012-10-17"
    Statement = [{{
      Effect = "Allow"
      Principal = {{ Service = "ecs-tasks.amazonaws.com" }}
      Action = "sts:AssumeRole"
    }}]
  }})
}}

resource "aws_ecs_task_definition" "service" {{
  family                   = "{service}"
  cpu                      = "512"
  memory                   = "1024"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  execution_role_arn       = aws_iam_role.task_execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([{{
    name      = "{service}"
    image     = "${{aws_ecr_repository.service.repository_url}}:${{var.image_tag}}"
    essential = true
    portMappings = [{{ containerPort = 8000, protocol = "tcp" }}]
    environment  = var.container_env
    secrets      = var.container_secrets
    logConfiguration = {{
      logDriver = "awslogs"
      options = {{
        "awslogs-group"         = aws_cloudwatch_log_group.service.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "ecs"
      }}
    }}
  }}])
}}

resource "aws_cloudwatch_log_group" "service" {{
  name              = "/ecs/{service}"
  retention_in_days = 14
  tags              = var.common_tags
}}

# Networking, ALB, target group, security groups, and RDS are intentionally
# left as TODO blocks — wire them to your existing VPC / shared modules.
"""

_DEFAULT_TERRAFORM_VARIABLES = """\
variable "aws_region" {{
  type        = string
  description = "AWS region for the {service} deployment"
  default     = "us-east-2"
}}

variable "image_tag" {{
  type        = string
  description = "ECR image tag to deploy (set by CI to the commit SHA)"
}}

variable "container_env" {{
  type        = list(object({{ name = string, value = string }}))
  description = "Non-secret environment variables for the container"
  default     = []
}}

variable "container_secrets" {{
  type        = list(object({{ name = string, valueFrom = string }}))
  description = "Secrets pulled from Secrets Manager / SSM Parameter Store"
  default     = []
}}

variable "common_tags" {{
  type        = map(string)
  description = "Tags applied to every resource"
  default = {{
    Service   = "{service}"
    ManagedBy = "terraform"
  }}
}}
"""

_DEFAULT_TERRAFORM_OUTPUTS = """\
output "ecr_repository_url" {{
  value       = aws_ecr_repository.service.repository_url
  description = "Push image to this URL from CI"
}}

output "ecs_cluster_name" {{
  value       = aws_ecs_cluster.main.name
  description = "Use with `aws ecs update-service --cluster` in the deploy job"
}}

output "task_role_arn" {{
  value       = aws_iam_role.task.arn
  description = "Attach additional policies to this role (e.g. bedrock:InvokeModel)"
}}
"""


def _read_developer_handoff(service: str) -> DeveloperHandoff | None:
    """Best-effort load of the developer handoff. Returns None on missing/invalid file."""
    path = _REPO_ROOT / "agents" / "pipeline" / f"{slugify(service)}.developer-handoff.json"
    if not path.is_file():
        return None
    try:
        return load_handoff(path, DeveloperHandoff)
    except (HandoffValidationError, ValueError, FileNotFoundError):
        return None


def _read_security_handoff(service: str) -> SecurityHandoff | None:
    path = _REPO_ROOT / "agents" / "pipeline" / f"{slugify(service)}.security-handoff.json"
    if not path.is_file():
        return None
    try:
        return load_handoff(path, SecurityHandoff)
    except (HandoffValidationError, ValueError, FileNotFoundError):
        return None


def _check_security_gate(service: str) -> tuple[str, str | None]:
    """Returns (gate_status, blocking_reason). Honors _force_deploy."""
    global _security_gate_status
    sec = _read_security_handoff(service)
    if sec is None:
        _security_gate_status = "no_security_handoff"
        return "warn", "No security-handoff found — running scan is recommended before deploy."
    if sec.status == "pass":
        _security_gate_status = "passed"
        return "pass", None
    if sec.status == "fail":
        reason = (
            f"Security gate: status=fail "
            f"(critical={sec.criticalCount}, high={sec.highCount}). "
            "Re-run security-agent after remediation or pass --force to override."
        )
        if _force_deploy:
            _security_gate_status = "failed_forced"
            return "warn", f"FORCED past security gate: {reason}"
        _security_gate_status = "failed"
        return "block", reason
    _security_gate_status = sec.status
    return "warn", f"Security status: {sec.status} (proceeding with caution)."


@tool
def devops_write_dockerfile(service: str) -> str:
    """Write a multi-stage Dockerfile to target-apps/<service>/Dockerfile."""
    try:
        service_dir = _ensure_service_exists(service)
    except ValueError as exc:
        return f"Error: {exc}"
    out = service_dir / "Dockerfile"
    out.write_text(_DEFAULT_DOCKERFILE, encoding="utf-8", newline="\n")
    _record_written(out)
    return f"wrote {out.relative_to(_REPO_ROOT).as_posix()}"


@tool
def devops_write_dockerignore(service: str) -> str:
    """Write a standard Python/FastAPI .dockerignore."""
    try:
        service_dir = _ensure_service_exists(service)
    except ValueError as exc:
        return f"Error: {exc}"
    out = service_dir / ".dockerignore"
    out.write_text(_DEFAULT_DOCKERIGNORE, encoding="utf-8", newline="\n")
    _record_written(out)
    return f"wrote {out.relative_to(_REPO_ROOT).as_posix()}"


@tool
def devops_write_gitlab_ci(service: str) -> str:
    """Write .gitlab-ci.yml. Pulls testCommand from developer/qa handoff when available."""
    try:
        service_dir = _ensure_service_exists(service)
    except ValueError as exc:
        return f"Error: {exc}"

    dev = _read_developer_handoff(service)
    test_command = "pytest tests/ -q --junitxml=pytest-report.xml"
    if dev and dev.testCommand:
        # Strip "cd target-apps/<svc> && " prefix if present — the CI step does `cd` itself.
        tc = dev.testCommand
        prefix = f"cd target-apps/{slugify(service)} && "
        if tc.startswith(prefix):
            tc = tc[len(prefix):]
        test_command = tc + " --junitxml=pytest-report.xml" if "--junitxml" not in tc else tc

    content = _DEFAULT_GITLAB_CI.format(service=slugify(service), test_command=test_command)
    out = service_dir / ".gitlab-ci.yml"
    out.write_text(content, encoding="utf-8", newline="\n")
    _record_written(out)
    return f"wrote {out.relative_to(_REPO_ROOT).as_posix()}"


@tool
def devops_write_terraform(service: str) -> str:
    """Write infrastructure/<service>/{main,variables,outputs}.tf — ECS Fargate skeleton."""
    infra = _infra_dir_for(service)
    infra.mkdir(parents=True, exist_ok=True)
    files = {
        "main.tf": _DEFAULT_TERRAFORM_MAIN.format(service=slugify(service)),
        "variables.tf": _DEFAULT_TERRAFORM_VARIABLES.format(service=slugify(service)),
        "outputs.tf": _DEFAULT_TERRAFORM_OUTPUTS,
    }
    written = []
    for name, content in files.items():
        path = infra / name
        path.write_text(content, encoding="utf-8", newline="\n")
        _record_written(path)
        written.append(path.relative_to(_REPO_ROOT).as_posix())
    return "wrote " + ", ".join(written)


@tool
def devops_write_deployment_md(service: str) -> str:
    """Write DEPLOYMENT.md — human runbook covering env vars, build, deploy, rollback."""
    try:
        service_dir = _ensure_service_exists(service)
    except ValueError as exc:
        return f"Error: {exc}"

    dev = _read_developer_handoff(service)
    sec = _read_security_handoff(service)
    env_vars = (dev.deploymentHandoff.envVarNames if dev and dev.deploymentHandoff else dev.envVarsRequired) if dev else []
    port = dev.deploymentHandoff.port if dev and dev.deploymentHandoff else 8000
    run_cmd = dev.runCommand or dev.runCommandLocal if dev else None

    security_section = ""
    if sec:
        if sec.status == "fail":
            security_section = (
                f"\n## ⚠️ Security gate: FAIL\n\n"
                f"- critical={sec.criticalCount}, high={sec.highCount}, "
                f"medium={sec.mediumCount}, low={sec.lowCount}\n"
                f"- See `SECURITY_REPORT.md` for findings.\n"
                f"- This deploy is proceeding under `--force`. Document the override + ETA to remediate.\n"
            )
        else:
            security_section = (
                f"\n## Security gate: {sec.status}\n\n"
                f"- critical={sec.criticalCount}, high={sec.highCount}, "
                f"medium={sec.mediumCount}, low={sec.lowCount}\n"
            )

    env_table = "\n".join(f"| `{v}` | TODO | yes |" for v in env_vars) or "| (none) | | |"

    content = f"""# {slugify(service)} — Deployment Runbook

This document is the canonical reference for deploying `{slugify(service)}` to AWS.
Generated by devops-agent; review before first production deploy.
{security_section}
## Container entrypoint

```
{run_cmd or f"uvicorn app.main:app --host 0.0.0.0 --port {port}"}
```

Container listens on port **{port}**. Health check hits `/health`.

## Required environment variables

| Variable | Source | Required |
|----------|--------|----------|
{env_table}

Set secrets via AWS Secrets Manager or SSM Parameter Store and reference them as
`container_secrets` in the Terraform module. Never put real values in `.env`,
Dockerfile, or `.gitlab-ci.yml`.

## Build (local)

```bash
cd target-apps/{slugify(service)}
docker build -t {slugify(service)}:local .
docker run --rm -p {port}:{port} --env-file .env {slugify(service)}:local
curl http://localhost:{port}/health
```

## CI/CD

`.gitlab-ci.yml` runs five stages: lint → test → security-scan → build → deploy.
Deploy is **manual** on `main` per the SDLC governance model. Required GitLab
CI/CD variables (Settings → CI/CD → Variables):

- `AWS_ACCOUNT_ID`, `AWS_DEFAULT_REGION`
- `ECR_REPO_URL` (the URL produced by `aws_ecr_repository.service`)
- `ECS_CLUSTER` (the name produced by `aws_ecs_cluster.main`)
- Service env vars (masked, environment-scoped)

## Terraform

```bash
cd infrastructure/{slugify(service)}
terraform init
terraform plan -var="image_tag=$CI_COMMIT_SHORT_SHA"
terraform apply -var="image_tag=$CI_COMMIT_SHORT_SHA"   # human approval
```

VPC, ALB, RDS, and security groups are intentionally left as TODOs in
`main.tf` — wire them to your existing shared modules.

## Rollback

```bash
# Pin to the previous known-good image tag:
aws ecs update-service \\
  --cluster $ECS_CLUSTER \\
  --service {slugify(service)} \\
  --task-definition $(aws ecs list-task-definitions \\
      --family-prefix {slugify(service)} --status ACTIVE --sort DESC \\
      --query 'taskDefinitionArns[1]' --output text)
```

Keep at least the previous 3 task-definition revisions ACTIVE for quick rollback.

## Monitoring

- CloudWatch log group: `/ecs/{slugify(service)}`
- Set up an alarm on `HTTPCode_Target_5XX_Count` from the ALB target group.
- Set up an alarm on RDS `DatabaseConnections` and `FreeStorageSpace`.

## Open items for the deploy engineer

- [ ] Provision RDS Postgres (or wire to existing shared instance) and create the schema.
- [ ] Create Secrets Manager entries for each masked CI variable.
- [ ] Wire ALB target group + listener rule for `{slugify(service)}`.
- [ ] Configure DNS record (CNAME or A-alias) pointing at the ALB.
"""
    out = service_dir / "DEPLOYMENT.md"
    out.write_text(content, encoding="utf-8", newline="\n")
    _record_written(out)
    return f"wrote {out.relative_to(_REPO_ROOT).as_posix()}"


# ── Model + agent ────────────────────────────────────────────────────────────

class _DevOpsCallbackHandler:
    def __init__(self, telemetry: RunTelemetry | None = None) -> None:
        self.telemetry = telemetry

    def __call__(self, **kwargs: Any) -> None:
        event = kwargs.get("event", {})
        tool_use = event.get("contentBlockStart", {}).get("start", {}).get("toolUse")
        if tool_use:
            name = tool_use.get("name", "<unknown>")
            if self.telemetry is not None:
                self.telemetry.record_tool(name)
                print(f"\n[devops-agent] Tool #{self.telemetry.tool_count}: {name}", file=sys.stderr)
            else:
                print(f"\n[devops-agent] Tool: {name}", file=sys.stderr)
        if self.telemetry is not None:
            usage = usage_from_event(kwargs) or usage_from_event(event)
            if usage:
                self.telemetry.record_usage(usage)


def _max_output_tokens() -> int:
    return int(
        os.getenv(
            "DEVOPS_AGENT_MAX_TOKENS",
            os.getenv("BEDROCK_MAX_OUTPUT_TOKENS", "12288"),
        )
    )


def _devops_model() -> BedrockModel:
    model_id = os.getenv(
        "DEVOPS_MODEL_ID",
        os.getenv("MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0"),
    )
    read_timeout = int(os.getenv("BEDROCK_READ_TIMEOUT", "600"))
    return BedrockModel(
        model_id=model_id,
        region_name=os.getenv("AWS_REGION", "us-east-2"),
        max_tokens=_max_output_tokens(),
        streaming=True,
        cache_config=CacheConfig(strategy="auto"),
        cache_tools="default",
        boto_client_config=botocore.config.Config(
            read_timeout=read_timeout,
            connect_timeout=10,
            retries={"mode": "standard", "max_attempts": 2},
        ),
    )


def _build_agent(telemetry: RunTelemetry | None = None) -> Agent:
    return Agent(
        agent_id=AGENT_NAME,
        name=AGENT_NAME,
        description=(
            "Produces deploy artifacts (Dockerfile, .gitlab-ci.yml, Terraform, DEPLOYMENT.md) "
            "for target-apps services. Honors a security gate from security-handoff: blocks "
            "deploy artifact generation when status=fail unless --force is set."
        ),
        model=_devops_model(),
        system_prompt=DEVOPS_SYS_PROMPT,
        tools=[
            devops_list_tree,
            devops_read_file,
            devops_write_file,
            devops_write_dockerfile,
            devops_write_dockerignore,
            devops_write_gitlab_ci,
            devops_write_terraform,
            devops_write_deployment_md,
        ],
        callback_handler=_DevOpsCallbackHandler(telemetry),
    )


def _user_message(task: str, context: dict[str, Any] | None) -> str:
    if not context:
        return task
    return f"{task}\n\nContext:\n{json.dumps(context, indent=2)}"


def _enrich_devops_context(ctx: dict[str, Any]) -> None:
    app = slugify(str(ctx["targetApp"]))
    service_dir = _REPO_ROOT / "target-apps" / app
    ctx.setdefault("targetAppDir", service_dir.relative_to(_REPO_ROOT).as_posix())

    for handoff_key, filename in (
        ("developerHandoffPath", f"{app}.developer-handoff.json"),
        ("qaHandoffPath", f"{app}.qa-handoff.json"),
        ("securityHandoffPath", f"{app}.security-handoff.json"),
    ):
        if not ctx.get(handoff_key):
            candidate = _REPO_ROOT / "agents" / "pipeline" / filename
            if candidate.is_file():
                ctx[handoff_key] = candidate.relative_to(_REPO_ROOT).as_posix()


def _build_context(
    *, target_app: str, jira_key: str | None = None, extra: dict[str, Any] | None = None
) -> dict[str, Any]:
    service_path = _ensure_service_exists(target_app)
    ctx: dict[str, Any] = {
        "targetApp": target_app,
        "targetAppDir": service_path.relative_to(_REPO_ROOT).as_posix(),
        "forceDeploy": _force_deploy,
    }
    if jira_key:
        ctx["jiraKey"] = jira_key
    if extra:
        ctx.update(extra)
    return ctx


def _write_devops_handoff(app: str, payload: dict[str, Any]) -> str:
    pipeline_dir = _REPO_ROOT / "agents" / "pipeline"
    pipeline_dir.mkdir(parents=True, exist_ok=True)
    out = pipeline_dir / f"{slugify(app)}.devops-handoff.json"
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return out.relative_to(_REPO_ROOT).as_posix()


def run_task(
    task: str,
    context: dict[str, Any] | None = None,
    *,
    target_app: str | None = None,
    jira_key: str | None = None,
) -> tuple[str, list[str], str | None]:
    global _written_files
    _written_files = []

    app = target_app or (context or {}).get("targetApp")
    if not app:
        raise TargetAppRequiredError("--target-app or context.targetApp required")
    app = slugify(str(app))

    ctx = context if context is not None else _build_context(target_app=app, jira_key=jira_key)
    ctx.setdefault("targetApp", app)
    ctx.setdefault("targetAppDir", _ensure_service_exists(app).relative_to(_REPO_ROOT).as_posix())
    ctx.setdefault("forceDeploy", _force_deploy)

    enrich_handoff_context(ctx, include_db_paths=True)
    _enrich_devops_context(ctx)

    # Check the security gate up front; the LLM still gets the context but we
    # surface the gate decision early in stderr.
    gate, reason = _check_security_gate(app)
    if gate == "block":
        print(f"[devops-agent] SECURITY GATE BLOCKED: {reason}", file=sys.stderr)
    elif gate == "warn":
        print(f"[devops-agent] WARNING: {reason}", file=sys.stderr)

    if jira_key:
        ctx.setdefault("jiraKey", jira_key)

    telemetry = RunTelemetry(AGENT_NAME, target_app=app)
    agent = _build_agent(telemetry)
    summary = str(agent(_user_message(task, ctx)))

    handoff = {
        "targetApp": app,
        "status": "blocked" if gate == "block" and not _written_files else "ready",
        "artifacts": list(_written_files),
        "securityGate": {"result": gate, "reason": reason, "status": _security_gate_status},
        "designDocPath": ctx.get("designDocPath"),
        "developerHandoffPath": ctx.get("developerHandoffPath"),
        "securityHandoffPath": ctx.get("securityHandoffPath"),
        "jiraKey": ctx.get("jiraKey"),
    }
    handoff_rel = _write_devops_handoff(app, handoff)

    telemetry.extra = {
        "filesWritten": len(_written_files),
        "securityGate": gate,
        "forceDeploy": _force_deploy,
    }
    telemetry.print_summary()
    telemetry.persist()

    return summary, list(_written_files), handoff_rel


def serve_a2a(host: str = "127.0.0.1", port: int = A2A_PORT) -> None:
    skills = [
        AgentSkill(
            id="generate_deploy_artifacts",
            name="generate_deploy_artifacts",
            description=(
                "Produce Dockerfile, .gitlab-ci.yml, Terraform skeleton, and DEPLOYMENT.md for a "
                "target-apps service. Honors security-handoff status as a quality gate."
            ),
            tags=["devops", "docker", "gitlab-ci", "terraform", "aws", "ecs"],
        )
    ]
    agent = _build_agent()
    A2AServer(agent, host=host, port=port, skills=skills).serve()


def main() -> None:
    global _force_deploy
    parser = argparse.ArgumentParser(description="DevOps agent — Strands + Bedrock + scoped infra tools")
    parser.add_argument("--task", help="Optional task override. Default: full pipeline task.")
    parser.add_argument(
        "--target-app",
        help="Service folder under target-apps/ (or context targetApp / DEVOPS_TARGET_APP env).",
    )
    parser.add_argument("--no-auto-context", action="store_true", help="Skip auto context load.")
    parser.add_argument("--jira-key", help="Jira key (e.g. SAAP-3)")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Override the security gate. Use only when remediation is tracked elsewhere.",
    )
    load_context_extra(parser)
    parser.add_argument("--serve-a2a", action="store_true", help=f"Start A2A server on :{A2A_PORT}")
    parser.add_argument("--port", type=int, default=A2A_PORT)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    _force_deploy = bool(args.force)

    if args.serve_a2a:
        serve_a2a(host=args.host, port=args.port)
        return

    if not args.task:
        args.task = DEFAULT_PIPELINE_TASK

    try:
        extra, target = resolve_cli_context(
            args.target_app,
            parse_context_args(args),
            no_auto_context=args.no_auto_context,
            env_var="DEVOPS_TARGET_APP",
        )
    except TargetAppRequiredError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    if extra.get("_contextFile"):
        print(f"[devops-agent] Context (auto): {extra['_contextFile']}", file=sys.stderr)

    enrich_handoff_context(extra, include_db_paths=True)
    _enrich_devops_context(extra)

    ctx = _build_context(target_app=target, jira_key=args.jira_key, extra=extra or None)

    model_id = os.getenv(
        "DEVOPS_MODEL_ID",
        os.getenv("MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0"),
    )
    print("", file=sys.stderr)
    print("=" * 64, file=sys.stderr)
    force_label = "  |  FORCE DEPLOY (security gate overridden)" if _force_deploy else ""
    print(
        f"  AGENT: {AGENT_NAME}  |  prompt-cache: auto  |  cache_tools: default{force_label}",
        file=sys.stderr,
    )
    print("=" * 64, file=sys.stderr)
    print(f"[devops-agent] Model      : {model_id}", file=sys.stderr)
    print(f"[devops-agent] Target app : {ctx['targetAppDir']}", file=sys.stderr)
    print(f"[devops-agent] Design doc : {resolve_design_doc_path(ctx)}", file=sys.stderr)
    for label, key in (
        ("Dev handoff", "developerHandoffPath"),
        ("QA handoff ", "qaHandoffPath"),
        ("Sec handoff", "securityHandoffPath"),
    ):
        if ctx.get(key):
            print(f"[devops-agent] {label}: {ctx[key]}", file=sys.stderr)
    print("[devops-agent] Running...", file=sys.stderr)

    result, written, handoff_rel = run_task(
        args.task, ctx, target_app=target, jira_key=args.jira_key
    )
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print(result)
    if written:
        print(
            f"[devops-agent] Wrote {len(written)} file(s)",
            file=sys.stderr,
        )
    if handoff_rel:
        print(f"[devops-agent] Handoff   : {handoff_rel}", file=sys.stderr)


if __name__ == "__main__":
    main()
