#!/usr/bin/env python3
"""Ensure infrastructure/environments/dev/<app>/main.tf exists for destroy/deploy.

DevOps deploys write Terraform state to S3, but the local TF root is often missing
on another machine (not committed, or wiped). Destroy then fails with
"No Terraform root". This script rebuilds a compatible main.tf from remote state.

Usage:
  python scripts/ensure-target-app-tf-root.py --app shift-summary-bot
  python scripts/ensure-target-app-tf-root.py --app desk-booking --force
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
TF_BUCKET = "sdlc-tfstate-061836593297-us-east-2"
DEFAULT_REGION = "us-east-2"
DEFAULT_DB_INSTANCE = "agenticaidbinstance"

_TEMPLATE = '''\
# Per-app deploy root for target-app: {app}
# Auto-scaffolded by scripts/ensure-target-app-tf-root.py for destroy/redeploy.
# Deploy with: .\\scripts\\deploy-target-app.ps1 -Feature {app}

terraform {{
  required_version = ">= 1.10"

  backend "s3" {{
    bucket       = "{bucket}"
    key          = "dev/apps/{app}/terraform.tfstate"
    region       = "{region}"
    use_lockfile = true
  }}

  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }}
  }}
}}

provider "aws" {{
  region = "{region}"

  default_tags {{
    tags = {{
      Project     = "sdlc-agentic-ai-platform"
      Environment = "dev"
      TargetApp   = "{app}"
      ManagedBy   = "terraform"
    }}
  }}
}}

data "terraform_remote_state" "shared" {{
  backend = "s3"
  config = {{
    bucket = "{bucket}"
    key    = "dev/_shared/terraform.tfstate"
    region = "{region}"
  }}
}}

module "app" {{
  source = "../../../modules/target-app-ecs"

  app_name    = "{app}"
  environment = "dev"
  aws_region  = "{region}"

  vpc_id                = data.terraform_remote_state.shared.outputs.vpc_id
  subnet_ids            = data.terraform_remote_state.shared.outputs.public_subnet_ids
  cluster_arn           = data.terraform_remote_state.shared.outputs.cluster_arn
  alb_listener_arn      = data.terraform_remote_state.shared.outputs.alb_listener_arn
  alb_security_group_id = data.terraform_remote_state.shared.outputs.alb_security_group_id

  enable_ui      = {enable_ui}
  enable_bedrock = {enable_bedrock}
{db_block}}}

{db_resources}output "app_url" {{
  value = "http://${{data.terraform_remote_state.shared.outputs.alb_dns_name}}/{app}/"
}}

output "ecr_repository_api" {{
  value = module.app.ecr_repository_api
}}

output "ecr_repository_ui" {{
  value = module.app.ecr_repository_ui
}}

output "service_name" {{
  value = module.app.service_name
}}

output "cluster_name" {{
  value = data.terraform_remote_state.shared.outputs.cluster_name
}}
'''

_DB_BLOCK = """\
  has_database         = true
  db_secret_arn        = aws_secretsmanager_secret.db.arn
  db_security_group_id = data.aws_db_instance.rds.vpc_security_groups[0]
