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

## CodeBuild lifecycle executor

All DEV mutations run in the `integration-catalogue-dev-lifecycle` CodeBuild
project. EventBridge Scheduler and the local PowerShell remote control start the
same project with one of three operations: `activate`, `maintain`, or `update`.
The project clones reviewed `main`, downloads the pinned Terraform version after
verifying its published SHA-256 checksum, and accesses the existing runtime and
edge state objects in the protected S3 bucket.

The selected immutable image tag is stored in the standard SSM parameter
`/integration-catalogue/dev/image-tag`. `update` changes the parameter only
after ECS is stable on the corresponding ECR digest. A later activation reads
that same parameter, so no local tfvars file or deployment-tag PR is required.

The schedules use `Europe/Warsaw` and are configured as:

| Operation | Schedule |
| --- | --- |
| `activate` | 08:00, Monday-Friday |
| `maintain` | 18:00, Monday-Friday |

Terraform initially creates both schedules disabled. Enable them only after a
manual CodeBuild activation and maintenance test succeeds.

## Local remote control

`scripts/dev.ps1` verifies the exact AWS account, the `AccountFullAccessRole`
session, and `eu-north-1`. `status` reads AWS directly. Mutation commands ask
for one confirmation, start CodeBuild, wait for its terminal result, and then
display the resulting state. Terraform and Docker are not used locally.

Set the expected account locally and authenticate with `aws login`:

```powershell
$env:INTEGRATION_CATALOGUE_AWS_ACCOUNT_ID = "your-12-digit-account-id"
aws login
```

```powershell
.\scripts\dev.ps1
.\scripts\dev.ps1 status
.\scripts\dev.ps1 activate
.\scripts\dev.ps1 update -ImageTag sha-0123456789abcdef0123456789abcdef01234567
.\scripts\dev.ps1 maintain
```

- `status` is read-only and reports the combined edge/runtime state and stable
  CloudFront URL.
- `activate` starts CodeBuild, which applies the runtime, waits for ECS
  stability, and then activates the persistent edge.
- `update` requires an active runtime and an immutable image tag that already
  exists in ECR. CodeBuild applies only the runtime, waits for ECS stability,
  verifies the deployed digest, records the tag in SSM, and leaves CloudFront
  active.
- `maintain` starts CodeBuild, which deploys and waits for the maintenance edge
  before destroying the runtime and its CloudWatch application log group.

Manual and scheduled builds use identical lifecycle code. CodeBuild emits the
complete Terraform plans to its dedicated 14-day CloudWatch log group and
deletes local plan files when the build ends.

## Bootstrap lifecycle automation

The CodeBuild project cannot create itself. Provision
`infra/environments/dev-automation` once through the existing reviewed operator
Terraform process. This root has its own state key,
`automation/dev/terraform.tfstate`, and creates:

- the CodeBuild project and scoped service role;
- the SSM image-selection parameter;
- the EventBridge Scheduler group, disabled schedules, and execution role;
- a dedicated CloudWatch build log group with 14-day retention.

Copy its ignored configuration examples:

```powershell
Copy-Item infra/environments/dev-automation/backend.hcl.example infra/environments/dev-automation/backend.hcl
Copy-Item infra/environments/dev-automation/terraform.tfvars.example infra/environments/dev-automation/terraform.tfvars
```

Replace the state-bucket placeholders and set `initial_image_tag` to an existing
immutable ECR tag. Keep `schedules_enabled = false` for the first apply. Review
the plan, apply it, run one manual lifecycle round trip, and then change the
value to `true` in the ignored tfvars file and apply the automation root again.

Destroying this automation root removes CodeBuild, schedules, roles, logs, and
the SSM selector; it does not destroy the independently managed DEV edge or
runtime. Disable the schedules before maintenance on the automation itself.
