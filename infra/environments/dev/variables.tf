variable "aws_region" {
  description = "AWS home region for all Integration Catalogue resources."
  type        = string
  default     = "eu-north-1"

  validation {
    condition     = var.aws_region == "eu-north-1"
    error_message = "The Integration Catalogue home region must remain eu-north-1."
  }
}

variable "allowed_ingress_cidrs" {
  description = "Public CIDRs allowed to access the temporary DEV HTTP endpoint."
  type        = list(string)
}

variable "image_tag" {
  description = "Immutable sha-<full-commit-sha> image tag already published to ECR."
  type        = string
}

variable "auradb_secret_arn" {
  description = "ARN of the existing DEV AuraDB JSON secret."
  type        = string
  sensitive   = true
}

variable "desired_count" {
  description = "Running DEV task count; zero leaves DEV stopped."
  type        = number
  default     = 0
}
