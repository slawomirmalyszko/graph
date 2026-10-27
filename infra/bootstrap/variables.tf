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

variable "publisher_access_expires_at" {
  description = "UTC timestamp after which the GitHub ECR publisher policy stops authorizing requests. Rotate within 180 days."
  type        = string

  validation {
    condition     = can(timecmp(var.publisher_access_expires_at, "1970-01-01T00:00:00Z"))
    error_message = "publisher_access_expires_at must be an RFC 3339 timestamp."
  }
}
