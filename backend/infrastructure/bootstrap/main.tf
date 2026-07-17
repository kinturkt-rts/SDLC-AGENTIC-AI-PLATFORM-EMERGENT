# One-time bootstrap: S3 bucket for Terraform remote state.
# Uses LOCAL state on purpose (chicken-and-egg) — run once, keep the tfstate file out of git.
# State locking uses S3 native lockfiles (Terraform >= 1.10), so no DynamoDB table is needed.
#
#   cd backend/infrastructure/bootstrap
#   terraform init && terraform apply

terraform {
  required_version = ">= 1.10"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  type    = string
  default = "us-east-2"
}

variable "state_bucket_name" {
  type    = string
  default = "sdlc-tfstate-061836593297-us-east-2"
}

resource "aws_s3_bucket" "tfstate" {
  bucket = var.state_bucket_name

  tags = {
    Project   = "sdlc-agentic-ai-platform"
    ManagedBy = "terraform-bootstrap"
  }
}

resource "aws_s3_bucket_versioning" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "tfstate" {
  bucket                  = aws_s3_bucket.tfstate.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

output "state_bucket" {
  value = aws_s3_bucket.tfstate.bucket
}
