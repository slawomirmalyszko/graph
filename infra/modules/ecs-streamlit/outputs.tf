output "application_url" {
  description = "Temporary HTTP URL; access is restricted by allowed_ingress_cidrs."
  value       = "http://${aws_lb.this.dns_name}"
}

output "ecs_cluster_name" {
  description = "ECS cluster name."
  value       = aws_ecs_cluster.this.name
}

output "ecs_service_name" {
  description = "ECS service name."
  value       = aws_ecs_service.app.name
}

output "log_group_name" {
  description = "CloudWatch log group for the application container."
  value       = aws_cloudwatch_log_group.app.name
}

output "deployed_image" {
  description = "Immutable application image selected for this environment."
  value       = local.image_uri
}
