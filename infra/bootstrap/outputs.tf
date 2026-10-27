output "github_image_publisher_role_arns" {
  description = "Set each value as AWS_GITHUB_OIDC_ROLE_ARN in its matching GitHub environment."
  value = {
    for environment, role in aws_iam_role.github_image_publisher :
    environment => role.arn
  }
}

output "terraform_state_bucket" {
  description = "S3 bucket used by remote Terraform backends."
  value       = aws_s3_bucket.terraform_state.id
}

output "github_oidc_subjects" {
  description = "Exact immutable GitHub OIDC subjects trusted by AWS."
  value       = local.oidc_subjects
}
