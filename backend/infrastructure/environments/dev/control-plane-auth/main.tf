# Cognito User Pool for SDLC control-plane UI login (standalone from agents/pipeline).
# Cost (dev): Cognito free tier covers 50k MAU — expected ~$0/mo for internal demos.
#
# Apply:
#   cd backend/infrastructure/environments/dev/control-plane-auth
#   aws sso login --profile eks-admin-user
#   terraform init
#   terraform apply

terraform {
  required_version = ">= 1.10"

  backend "s3" {
    bucket       = "sdlc-tfstate-061836593297-us-east-2"
    key          = "dev/control-plane-auth/terraform.tfstate"
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
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "sdlc-agentic-ai-platform"
      Environment = "dev"
      Component   = "control-plane-auth"
      ManagedBy   = "terraform"
    }
  }
}

variable "aws_region" {
  type    = string
  default = "us-east-2"
}

variable "callback_urls" {
  type = list(string)
  default = [
    "http://localhost:3000/login",
    "https://d14mr4f4z1bscv.cloudfront.net/login",
  ]
  description = "Allowed app callback URLs. Cognito requires HTTPS except localhost."
}

variable "logout_urls" {
  type = list(string)
  default = [
    "http://localhost:3000/login",
    "https://d14mr4f4z1bscv.cloudfront.net/login",
  ]
}

resource "aws_cognito_user_pool" "control_plane" {
  name = "sdlc-control-plane-users"

  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  username_configuration {
    case_sensitive = false
  }

  password_policy {
    minimum_length                   = 10
    require_lowercase                = true
    require_uppercase                = true
    require_numbers                  = true
    require_symbols                  = false
    temporary_password_validity_days = 7
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  admin_create_user_config {
    # Internal tool — admins create users; no public self-sign-up.
    allow_admin_create_user_only = true
  }

  schema {
    name                     = "email"
    attribute_data_type      = "String"
    required                 = true
    mutable                  = true
    developer_only_attribute = false

    string_attribute_constraints {
      min_length = 5
      max_length = 256
    }
  }

  tags = {
    Name = "sdlc-control-plane-users"
  }
}

resource "aws_cognito_user_pool_client" "control_plane_web" {
  name         = "sdlc-control-plane-web"
  user_pool_id = aws_cognito_user_pool.control_plane.id

  generate_secret = false

  explicit_auth_flows = [
    "ALLOW_USER_SRP_AUTH",
    "ALLOW_USER_PASSWORD_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
  ]

  prevent_user_existence_errors = "ENABLED"

  access_token_validity  = 1
  id_token_validity      = 1
  refresh_token_validity = 30

  token_validity_units {
    access_token  = "hours"
    id_token      = "hours"
    refresh_token = "days"
  }

  callback_urls = var.callback_urls
  logout_urls   = var.logout_urls

  supported_identity_providers = ["COGNITO"]
}

output "user_pool_id" {
  value = aws_cognito_user_pool.control_plane.id
}

output "user_pool_arn" {
  value = aws_cognito_user_pool.control_plane.arn
}

output "user_pool_client_id" {
  value = aws_cognito_user_pool_client.control_plane_web.id
}

output "region" {
  value = var.aws_region
}

output "frontend_env" {
  description = "Copy these into ECS task env / frontend .env.local"
  value = {
    COGNITO_USER_POOL_ID = aws_cognito_user_pool.control_plane.id
    COGNITO_CLIENT_ID    = aws_cognito_user_pool_client.control_plane_web.id
    COGNITO_REGION       = var.aws_region
  }
}
