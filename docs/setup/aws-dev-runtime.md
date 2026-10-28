# AWS DEV runtime and persistent edge

DEV has one persistent CloudFront entry point and one disposable ECS/Fargate
runtime. Terraform keeps them in separate state objects so the runtime can be
destroyed without changing the public CloudFront hostname.

## Architecture

- `infra/environments/dev-edge` owns the persistent CloudFront distribution and
  its lifecycle function.
- `infra/environments/dev` owns the disposable VPC, public subnets, ALB, ECS
  service, IAM runtime roles, and application log group.
- CloudFront uses its AWS-managed HTTPS hostname and default certificate. A
  custom domain and ACM certificate are intentionally deferred.
- The ALB accepts HTTP only from the AWS-managed CloudFront origin-facing
  prefix list. It is not a direct public user endpoint.
- CloudFront disables caching and forwards all viewer headers, cookies, and
  query strings so Streamlit HTTP and WebSocket traffic reaches the runtime.
- Fargate tasks use public IPs for AuraDB and AWS API egress without a NAT
  Gateway. Task ingress is accepted only from the ALB security group.
- The immutable `sha-<full-commit-sha>` image is resolved to its ECR digest.

The application task role can invoke only the configured regional Bedrock
model. The execution role can pull the selected ECR image, write application
logs, and read the environment AuraDB secret.

## Two operational states

| State | Edge | Runtime | Cost profile |
| --- | --- | --- | --- |
| `active` | Forwards to the healthy ALB | Present, one Fargate task | CloudFront usage, ALB/public IPv4, Fargate, logs, secret, and transfer |
| `maintenance` | Returns a static HTTP 503 page at the edge | Absent | CloudFront function/request usage plus the separately managed secret |

There is no paused state. Entering maintenance updates and deploys CloudFront
before destroying the runtime. Entering active creates the runtime, waits for
ECS stability, then updates CloudFront with the new ALB DNS name. Interrupted
transitions are reported as incomplete and require review before continuing.

CloudFront and its function have no fixed hourly runtime charge; normal request
and transfer pricing and applicable free-tier allowances still apply. The ALB,
public IPv4 addresses, Fargate, and runtime log group disappear in maintenance.

## Secret contract

Create one DEV Secrets Manager secret in `eu-north-1` with JSON keys:

```json
{
  "NEO4J_URI": "neo4j+s://example.databases.neo4j.io",
  "NEO4J_USERNAME": "neo4j",
  "NEO4J_PASSWORD": "replace-outside-git"
}
```

Do not paste real values into Terraform, tfvars, terminal output, issues, or
agent chat. Terraform stores only the secret name and configures ECS to inject
the three fields. Secret rotation requires a new task deployment.

## Local lifecycle controller

`scripts/dev.ps1` verifies the exact AWS account, the
`AccountFullAccessRole` session, and `eu-north-1` before reading or changing
resources. Set the expected account locally and authenticate with `aws login`:

```powershell
$env:INTEGRATION_CATALOGUE_AWS_ACCOUNT_ID = "your-12-digit-account-id"
aws login
```

Terraform runs in the pinned Docker image. The AWS login cache is mounted
read-only and credentials are not printed, copied into the image, or stored in
Terraform state.

```powershell
.\scripts\dev.cmd
.\scripts\dev.cmd status
.\scripts\dev.cmd active
.\scripts\dev.cmd maintenance
```

- `status` is read-only and reports the combined edge/runtime state and stable
  CloudFront URL.
- `active` reviews and applies the runtime plan, waits for ECS stability, then
  separately reviews and applies the active edge plan.
- `maintenance` reviews and deploys the maintenance edge first, then separately
  reviews the runtime destroy plan.

Every mutation displays a saved Terraform plan and requires an exact
interactive confirmation. Plan files are deleted after success, cancellation,
or failure. Runtime destruction also removes its CloudWatch log group.

## Prepare local configuration

Copy the ignored configuration examples. Both roots use the same protected
state bucket but different keys:

```powershell
Copy-Item infra/environments/dev/backend.hcl.example infra/environments/dev/backend.hcl
Copy-Item infra/environments/dev-edge/backend.hcl.example infra/environments/dev-edge/backend.hcl
Copy-Item infra/environments/dev/terraform.tfvars.example infra/environments/dev/terraform.tfvars
```

Replace the state-bucket placeholder in both backend files and select an image
that already exists in ECR. The edge root requires no tfvars file: the lifecycle
controller passes the current ALB hostname and state explicitly.

Run `status`, then use `active` or `maintenance` and review every plan before
entering the displayed phrase. Use direct Terraform commands only for diagnosis
or recovery when the controller cannot safely classify the deployment.
