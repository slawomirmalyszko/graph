# AWS DEV runtime

The DEV runtime runs the immutable Integration Catalogue image from the shared
ECR repository on ECS Fargate. Terraform state is separate from shared platform
state and will also remain separate from the future PRD runtime.

## Architecture and access

- One environment VPC spans two public subnets in separate availability zones.
- An internet-facing ALB exposes temporary HTTP access only to explicitly
  configured public CIDRs.
- Fargate tasks receive public IPs to reach AuraDB and AWS APIs without a NAT
  Gateway. Their security group accepts inbound traffic only from the ALB.
- The ECS execution role pulls the selected ECR image, writes to the environment
  log group, and injects one environment-specific AuraDB secret.
- The application task role can invoke only the configured regional Bedrock
  foundation model.
- The image tag must be `sha-<full-commit-sha>` and already exist in ECR.
  Terraform resolves it to its digest, and ECS runs that exact artifact.

This HTTP endpoint is an interim DEV mechanism. It is not suitable for public
PRD access or Cognito authentication. HTTPS, a stable domain, and Cognito remain
separate follow-up increments.

## Secret contract

Create one DEV Secrets Manager secret manually in `eu-north-1` with JSON keys:

```json
{
  "NEO4J_URI": "neo4j+s://example.databases.neo4j.io",
  "NEO4J_USERNAME": "neo4j",
  "NEO4J_PASSWORD": "replace-outside-git"
}
```

Do not paste the real values into Terraform, tfvars, terminal output, issues, or
agent chat. Terraform receives only the stable secret name, resolves its ARN,
and configures ECS to inject the three keys when a task starts. Secret rotation
requires a new task deployment.

## Cost boundary

`desired_count = 0` stops Fargate task compute but does not delete the ALB, VPC,
CloudWatch log group, or Secrets Manager secret. The ALB has an hourly charge
while provisioned. Fargate compute, CloudWatch ingestion/storage, Secrets
Manager, and data transfer can add usage charges when DEV runs.

Container Insights is disabled initially to avoid additional observability cost.
The design avoids NAT Gateway hourly charges. Destroying the DEV Terraform root
removes the ALB, ECS, VPC, roles, and log group; it does not remove the shared
ECR repository or the externally managed AuraDB secret.

## Local lifecycle controller

Use `scripts/dev.ps1` to operate DEV without handling Terraform commands or
plan files manually. The controller always verifies the exact AWS account, the
`AccountFullAccessRole` session, and `eu-north-1` before it reads or changes the
runtime. The expected account ID is local configuration and must not be written
to the repository:

```powershell
$env:INTEGRATION_CATALOGUE_AWS_ACCOUNT_ID = "your-12-digit-account-id"
```

Authenticate with `aws login` before using the controller. Terraform runs in
the pinned Docker image and receives the AWS login cache through a read-only
mount. Credentials are not printed, copied into the image, or stored in state.

```powershell
.\scripts\dev.cmd
.\scripts\dev.cmd status
.\scripts\dev.cmd start
.\scripts\dev.cmd stop
.\scripts\dev.cmd hibernate
```

The wrapper launches `dev.ps1` with process-scoped `-ExecutionPolicy Bypass`.
It does not change the user or machine execution policy.
Running it without a command displays its commands, DEV states, prerequisites,
confirmation phrases, and examples without making an AWS request.

- `status` performs read-only AWS checks and reports `running`, `paused`,
  `hibernated`, or `incomplete`.
- `start` sets the ignored local `desired_count` to `1`. It starts a paused
  service or recreates a hibernated DEV root.
- `stop` sets `desired_count` to `0`. It stops Fargate task compute while
  retaining the ALB and its public IPv4 addresses for a fast restart.
- `hibernate` destroys the DEV Terraform root. Shared ECR, remote state,
  AuraDB, and the externally managed Secrets Manager secret remain. The next
  `start` recreates DEV with a new temporary ALB hostname.

Every mutation writes and displays a saved Terraform plan, then requires an
exact interactive confirmation before applying it. Plan files are deleted after
success, cancellation, or failure. `hibernate` also removes the DEV CloudWatch
log group, so preserve required logs before confirming it.

## Prepare and validate

Copy the ignored configuration examples and replace placeholders locally:

```powershell
Copy-Item infra/environments/dev/backend.hcl.example infra/environments/dev/backend.hcl
Copy-Item infra/environments/dev/terraform.tfvars.example infra/environments/dev/terraform.tfvars
.\scripts\dev.cmd status
```

Run `start`, `stop`, or `hibernate` and review the complete plan before entering
the displayed confirmation phrase. Use direct Terraform commands only for
diagnosis or recovery when the controller cannot safely classify the runtime.
