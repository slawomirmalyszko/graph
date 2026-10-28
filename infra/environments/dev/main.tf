provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "Integration Catalogue"
      Environment = "DEV"
      ManagedBy   = "Terraform"
    }
  }
}

module "runtime" {
  source = "../../modules/ecs-streamlit"

  project_name        = "integration-catalogue"
  environment         = "dev"
  aws_region          = var.aws_region
  vpc_cidr            = "10.20.0.0/20"
  ecr_repository_name = "integration-catalogue"
  image_tag           = var.image_tag
  auradb_secret_name  = var.auradb_secret_name
  desired_count       = var.desired_count
}
