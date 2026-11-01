data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

locals {
  project_name         = "integration-catalogue"
  build_project_name   = "${local.project_name}-dev-lifecycle"
  build_role_name      = "${local.project_name}-dev-lifecycle-codebuild"
  scheduler_role_name  = "${local.project_name}-dev-lifecycle-scheduler"
  schedule_group_name  = "${local.project_name}-dev"
  image_parameter_name = "/${local.project_name}/dev/image-tag"
  log_group_name       = "/aws/codebuild/${local.build_project_name}"
  build_project_arn    = "arn:${data.aws_partition.current.partition}:codebuild:${var.aws_region}:${data.aws_caller_identity.current.account_id}:project/${local.build_project_name}"
  schedule_group_arn   = "arn:${data.aws_partition.current.partition}:scheduler:${var.aws_region}:${data.aws_caller_identity.current.account_id}:schedule-group/${local.schedule_group_name}"
  schedule_source_arn  = "arn:${data.aws_partition.current.partition}:scheduler:${var.aws_region}:${data.aws_caller_identity.current.account_id}:schedule/${local.schedule_group_name}/*"
  state_bucket_arn     = "arn:${data.aws_partition.current.partition}:s3:::${var.state_bucket_name}"
  ecr_repository_arn   = "arn:${data.aws_partition.current.partition}:ecr:${var.aws_region}:${data.aws_caller_identity.current.account_id}:repository/${local.project_name}"
  image_parameter_arn  = "arn:${data.aws_partition.current.partition}:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${local.image_parameter_name}"
  runtime_role_arns = [
    "arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:role/${local.project_name}-dev-execution",
    "arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:role/${local.project_name}-dev-task",
  ]
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "Integration Catalogue"
      Environment = "DEV"
      ManagedBy   = "Terraform"
      Layer       = "Automation"
    }
  }
}

resource "aws_ssm_parameter" "image_tag" {
  name        = local.image_parameter_name
  description = "Last successfully selected immutable Integration Catalogue DEV image tag"
  type        = "String"
  value       = var.initial_image_tag

  lifecycle {
    ignore_changes = [value]
  }
}

resource "aws_cloudwatch_log_group" "codebuild" {
  name              = local.log_group_name
  retention_in_days = 14
}

data "aws_iam_policy_document" "codebuild_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["codebuild.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }

    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [local.build_project_arn]
    }
  }
}

resource "aws_iam_role" "codebuild" {
  name               = local.build_role_name
  assume_role_policy = data.aws_iam_policy_document.codebuild_trust.json
}

