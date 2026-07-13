output "ecr_repository_api" {
  value = aws_ecr_repository.api.repository_url
}

output "ecr_repository_ui" {
  value = one(aws_ecr_repository.ui[*].repository_url)
}

output "service_name" {
  value = aws_ecs_service.app.name
}

output "task_security_group_id" {
  value = aws_security_group.task.id
}

output "app_path" {
  value = "/${var.app_name}/"
}
