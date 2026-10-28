variable "aws_region" {
  description = "AWS home region used for provider operations and project tagging."
  type        = string
  default     = "eu-north-1"

  validation {
    condition     = var.aws_region == "eu-north-1"
    error_message = "The Integration Catalogue home region must remain eu-north-1."
  }
}

variable "origin_domain_name" {
  description = "Current DEV ALB DNS name; ignored while the edge returns maintenance."
  type        = string
  default     = "maintenance.invalid"

  validation {
    condition     = can(regex("^[A-Za-z0-9.-]+$", var.origin_domain_name))
    error_message = "origin_domain_name must be a DNS hostname without a scheme or path."
  }
}

variable "maintenance_mode" {
  description = "Return the maintenance page at the edge instead of forwarding to the origin."
  type        = bool
  default     = true
}