data "aws_iam_policy_document" "codebuild" {
  statement {
    sid = "WriteLifecycleBuildLogs"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = ["${aws_cloudwatch_log_group.codebuild.arn}:*"]
  }

  statement {
    sid       = "VerifyBuildIdentity"
    actions   = ["sts:GetCallerIdentity"]
    resources = ["*"]
  }

  statement {
    sid = "ListTerraformStateBucket"
    actions = [
      "s3:GetBucketLocation",
      "s3:GetBucketVersioning",
      "s3:ListBucket",
    ]
    resources = [local.state_bucket_arn]

    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values = [
        "runtime/dev/*",
        "edge/dev/*",
      ]
    }
  }

  statement {
    sid = "ManageDevTerraformStateObjects"
    actions = [
      "s3:DeleteObject",
      "s3:GetObject",
      "s3:PutObject",
    ]
    resources = [
      "${local.state_bucket_arn}/runtime/dev/*",
      "${local.state_bucket_arn}/edge/dev/*",
    ]
  }

  statement {
    sid = "ReadAndSelectDevImage"
    actions = [
      "ssm:GetParameter",
      "ssm:PutParameter",
    ]
    resources = [local.image_parameter_arn]
  }

  statement {
    sid = "ReadApplicationImages"
    actions = [
      "ecr:BatchGetImage",
      "ecr:DescribeImages",
      "ecr:DescribeRepositories",
      "ecr:ListImages",
    ]
    resources = [local.ecr_repository_arn]
  }

  statement {
    sid = "ReadRegionalInfrastructure"
    actions = [
      "ec2:Describe*",
      "ec2:GetManagedPrefixListEntries",
      "ecs:Describe*",
      "ecs:List*",
      "elasticloadbalancing:Describe*",
      "logs:DescribeLogGroups",
      "secretsmanager:DescribeSecret",
      "secretsmanager:ListSecrets",
    ]
    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "aws:RequestedRegion"
      values   = [var.aws_region]
    }
  }

  statement {
    sid = "ManageDevNetwork"
    actions = [
      "ec2:AssociateRouteTable",
      "ec2:AttachInternetGateway",
      "ec2:AuthorizeSecurityGroupEgress",
      "ec2:AuthorizeSecurityGroupIngress",
      "ec2:CreateInternetGateway",
      "ec2:CreateRoute",
      "ec2:CreateRouteTable",
      "ec2:CreateSecurityGroup",
      "ec2:CreateSubnet",
      "ec2:CreateTags",
      "ec2:CreateVpc",
      "ec2:DeleteInternetGateway",
      "ec2:DeleteRoute",
      "ec2:DeleteRouteTable",
      "ec2:DeleteSecurityGroup",
      "ec2:DeleteSubnet",
      "ec2:DeleteTags",
      "ec2:DeleteVpc",
      "ec2:DetachInternetGateway",
      "ec2:DisassociateRouteTable",
      "ec2:ModifySubnetAttribute",
      "ec2:ModifySecurityGroupRules",
      "ec2:ModifyVpcAttribute",
      "ec2:ReplaceRoute",
      "ec2:ReplaceRouteTableAssociation",
      "ec2:RevokeSecurityGroupEgress",
      "ec2:RevokeSecurityGroupIngress",
      "ec2:UpdateSecurityGroupRuleDescriptionsEgress",
      "ec2:UpdateSecurityGroupRuleDescriptionsIngress",
    ]
    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "aws:RequestedRegion"
      values   = [var.aws_region]
    }
  }

  statement {
    sid = "ManageDevLoadBalancer"
    actions = [
      "elasticloadbalancing:AddTags",
      "elasticloadbalancing:CreateListener",
      "elasticloadbalancing:CreateLoadBalancer",
      "elasticloadbalancing:CreateTargetGroup",
      "elasticloadbalancing:DeleteListener",
      "elasticloadbalancing:DeleteLoadBalancer",
      "elasticloadbalancing:DeleteTargetGroup",
      "elasticloadbalancing:ModifyLoadBalancerAttributes",
      "elasticloadbalancing:ModifyListener",
      "elasticloadbalancing:ModifyTargetGroup",
      "elasticloadbalancing:ModifyTargetGroupAttributes",
      "elasticloadbalancing:RemoveTags",
      "elasticloadbalancing:SetSecurityGroups",
      "elasticloadbalancing:SetSubnets",
    ]
    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "aws:RequestedRegion"
      values   = [var.aws_region]
    }
  }

  statement {
    sid = "ManageDevEcs"
    actions = [
      "ecs:CreateCluster",
      "ecs:CreateService",
      "ecs:DeleteCluster",
      "ecs:DeleteService",
      "ecs:DeregisterTaskDefinition",
      "ecs:PutClusterCapacityProviders",
      "ecs:RegisterTaskDefinition",
      "ecs:TagResource",
      "ecs:UntagResource",
      "ecs:UpdateCluster",
      "ecs:UpdateClusterSettings",
      "ecs:UpdateService",
    ]
    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "aws:RequestedRegion"
      values   = [var.aws_region]
    }
  }

  statement {
    sid = "ManageDevRuntimeLogs"
    actions = [
      "logs:CreateLogGroup",
      "logs:DeleteLogGroup",
      "logs:ListTagsForResource",
      "logs:PutRetentionPolicy",
      "logs:TagResource",
      "logs:UntagResource",
    ]
    resources = [
      "arn:${data.aws_partition.current.partition}:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/ecs/${local.project_name}-dev",
      "arn:${data.aws_partition.current.partition}:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/ecs/${local.project_name}-dev:*",
    ]
  }

  statement {
    sid = "ManageDevRuntimeRoles"
    actions = [
      "iam:CreateRole",
      "iam:DeleteRole",
      "iam:DeleteRolePolicy",
      "iam:GetRole",
      "iam:GetRolePolicy",
      "iam:ListAttachedRolePolicies",
      "iam:ListInstanceProfilesForRole",
      "iam:ListRolePolicies",
      "iam:ListRoleTags",
      "iam:PutRolePolicy",
      "iam:TagRole",
      "iam:UntagRole",
      "iam:UpdateAssumeRolePolicy",
    ]
    resources = local.runtime_role_arns
  }

  statement {
    sid       = "PassDevRuntimeRolesOnlyToEcs"
    actions   = ["iam:PassRole"]
    resources = local.runtime_role_arns

    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["ecs-tasks.amazonaws.com"]
    }
  }

  statement {
    sid = "ReadAndManageDevEdge"
    actions = [
      "cloudfront:CreateDistribution",
      "cloudfront:CreateDistributionWithTags",
      "cloudfront:CreateFunction",
      "cloudfront:DeleteDistribution",
      "cloudfront:DeleteFunction",
      "cloudfront:DescribeFunction",
      "cloudfront:GetCachePolicy",
      "cloudfront:GetDistribution",
      "cloudfront:GetDistributionConfig",
      "cloudfront:GetFunction",
      "cloudfront:GetOriginRequestPolicy",
      "cloudfront:GetResponseHeadersPolicy",
      "cloudfront:ListCachePolicies",
      "cloudfront:ListDistributions",
      "cloudfront:ListFunctions",
      "cloudfront:ListOriginRequestPolicies",
      "cloudfront:ListResponseHeadersPolicies",
      "cloudfront:ListTagsForResource",
      "cloudfront:PublishFunction",
      "cloudfront:TagResource",
      "cloudfront:UntagResource",
      "cloudfront:UpdateDistribution",
      "cloudfront:UpdateFunction",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "codebuild" {
  name   = "dev-lifecycle"
  role   = aws_iam_role.codebuild.id
  policy = data.aws_iam_policy_document.codebuild.json
}

resource "aws_codebuild_project" "lifecycle" {
  name                   = local.build_project_name
  description            = "Single executor for Integration Catalogue DEV activate, maintain, and update operations"
  service_role           = aws_iam_role.codebuild.arn
  build_timeout          = 60
  queued_timeout         = 30
  concurrent_build_limit = 1

  artifacts {
    type = "NO_ARTIFACTS"
  }

  source {
    type      = "NO_SOURCE"
    buildspec = file("${path.module}/../../../automation/dev-lifecycle-buildspec.yml")
  }

  environment {
    compute_type                = "BUILD_GENERAL1_SMALL"
    image                       = "aws/codebuild/standard:7.0"
    type                        = "LINUX_CONTAINER"
    image_pull_credentials_type = "CODEBUILD"
    privileged_mode             = false

    environment_variable {
      name  = "AWS_REGION"
      value = var.aws_region
    }

    environment_variable {
      name  = "EXPECTED_AWS_ACCOUNT_ID"
      value = data.aws_caller_identity.current.account_id
    }

    environment_variable {
      name  = "TF_STATE_BUCKET"
      value = var.state_bucket_name
    }

    environment_variable {
      name  = "DEV_IMAGE_PARAMETER_NAME"
      value = aws_ssm_parameter.image_tag.name
    }

    environment_variable {
      name  = "REPOSITORY_URL"
      value = var.repository_url
    }

    environment_variable {
      name  = "REPOSITORY_REF"
      value = var.repository_ref
    }

    environment_variable {
      name  = "TERRAFORM_VERSION"
      value = var.terraform_version
    }

    environment_variable {
      name  = "DEV_OPERATION"
      value = "unsupported"
    }
  }

  logs_config {
    cloudwatch_logs {
      status      = "ENABLED"
      group_name  = aws_cloudwatch_log_group.codebuild.name
      stream_name = "lifecycle"
    }
  }
}

resource "aws_scheduler_schedule_group" "dev" {
  name = local.schedule_group_name
}

data "aws_iam_policy_document" "scheduler_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }

    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = [local.schedule_source_arn]
    }
  }
}

