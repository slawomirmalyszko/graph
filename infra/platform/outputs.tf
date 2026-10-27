output "ecr_repository_arn" {
  description = "ARN of the environment-specific application image repository."
  value       = aws_ecr_repository.application.arn
}

output "ecr_repository_url" {
  description = "URL used to tag and push application images."
  value       = aws_ecr_repository.application.repository_url
}
