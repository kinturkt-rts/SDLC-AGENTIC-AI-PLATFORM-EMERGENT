# Per-app deploy root for target-app: employee-leave-manager
# Auto-scaffolded by scripts/ensure-target-app-tf-root.py for destroy/redeploy.
# Deploy with: .\scripts\deploy-target-app.ps1 -Feature employee-leave-manager

terraform {
  required_version = ">= 1.10"

  backend "s3" {
    bucket       = "sdlc-tfstate-061836593297-us-east-2"
    key          = "dev/apps/employee-leave-manager/terraform.tfstate"
    region       = "us-east-2"
    use_lockfile = true
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region = "us-east-2"

  default_tags {
    tags = {
      Project     = "sdlc-agentic-ai-platform"
      Environment = "dev"
      TargetApp   = "employee-leave-manager"
      ManagedBy   = "terraform"
    }
  }
}

data "terraform_remote_state" "shared" {
  backend = "s3"
  config = {
    bucket = "sdlc-tfstate-061836593297-us-east-2"
    key    = "dev/_shared/terraform.tfstate"
    region = "us-east-2"
  }
}

module "app" {
  source = "../../../modules/target-app-ecs"

  app_name    = "employee-leave-manager"
  environment = "dev"
  aws_region  = "us-east-2"

  vpc_id                = data.terraform_remote_state.shared.outputs.vpc_id
  subnet_ids            = data.terraform_remote_state.shared.outputs.public_subnet_ids
  cluster_arn           = data.terraform_remote_state.shared.outputs.cluster_arn
  alb_listener_arn      = data.terraform_remote_state.shared.outputs.alb_listener_arn
  alb_security_group_id = data.terraform_remote_state.shared.outputs.alb_security_group_id

  enable_ui      = true
  enable_bedrock = true
  has_database         = true
  db_secret_arn        = aws_secretsmanager_secret.db.arn
  db_security_group_id = data.aws_db_instance.rds.vpc_security_groups[0]
}

variable "database_url" {
  description = "SQLAlchemy Postgres DSN — supplied by deploy script via TF_VAR_database_url."
  type        = string
  sensitive   = true
  default     = "postgresql+psycopg://unused:unused@localhost:5432/unused"
}

resource "aws_secretsmanager_secret" "db" {
  name                    = "sdlc/employee-leave-manager/database-url"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "db" {
  secret_id     = aws_secretsmanager_secret.db.id
  secret_string = var.database_url
}

data "aws_db_instance" "rds" {
  db_instance_identifier = "agenticaidbinstance"
}

output "app_url" {
  value = "http://${data.terraform_remote_state.shared.outputs.alb_dns_name}/employee-leave-manager/"
}

output "ecr_repository_api" {
  value = module.app.ecr_repository_api
}

output "ecr_repository_ui" {
  value = module.app.ecr_repository_ui
}

output "service_name" {
  value = module.app.service_name
}

output "cluster_name" {
  value = data.terraform_remote_state.shared.outputs.cluster_name
}
