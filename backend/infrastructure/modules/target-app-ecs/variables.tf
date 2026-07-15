variable "app_name" {
  description = "Target-app slug (e.g. hello-fastapi). Used for names, ECR repos, and the ALB path /<app_name>/."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,40}$", var.app_name))
    error_message = "app_name must be lowercase kebab-case (used in DNS-ish names and URL paths)."
  }
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "aws_region" {
  type    = string
  default = "us-east-2"
}

# ── Shared platform inputs (from environments/dev/_shared outputs) ────────────
variable "vpc_id" {
  type = string
}

variable "subnet_ids" {
  description = "Public subnets for the Fargate tasks (assign_public_ip = true, no NAT needed)."
  type        = list(string)
}

variable "cluster_arn" {
  type = string
}

variable "alb_listener_arn" {
  description = "Shared ALB HTTP listener; the module adds a path rule /<app_name>/*."
  type        = string
}

variable "alb_security_group_id" {
  description = "ALB security group — task SG only accepts traffic from it."
  type        = string
}

# ── App shape (devops-agent derives these from pipeline context) ──────────────
variable "enable_ui" {
  description = "true: Streamlit UI container is the ALB target; false: the FastAPI container is."
  type        = bool
  default     = true
}

variable "api_port" {
  type    = number
  default = 8000
}

variable "ui_port" {
  type    = number
  default = 8501
}

variable "image_tag" {
  type    = string
  default = "latest"
}

variable "cpu" {
  type    = number
  default = 512
}

variable "memory" {
  type    = number
  default = 1024
}

variable "desired_count" {
  type    = number
  default = 1
}

variable "has_database" {
  description = "Plan-time flag: app uses Postgres. Must be a literal (not derived from resources) so count expressions stay computable at plan."
  type        = bool
  default     = false
}

variable "enable_bedrock" {
  description = "App calls Amazon Bedrock (RAG/LLM) — grants InvokeModel on the task role."
  type        = bool
  default     = false
}

variable "db_secret_arn" {
  description = "Secrets Manager secret holding DATABASE_URL. Required when has_database = true."
  type        = string
  default     = null
}

variable "db_security_group_id" {
  description = "RDS security group to open 5432 into from the task SG. null = no database."
  type        = string
  default     = null
}

variable "extra_env" {
  description = "Extra plain-text env vars for the API container."
  type        = map(string)
  default     = {}
}

variable "log_retention_days" {
  type    = number
  default = 7
}
