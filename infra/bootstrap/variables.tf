variable "aws_region" {
  description = "AWS home region for all Integration Catalogue resources."
  type        = string
  default     = "eu-north-1"

  validation {
    condition     = var.aws_region == "eu-north-1"
    error_message = "The Integration Catalogue home region must remain eu-north-1."
  }
}

variable "project_name" {
  description = "Stable resource and tag prefix."
  type        = string
  default     = "integration-catalogue"
}

variable "state_bucket_name" {
  description = "Globally unique S3 bucket name for Terraform state."
  type        = string
}

variable "github_owner" {
  description = "GitHub repository owner name."
  type        = string
  default     = "slawomirmalyszko"
}

variable "github_owner_id" {
  description = "Immutable public GitHub repository owner ID."
  type        = string
  default     = "118607047"
}

variable "github_repository" {
  description = "GitHub repository name."
  type        = string
  default     = "graph"
}

variable "github_repository_id" {
  description = "Immutable public GitHub repository ID."
  type        = string
  default     = "1423602721"
}
