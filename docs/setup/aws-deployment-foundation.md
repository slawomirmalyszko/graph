# AWS deployment foundation

This guide prepares remote Terraform state, one shared ECR repository, and a
least-privilege GitHub image-publisher identity for the Integration Catalogue.
It creates no ECS, load-balancer, Cognito, networking, or continuously running
resources.

## Architecture

| Root | Responsibility | State |
| --- | --- | --- |
| `infra/bootstrap` | S3 state bucket and GitHub ECR publisher user/policy | Bootstrapped locally, then migrated to S3 |
| `infra/platform` | Shared immutable application image repository | Shared S3 state key |
| `infra/environments/dev` | DEV VPC, ALB, ECS/Fargate runtime, roles, and logs | Dedicated DEV S3 state key |

DEV and PRD will run the same commit-addressed image. Their runtime settings and
secrets remain environment-specific and are not baked into the image.

## Authentication exception

The simplified AWS project blocks creation of IAM OIDC providers. This demo
therefore uses one long-lived IAM access key for GitHub image publishing. Its
permissions are limited to obtaining an ECR authorization token and pushing to
the `integration-catalogue` repository. It cannot run Terraform, deploy ECS,
read runtime secrets, invoke Bedrock, or administer IAM.

The access key is deliberately not a Terraform resource: Terraform would store
its secret value in state. Create it manually only after reviewing and applying
the user and policy. Transfer the value directly from the AWS Console into the
protected GitHub environment; never paste it into source files, Terraform,
terminal history, issues, pull requests, or agent chat.

## Cost and cleanup

The IAM user and access key have no direct charge. The S3 bucket incurs small
storage/request charges for state versions. ECR incurs storage and transfer
charges for pushed image layers. Basic image scanning has no separate ECR
scanning charge; enhanced Inspector scanning is not enabled. No continuously
running compute is created.

Untagged ECR images expire after seven days. Cleanup order is:

1. Disable and delete the access key in IAM.
2. Remove both AWS secrets from the GitHub `image-publishing` environment.
3. Delete all repository images and destroy `infra/platform`.
4. Destroy the publisher policy and user from `infra/bootstrap`.
5. Retain the state bucket unless all Terraform state is intentionally retired.

The state bucket uses `prevent_destroy` and `force_destroy = false`. Removing it
requires an offline state backup, deletion of all object versions, and an
intentional temporary removal of the Terraform deletion guard.

## Validate locally without AWS access

```powershell
terraform fmt -check -recursive infra
terraform -chdir=infra/bootstrap init -backend=false
terraform -chdir=infra/bootstrap validate
terraform -chdir=infra/platform init -backend=false
terraform -chdir=infra/platform validate
terraform -chdir=infra/environments/dev init -backend=false
terraform -chdir=infra/environments/dev validate
```

Provider installation may access the Terraform registry but these validation
commands do not read or mutate the AWS account.

## Bootstrap remote state and publisher identity

Before every AWS operation, verify the expected caller identity and Stockholm
access through AWS MCP. Copy the ignored inputs and choose a globally unique
bucket name plus an expiry no more than 180 days after the planned apply:

```powershell
Copy-Item infra/bootstrap/terraform.tfvars.example infra/bootstrap/terraform.tfvars
terraform -chdir=infra/bootstrap init -backend=false
terraform -chdir=infra/bootstrap plan -out bootstrap.tfplan
terraform -chdir=infra/bootstrap apply bootstrap.tfplan
```

No access key exists after this apply. The first apply uses local state because
the S3 bucket cannot be its own backend before it exists. Copy both backend
examples to their ignored local names, insert the created bucket name, and then
migrate bootstrap state:

```powershell
Copy-Item infra/bootstrap/backend.hcl.example infra/bootstrap/backend.hcl
Copy-Item infra/bootstrap/backend_override.tf.example infra/bootstrap/backend_override.tf
terraform -chdir=infra/bootstrap init -migrate-state -backend-config=backend.hcl
```

Confirm the migration before deleting any local state file.

## Create the shared ECR repository

Copy `infra/platform/backend.hcl.example` to the ignored `backend.hcl`, insert
the state bucket name, and apply the reviewed plan:

```powershell
Copy-Item infra/platform/backend.hcl.example infra/platform/backend.hcl
terraform -chdir=infra/platform init -reconfigure -backend-config=backend.hcl
terraform -chdir=infra/platform plan -out platform.tfplan
terraform -chdir=infra/platform apply platform.tfplan
```

The repository is shared by DEV and PRD and accepts immutable
`sha-<full-commit-sha>` image tags.

## Create and store the publisher access key

After the IAM user and ECR repository exist:

1. In AWS Console, open **IAM -> Users -> integration-catalogue-github-ecr-publisher**.
2. Open **Security credentials -> Create access key**.
3. Select the third-party service use case and acknowledge the recommendation.
4. In GitHub, create an environment named `image-publishing` restricted to the
   `main` branch. Add approval protection if supported by the repository plan.
5. Add `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` as environment secrets.
6. Delete the downloaded credential file after the two values are stored and
   verified. Do not retain a plaintext backup.

The secret access key is shown only once. Neither Codex nor Terraform should
create, retrieve, display, or store it.

## Publish and rotate

The manual **Publish image** workflow runs only from `main`, builds the root
Dockerfile, and pushes `sha-<full-commit-sha>`. It first checks whether the
immutable tag already exists, making a rerun safe.

Before the policy expiry:

1. Create a second access key for the same user.
2. Replace both GitHub environment secrets with the new pair.
3. Run **Publish image** for a commit that has not yet been published.
4. Disable the old key and confirm publishing still works.
5. Delete the old key.
6. Move `publisher_access_expires_at` forward by no more than 180 days through a
   reviewed Terraform change.

If compromise is suspected, disable the key immediately, remove the GitHub
secrets, inspect CloudTrail and ECR image history, and do not deploy unverified
tags.