"""

_DB_BLOCK_NONE = "  db_secret_arn = null # no database for this app\n"

_DB_RESOURCES = '''\
variable "database_url" {{
  description = "SQLAlchemy Postgres DSN — supplied by deploy script via TF_VAR_database_url."
  type        = string
  sensitive   = true
  default     = "postgresql+psycopg://unused:unused@localhost:5432/unused"
}}

resource "aws_secretsmanager_secret" "db" {{
  name                    = "sdlc/{app}/database-url"
  recovery_window_in_days = 0
}}

resource "aws_secretsmanager_secret_version" "db" {{
  secret_id     = aws_secretsmanager_secret.db.id
  secret_string = var.database_url
}}

data "aws_db_instance" "rds" {{
  db_instance_identifier = "{db_instance}"
}}

'''


def _slug(app: str) -> str:
    return "-".join(app.strip().lower().split())


def _tf_root(app: str) -> Path:
    return BACKEND / "infrastructure" / "environments" / "dev" / app


def _main_tf_complete(path: Path) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    return 'module "app"' in text or "module \"app\"" in text


def _state_exists(app: str, region: str) -> bool:
    key = f"dev/apps/{app}/terraform.tfstate"
    proc = subprocess.run(
        [
            "aws",
            "s3api",
            "head-object",
            "--bucket",
            TF_BUCKET,
            "--key",
            key,
            "--region",
            region,
        ],
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0


def _load_state(app: str, region: str) -> dict:
    key = f"s3://{TF_BUCKET}/dev/apps/{app}/terraform.tfstate"
    proc = subprocess.run(
        ["aws", "s3", "cp", key, "-", "--region", region],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"Failed to read {key}")
    return json.loads(proc.stdout)


def _infer_flags(state: dict) -> tuple[bool, bool, bool, str]:
    enable_ui = False
    has_database = False
    enable_bedrock = False
    db_instance = DEFAULT_DB_INSTANCE

    for res in state.get("resources", []):
        rtype = res.get("type") or ""
        name = res.get("name") or ""
        module = res.get("module") or ""

        if rtype == "aws_ecr_repository" and name == "ui":
            enable_ui = True
        if rtype == "aws_secretsmanager_secret" and name == "db":
            has_database = True
        if rtype == "aws_iam_role_policy" and "bedrock" in name:
            enable_bedrock = True
        if rtype == "aws_db_instance" and name == "rds":
            for inst in res.get("instances") or []:
                attrs = inst.get("attributes") or {}
                ident = attrs.get("db_instance_identifier")
                if ident:
                    db_instance = ident

        # Bedrock policy may live under module.app
        if module == "module.app" and rtype == "aws_iam_role_policy" and "bedrock" in name:
            enable_bedrock = True

    return enable_ui, has_database, enable_bedrock, db_instance


def _render(app: str, region: str, enable_ui: bool, has_database: bool, enable_bedrock: bool, db_instance: str) -> str:
    if has_database:
        db_block = _DB_BLOCK
        db_resources = _DB_RESOURCES.format(app=app, db_instance=db_instance)
    else:
        db_block = _DB_BLOCK_NONE
        db_resources = ""

    return _TEMPLATE.format(
        app=app,
        bucket=TF_BUCKET,
        region=region,
        enable_ui="true" if enable_ui else "false",
        enable_bedrock="true" if enable_bedrock else "false",
        db_block=db_block,
        db_resources=db_resources,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", required=True, help="Target app slug (e.g. shift-summary-bot)")
    parser.add_argument("--region", default=DEFAULT_REGION)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite main.tf even if a complete root already exists",
    )
    args = parser.parse_args()
    app = _slug(args.app)
    root = _tf_root(app)
    main_tf = root / "main.tf"

    if _main_tf_complete(main_tf) and not args.force:
        print(f"OK: complete TF root already present at {main_tf.relative_to(BACKEND)}")
        return 0

    if not _state_exists(app, args.region):
        print(
            f"ERROR: no remote Terraform state for '{app}' "
            f"(s3://{TF_BUCKET}/dev/apps/{app}/terraform.tfstate). Nothing to scaffold.",
            file=sys.stderr,
        )
        return 2

    state = _load_state(app, args.region)
    enable_ui, has_database, enable_bedrock, db_instance = _infer_flags(state)
    content = _render(app, args.region, enable_ui, has_database, enable_bedrock, db_instance)

    root.mkdir(parents=True, exist_ok=True)
    main_tf.write_text(content, encoding="utf-8", newline="\n")
    print(
        f"WROTE {main_tf.relative_to(BACKEND)} "
        f"(enable_ui={enable_ui}, has_database={has_database}, enable_bedrock={enable_bedrock})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
