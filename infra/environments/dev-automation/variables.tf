variable "aws_region" {
  description = "AWS home region for all Integration Catalogue resources."
  type        = string
  default     = "eu-north-1"

  validation {
    condition     = var.aws_region == "eu-north-1"
    error_message = "The Integration Catalogue home region must remain eu-north-1."
  }
}

variable "state_bucket_name" {
  description = "Existing protected S3 bucket containing the DEV Terraform states."
  type        = string
}

variable "initial_image_tag" {
  description = "Existing immutable ECR image tag used until a successful update selects another image."
  type        = string

  validation {
    condition     = can(regex("^sha-[0-9a-f]{40}$", var.initial_image_tag))
    error_message = "initial_image_tag must use sha- followed by the full lowercase Git commit SHA."
  }
}

variable "repository_url" {
  description = "Public repository cloned by the standalone CodeBuild project."
  type        = string
  default     = "https://github.com/slawomirmalyszko/graph.git"
}

variable "repository_ref" {
  description = "Reviewed repository branch used by scheduled and manually requested lifecycle builds."
  type        = string
  default     = "main"
}

variable "terraform_version" {
  description = "Pinned Terraform CLI version downloaded and checksum-verified by CodeBuild."
  type        = string
  default     = "1.17.0"
}

variable "schedules_enabled" {
  description = "Enable weekday automatic activation and maintenance schedules."
  type        = bool
  default     = false
}

variable "schedule_timezone" {
  description = "IANA timezone used for DEV working-hour schedules and daylight-saving handling."
  type        = string
  default     = "Europe/Warsaw"
}

variable "activate_schedule_expression" {
  description = "EventBridge Scheduler expression for weekday DEV activation."
  type        = string
  default     = "cron(0 8 ? * MON-FRI *)"
}

variable "maintain_schedule_expression" {
  description = "EventBridge Scheduler expression for weekday DEV maintenance."
  type        = string
  default     = "cron(0 18 ? * MON-FRI *)"
}
