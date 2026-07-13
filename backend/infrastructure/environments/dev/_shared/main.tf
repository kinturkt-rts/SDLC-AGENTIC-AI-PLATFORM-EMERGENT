# Shared dev platform for SDLC target-apps: one ECS cluster + one ALB.
# Each app adds its own listener rule at /<app>/ via modules/target-app-ecs,
# so new apps cost only a Fargate task — not a new load balancer.

terraform {
  required_version = ">= 1.10"

  backend "s3" {
    bucket       = "sdlc-tfstate-061836593297-us-east-2"
    key          = "dev/_shared/terraform.tfstate"
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
      ManagedBy   = "terraform"
    }
  }
}

variable "aws_region" {
  type    = string
  default = "us-east-2"
}

# Default VPC + its public subnets — fine for dev; swap for a dedicated VPC later.
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "public" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
  filter {
    name   = "default-for-az"
    values = ["true"]
  }
}

resource "aws_ecs_cluster" "target_apps" {
  name = "sdlc-target-apps-dev"
}

resource "aws_security_group" "alb" {
  name        = "sdlc-target-apps-dev-alb"
  description = "Shared ALB for SDLC target-apps (dev)"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "HTTP from anywhere"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_lb" "target_apps" {
  name               = "sdlc-target-apps-dev"
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = data.aws_subnets.public.ids
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.target_apps.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "fixed-response"
    fixed_response {
      content_type = "text/plain"
      status_code  = "404"
      message_body = "SDLC target-apps ALB — no app matches this path. Apps live at /<app-name>/."
    }
  }
}

output "vpc_id" {
  value = data.aws_vpc.default.id
}

output "public_subnet_ids" {
  value = data.aws_subnets.public.ids
}

output "cluster_arn" {
  value = aws_ecs_cluster.target_apps.arn
}

output "cluster_name" {
  value = aws_ecs_cluster.target_apps.name
}

output "alb_dns_name" {
  value = aws_lb.target_apps.dns_name
}

output "alb_listener_arn" {
  value = aws_lb_listener.http.arn
}

output "alb_security_group_id" {
  value = aws_security_group.alb.id
}
