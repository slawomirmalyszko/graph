output "application_url" {
  description = "Restricted temporary DEV URL."
  value       = module.runtime.application_url
}

output "ecs_cluster_name" {
  description = "DEV ECS cluster name."
  value       = module.runtime.ecs_cluster_name
}

output "ecs_service_name" {
  description = "DEV ECS service name."
  value       = module.runtime.ecs_service_name
}

output "log_group_name" {
  description = "DEV application log group."
  value       = module.runtime.log_group_name
}

output "deployed_image" {
  description = "Immutable image selected for DEV."
  value       = module.runtime.deployed_image
}
