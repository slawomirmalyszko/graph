# AWS deployment foundation

This guide prepares remote Terraform state and environment-specific ECR
repositories for the Integration Catalogue. It creates no ECS, load-balancer,
Cognito, networking, or always-running resources.

## Architecture

| Root | Responsibility | State |
| --- | --- | --- |
| `infra/bootstrap` | S3 state bucket, GitHub OIDC provider, image-publisher role | Bootstrapped locally, then migrated to S3 |
| `infra/platform` | One ECR repository for the selected environment | Separate `dev` and `prd` S3 keys |

All AWS resources are restricted to `eu-north-1`. GitHub Actions can publish
images but cannot run Terraform or change infrastructure.

## Cost and cleanup

The S3 bucket incurs small storage/request charges for state versions. ECR
incurs storage and transfer charges for pushed image layers. Basic image
scanning has no separate ECR scanning charge; enhanced Inspector scanning is
not enabled. No continuously running compute is created.

Untagged ECR images expire after seven days. To clean up, destroy each platform
environment before bootstrap. The state bucket uses `prevent_destroy` and
`force_destroy = false`; intentionally removing it requires first emptying all
state versions and temporarily removing the Terraform deletion guard. Retain an
offline state backup before doing that.

## Prerequisites

Before any apply:

1. Use AWS MCP to verify the expected caller identity and `eu-north-1` access.
2. Confirm the plan still uses only the intended Integration Catalogue account.
3. Install Terraform 1.10 or newer, or use the pinned CI version.
4. Use a confirmed short-lived local AWS session for the one-time bootstrap.
5. Create GitHub environments named `dev` and `prd`. Restrict deployments to
   `main`; add approval protection to `prd` when the stable deployment begins.

Do not put AWS account IDs, credentials, AuraDB values, or populated backend
files in Git.

## Validate locally without AWS access

```powershell
terraform fmt -check -recursive infra
terraform -chdir=infra/bootstrap init -backend=false
terraform -chdir=infra/bootstrap validate
terraform -chdir=infra/platform init -backend=false
terraform -chdir=infra/platform validate
```

These commands download the AWS provider but do not contact an AWS account.

## Bootstrap remote state

Copy the ignored local inputs and choose a globally unique bucket name:

```powershell
Copy-Item infra/bootstrap/terraform.tfvars.example infra/bootstrap/terraform.tfvars
```

The repository was created after GitHub's July 15, 2026 immutable-OIDC cutoff.
The committed public owner/repository IDs therefore form the exact trusted
subjects for the `dev` and `prd` environments.

Review before applying:

```powershell
terraform -chdir=infra/bootstrap init -backend=false
terraform -chdir=infra/bootstrap plan -out bootstrap.tfplan
terraform -chdir=infra/bootstrap apply bootstrap.tfplan
```

Then copy `backend.hcl.example` to the ignored `backend.hcl`, insert the created
bucket name, and migrate bootstrap state:

```powershell
Copy-Item infra/bootstrap/backend.hcl.example infra/bootstrap/backend.hcl
terraform -chdir=infra/bootstrap init -migrate-state -backend-config=backend.hcl
```

Confirm the migration before deleting any local state file.

## Create DEV and PRD ECR repositories

Copy each example backend file to its ignored `.hcl` counterpart and insert the
state bucket name. Run plan first and use the matching backend and variable file:

```powershell
terraform -chdir=infra/platform init -reconfigure -backend-config=backends/dev.hcl
terraform -chdir=infra/platform plan -var-file=environments/dev.tfvars -out dev.tfplan
terraform -chdir=infra/platform apply dev.tfplan
```

Repeat with `prd.hcl` and `prd.tfvars`. Never reuse one environment's initialized
working directory for another without `init -reconfigure`.

## Configure GitHub image publishing

Use the matching value from the bootstrap output
`github_image_publisher_role_arns` as an environment variable named
`AWS_GITHUB_OIDC_ROLE_ARN` in each GitHub environment. Each role is restricted
to that environment's exact OIDC subject and ECR repository. The ARN is an
identifier, not a credential. Do not configure AWS access-key secrets.

The manual **Publish image** workflow:

- runs only from `main`;
- selects `dev` or `prd` through a GitHub environment;
- receives short-lived AWS credentials through OIDC;
- builds the repository Dockerfile; and
- pushes `sha-<full Git commit SHA>` to the matching immutable ECR repository.

Rerunning the workflow for an already-published commit is safe: it detects the
existing immutable tag and skips the duplicate build and push.

The workflow becomes usable only after bootstrap, both platform applies, and
GitHub environment configuration are complete.
