variable "project_name" {
  description = "Stable project resource prefix."
  type        = string
}

variable "environment" {
  description = "Deployment environment name."
  type        = string

  validation {
    condition     = contains(["dev", "prd"], var.environment)
    error_message = "Environment must be dev or prd."
  }
}

variable "aws_region" {
  description = "AWS region for all runtime resources."
  type        = string

  validation {
    condition     = var.aws_region == "eu-north-1"
    error_message = "The Integration Catalogue runtime must remain in eu-north-1."
  }
}

variable "vpc_cidr" {
  description = "CIDR allocated to the environment VPC."
  type        = string
}

variable "allowed_ingress_cidrs" {
  description = "Public CIDRs permitted to reach the HTTP ALB listener."
  type        = list(string)

  validation {
    condition     = length(var.allowed_ingress_cidrs) > 0 && !contains(var.allowed_ingress_cidrs, "0.0.0.0/0")
    error_message = "At least one restricted CIDR is required; 0.0.0.0/0 is not allowed."
  }
}

variable "ecr_repository_name" {
  description = "Name of the existing shared ECR repository."
  type        = string
}

variable "image_tag" {
  description = "Immutable ECR image tag to deploy."
  type        = string

  validation {
    condition     = can(regex("^sha-[0-9a-f]{40}$", var.image_tag))
    error_message = "image_tag must be sha- followed by a full 40-character Git commit SHA."
  }
}

variable "auradb_secret_arn" {
  description = "ARN of an existing JSON secret with NEO4J_URI, NEO4J_USERNAME, and NEO4J_PASSWORD keys."
  type        = string
  sensitive   = true

  validation {
    condition     = can(regex("^arn:[^:]+:secretsmanager:eu-north-1:[0-9]{12}:secret:", var.auradb_secret_arn))
    error_message = "auradb_secret_arn must be a Secrets Manager secret ARN in eu-north-1."
  }
}

variable "desired_count" {
  description = "Number of running Fargate tasks; set to zero to stop DEV compute."
  type        = number
  default     = 0

  validation {
    condition     = var.desired_count >= 0 && var.desired_count <= 2
    error_message = "desired_count must be between 0 and 2 for this demo."
  }
}

variable "bedrock_model_id" {
  description = "Regional Bedrock model invoked by the application."
  type        = string
  default     = "amazon.nova-lite-v1:0"
}

variable "log_retention_days" {
  description = "CloudWatch log retention period."
  type        = number
  default     = 7
}
