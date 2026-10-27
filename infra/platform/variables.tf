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

variable "untagged_image_retention_days" {
  description = "Days to retain untagged images before automatic expiry."
  type        = number
  default     = 7

  validation {
    condition     = var.untagged_image_retention_days >= 1
    error_message = "Untagged images must be retained for at least one day."
  }
}
