# Agent instructions

These instructions apply to the entire repository.

## AWS working context

- AWS project display name: `Integration Catalogue`.
- Account type: AWS new experience, Free Plan.
- Home and resource region: Europe (Stockholm), `eu-north-1`.
- Do not substitute Frankfurt (`eu-central-1`) or use multiple regions unless a
  documented requirement explicitly changes this decision.
- The project region is fixed by the new AWS experience. Confirm that every
  proposed regional service and Bedrock model is available in `eu-north-1`.
- Do not commit AWS account IDs, credentials, access tokens, connection strings,
  or downloaded credential files.

## AWS access style

- Prefer the official AWS MCP server for AWS discovery, read operations, and
  resource changes. Use its sandboxed AWS API execution rather than shelling out
  to the AWS CLI.
- At the beginning of AWS work, verify access with a read-only STS caller
  identity request and confirm regional access in `eu-north-1`.
- The expected session uses an assumed role. Never retrieve, print, request, or
  persist underlying credentials.
- Start with read-only discovery. Before a resource mutation, explain the
  intended resource, region, estimated cost implications, and rollback or
  deletion path.
- Do not create chargeable resources merely to test connectivity.
- Use local `aws login` only when local CLI/SDK credentials are actually needed.
  It requires AWS CLI 2.32 or later and explicit user confirmation. Prefer its
  short-lived credentials over long-lived access keys.
- GitHub Actions normally authenticate to AWS using OIDC and a narrowly scoped
  IAM role. The simplified AWS project blocks IAM OIDC-provider creation, so
  this repository permits one documented exception: a non-console IAM user's
  long-lived key may be stored only in the protected `image-publishing` GitHub
  environment and may grant only ECR image-push access to the project registry.
  The key must expire or rotate within 180 days and must never receive Terraform,
  ECS deployment, Bedrock, Secrets Manager, S3, or IAM permissions.
- Store runtime application secrets in AWS Secrets Manager when introduced;
  repository files contain only secret names and configuration examples.

## Delivery workflow

- Make repository changes on a focused branch.
- Run relevant local tests and lint checks.
- After making and validating changes, stop and present the diff and repository
  status for review. Wait for the user to explicitly say `commit` before
  committing, pushing, creating or merging a pull request, cleaning up the
  branch, or synchronizing local `main`.
- Commit and push the branch, create a pull request, and wait for GitHub Actions.
- Merge only after required checks pass.
- Record consequential AWS architecture choices in `docs/decisions.md`.
- Update `docs/setup/aws-agent-workflow.md` when the AWS operating procedure
  changes.
