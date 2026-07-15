# target-app-ecs — deploy one SDLC target-app (FastAPI api + optional Streamlit ui)
# as a single Fargate task behind the shared ALB, routed at /<app_name>/.
#
# Containers share the task network namespace, so the UI reaches the API at
# http://localhost:<api_port> — no service discovery needed.

terraform {
  required_version = ">= 1.10"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

locals {
  name       = "sdlc-${var.app_name}-${var.environment}"
  # Plan-time literal (var.db_secret_arn is often an unknown resource ARN, which
  # cannot drive count).
  has_db     = var.has_database
  # Streamlit serves under baseUrlPath = app_name so the shared ALB can path-route.
  ui_health  = "/${var.app_name}/_stcore/health"
  api_health = "/health"

  api_env = merge(
    {
      APP_NAME            = var.app_name
      ENVIRONMENT         = var.environment
      SKIP_STARTUP_CHECKS = local.has_db ? "0" : "1"
      # boto3 region for apps calling AWS services (Bedrock etc.)
      AWS_REGION         = var.aws_region
      AWS_DEFAULT_REGION = var.aws_region
    },
    # api-only apps face the ALB directly; serve_api.py strips this prefix
    var.enable_ui ? {} : { API_PATH_PREFIX = "/${var.app_name}" },
    var.extra_env,
  )

  api_container = {
    name      = "api"
    image     = "${aws_ecr_repository.api.repository_url}:${var.image_tag}"
    essential = true
    portMappings = [{ containerPort = var.api_port, protocol = "tcp" }]
    environment = [for k, v in local.api_env : { name = k, value = v }]
    secrets = local.has_db ? [
      { name = "DATABASE_URL", valueFrom = var.db_secret_arn }
    ] : []
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.app.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "api"
      }
    }
  }

  # one() -> null when the ui repo is disabled (count = 0)
  ui_repo_url = one(aws_ecr_repository.ui[*].repository_url)

  ui_container = {
    name      = "ui"
    image     = "${coalesce(local.ui_repo_url, "disabled")}:${var.image_tag}"
    essential = true
    portMappings = [{ containerPort = var.ui_port, protocol = "tcp" }]
    secrets = []
    # extra_env goes to the UI too: shared secrets (e.g. API_KEY the UI sends as a
    # header) must match the API container.
    environment = concat(
      [
        { name = "API_BASE_URL", value = "http://localhost:${var.api_port}" },
        { name = "STREAMLIT_SERVER_BASE_URL_PATH", value = var.app_name },
        { name = "STREAMLIT_SERVER_PORT", value = tostring(var.ui_port) },
        { name = "STREAMLIT_SERVER_HEADLESS", value = "true" },
        { name = "STREAMLIT_BROWSER_GATHER_USAGE_STATS", value = "false" },
      ],
      [for k, v in var.extra_env : { name = k, value = v }],
    )
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.app.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "ui"
      }
    }
  }

  containers = concat([local.api_container], var.enable_ui ? [local.ui_container] : [])

  # What the ALB forwards to.
  target_container = var.enable_ui ? "ui" : "api"
  target_port      = var.enable_ui ? var.ui_port : var.api_port
  health_path      = var.enable_ui ? local.ui_health : local.api_health
}

# ── ECR ────────────────────────────────────────────────────────────────────────
resource "aws_ecr_repository" "api" {
  name         = "sdlc/${var.app_name}/api"
  force_delete = true

  image_scanning_configuration {
    scan_on_push = false
  }
}

resource "aws_ecr_repository" "ui" {
  count        = var.enable_ui ? 1 : 0
  name         = "sdlc/${var.app_name}/ui"
  force_delete = true

  image_scanning_configuration {
    scan_on_push = false
  }
}

# ── Logs ───────────────────────────────────────────────────────────────────────
resource "aws_cloudwatch_log_group" "app" {
  name              = "/ecs/sdlc/${var.environment}/${var.app_name}"
  retention_in_days = var.log_retention_days
}

# ── IAM ────────────────────────────────────────────────────────────────────────
data "aws_iam_policy_document" "ecs_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "execution" {
  name               = "${local.name}-exec"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
}

resource "aws_iam_role_policy_attachment" "execution_managed" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "execution_secrets" {
  count = local.has_db ? 1 : 0
  name  = "read-db-secret"
  role  = aws_iam_role.execution.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = [var.db_secret_arn]
    }]
  })
}

resource "aws_iam_role" "task" {
  name               = "${local.name}-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
}

resource "aws_iam_role_policy" "task_bedrock" {
  count = var.enable_bedrock ? 1 : 0
  name  = "invoke-bedrock"
  role  = aws_iam_role.task.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ]
      Resource = [
        "arn:aws:bedrock:*::foundation-model/*",
        "arn:aws:bedrock:*:*:inference-profile/*"
      ]
    }]
  })
}

# ── Networking ─────────────────────────────────────────────────────────────────
resource "aws_security_group" "task" {
  name        = "${local.name}-task"
  description = "Fargate tasks for ${var.app_name} (${var.environment})"
  vpc_id      = var.vpc_id

  ingress {
    description     = "ALB to app target port"
    from_port       = local.target_port
    to_port         = local.target_port
    protocol        = "tcp"
    security_groups = [var.alb_security_group_id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_vpc_security_group_ingress_rule" "task_to_db" {
  count                        = var.db_security_group_id != null ? 1 : 0
  security_group_id            = var.db_security_group_id
  referenced_security_group_id = aws_security_group.task.id
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
  description                  = "sdlc target-app ${var.app_name} (${var.environment})"
}

# ── ALB wiring ─────────────────────────────────────────────────────────────────
resource "aws_lb_target_group" "app" {
  name        = substr("${local.name}-tg", 0, 32)
  port        = local.target_port
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  deregistration_delay = 15

  health_check {
    path                = local.health_path
    matcher             = "200"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }
}

resource "aws_lb_listener_rule" "app" {
  listener_arn = var.alb_listener_arn

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }

  condition {
    path_pattern {
      values = ["/${var.app_name}", "/${var.app_name}/*"]
    }
  }
}

# ── ECS ────────────────────────────────────────────────────────────────────────
resource "aws_ecs_task_definition" "app" {
  family                   = local.name
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn
  container_definitions    = jsonencode(local.containers)

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }
}

resource "aws_ecs_service" "app" {
  name            = local.name
  cluster         = var.cluster_arn
  task_definition = aws_ecs_task_definition.app.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  health_check_grace_period_seconds = 90

  network_configuration {
    subnets          = var.subnet_ids
    security_groups  = [aws_security_group.task.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.app.arn
    container_name   = local.target_container
    container_port   = local.target_port
  }

  # Task definition changes (new image tag) roll the service; :latest re-pushes
  # are rolled by the deploy script via --force-new-deployment.
  depends_on = [aws_lb_listener_rule.app]
}
