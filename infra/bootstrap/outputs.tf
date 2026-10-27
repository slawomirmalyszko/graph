output "github_image_publisher_user_name" {
  description = "IAM automation user whose manually created key is stored in the protected GitHub environment."
  value       = aws_iam_user.github_image_publisher.name
}

output "terraform_state_bucket" {
  description = "S3 bucket used by remote Terraform backends."
  value       = aws_s3_bucket.terraform_state.id
}

output "github_image_publisher_access_expires_at" {
  description = "Timestamp after which the publisher policy stops authorizing ECR requests."
  value       = var.publisher_access_expires_at
}
