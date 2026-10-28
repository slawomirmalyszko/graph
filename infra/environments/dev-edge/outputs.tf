output "distribution_id" {
  description = "Persistent DEV CloudFront distribution ID."
  value       = aws_cloudfront_distribution.dev.id
}

output "cloudfront_domain_name" {
  description = "Persistent AWS-managed DEV hostname."
  value       = aws_cloudfront_distribution.dev.domain_name
}

output "application_url" {
  description = "Persistent HTTPS DEV URL."
  value       = "https://${aws_cloudfront_distribution.dev.domain_name}"
}

output "operational_state" {
  description = "Configured edge state."
  value       = var.maintenance_mode ? "maintenance" : "active"
}

