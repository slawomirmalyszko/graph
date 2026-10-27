# AWS agent and MCP workflow

## Purpose

This document defines how coding agents work with the project's AWS environment.
It complements the concise mandatory instructions in the repository-level
`AGENTS.md`.

## Project context

| Setting | Value |
| --- | --- |
| AWS project | Integration Catalogue |
| AWS experience | New experience |
| Plan | Free Plan |
| Home region | Europe (Stockholm) |
| Region code | `eu-north-1` |

The project display name is visible in AWS Settings. Standard AWS service APIs
can verify the underlying account, assumed role, and regional access, but may not
return that new-experience display name.

## Standard session procedure

1. Use the official AWS MCP connection.
2. Call STS `GetCallerIdentity` as a read-only authentication check.
3. Do not publish the full account ID in logs, documentation, or chat summaries.
4. Confirm the target region is `eu-north-1`.
5. Verify that the required service, feature, and—where applicable—Bedrock model
   are available in Stockholm.
6. Discover existing resources before proposing changes.
7. Explain cost and cleanup implications before creating resources.
8. Execute the smallest scoped change and read it back for verification.
9. Record durable architectural decisions in Git.

## Access boundaries

AWS MCP access and local shell access are separate:

- **AWS MCP** is the default for agent-driven AWS operations. It provides
  sandboxed API access and an auditable tool boundary.
- **Local AWS CLI/SDK** is used only when application development or a local
  diagnostic specifically needs credentials. Install AWS CLI 2.32 or later and
  run `aws login` after explicit user confirmation. This produces short-lived,
  automatically rotating credentials.
- **GitHub Actions** uses GitHub OIDC to assume a narrowly scoped AWS role. It
  must not use long-lived IAM access keys.

## Safety rules

- Never request or expose passwords, access keys, session tokens, or secret
  values.
- Never commit `.env` files or downloaded AWS credentials.
- Prefer read-only calls during investigation.
- Treat creation, update, and deletion as explicit operations with known scope.
- Identify resources using project and environment tags once the tagging policy
  is defined.
- Keep the deployment in `eu-north-1` unless an architecture decision explicitly
  authorizes another region.
- Do not assume that endpoint availability means a particular Bedrock model is
  available; verify the model immediately before implementation.

## Terraform and GitHub Actions

- Terraform roots live under `infra/`; never commit local state, plans, backend
  configuration, or populated bootstrap variables.
- Remote state uses the protected S3 bucket created by `infra/bootstrap` and
  native S3 lock files. `dev` and `prd` use separate state keys.
- Bootstrap is an explicit manual operation because GitHub OIDC does not exist
  until the bootstrap root has been applied. Do not automate it with static AWS
  credentials.
- GitHub environments named `dev` and `prd` control image publishing. Configure
  `AWS_GITHUB_OIDC_ROLE_ARN` as a GitHub environment variable, not a secret.
- Workflows authenticate with GitHub OIDC and publish immutable commit-SHA image
  tags. They do not receive Terraform permissions in this foundation increment.

## Verified baseline

On 2026-10-19, read-only checks established that:

- The agentic AWS MCP connection could assume the project's access role.
- STS caller identity succeeded.
- Amazon Bedrock discovery succeeded in `eu-north-1`.
- The regional resource-tagging API succeeded.
- No tagged project resources were returned at that time.

This baseline proves access at that point in time, not permanent authorization.
Future sessions must perform their own read-only verification.