resource "aws_iam_role" "scheduler" {
  name               = local.scheduler_role_name
  assume_role_policy = data.aws_iam_policy_document.scheduler_trust.json
}

data "aws_iam_policy_document" "scheduler" {
  statement {
    actions   = ["codebuild:StartBuild"]
    resources = [aws_codebuild_project.lifecycle.arn]
  }
}

resource "aws_iam_role_policy" "scheduler" {
  name   = "start-dev-lifecycle-build"
  role   = aws_iam_role.scheduler.id
  policy = data.aws_iam_policy_document.scheduler.json
}

resource "aws_scheduler_schedule" "activate" {
  name                         = "activate-weekdays"
  group_name                   = aws_scheduler_schedule_group.dev.name
  description                  = "Activate Integration Catalogue DEV on weekday mornings"
  state                        = var.schedules_enabled ? "ENABLED" : "DISABLED"
  schedule_expression          = var.activate_schedule_expression
  schedule_expression_timezone = var.schedule_timezone

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_codebuild_project.lifecycle.arn
    role_arn = aws_iam_role.scheduler.arn
    input = jsonencode({
      environmentVariablesOverride = [
        {
          name  = "DEV_OPERATION"
          type  = "PLAINTEXT"
          value = "activate"
        },
      ]
    })

    retry_policy {
      maximum_event_age_in_seconds = 3600
      maximum_retry_attempts       = 1
    }
  }
}

resource "aws_scheduler_schedule" "maintain" {
  name                         = "maintain-weeknights"
  group_name                   = aws_scheduler_schedule_group.dev.name
  description                  = "Put Integration Catalogue DEV into maintenance on weekday evenings"
  state                        = var.schedules_enabled ? "ENABLED" : "DISABLED"
  schedule_expression          = var.maintain_schedule_expression
  schedule_expression_timezone = var.schedule_timezone

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_codebuild_project.lifecycle.arn
    role_arn = aws_iam_role.scheduler.arn
    input = jsonencode({
      environmentVariablesOverride = [
        {
          name  = "DEV_OPERATION"
          type  = "PLAINTEXT"
          value = "maintain"
        },
      ]
    })

    retry_policy {
      maximum_event_age_in_seconds = 3600
      maximum_retry_attempts       = 1
    }
  }
}
