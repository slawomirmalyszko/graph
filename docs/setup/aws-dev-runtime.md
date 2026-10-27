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
agent chat. Terraform receives only the secret ARN and ECS resolves the three
keys when a task starts. Secret rotation requires a new task deployment.

## Cost boundary

`desired_count = 0` stops Fargate task compute but does not delete the ALB, VPC,
CloudWatch log group, or Secrets Manager secret. The ALB has an hourly charge
while provisioned. Fargate compute, CloudWatch ingestion/storage, Secrets
Manager, and data transfer can add usage charges when DEV runs.

Container Insights is disabled initially to avoid additional observability cost.
The design avoids NAT Gateway hourly charges. Destroying the DEV Terraform root
removes the ALB, ECS, VPC, roles, and log group; it does not remove the shared
ECR repository or the externally managed AuraDB secret.

## Prepare and validate

Copy the ignored configuration examples and replace placeholders locally:

```powershell
Copy-Item infra/environments/dev/backend.hcl.example infra/environments/dev/backend.hcl
Copy-Item infra/environments/dev/terraform.tfvars.example infra/environments/dev/terraform.tfvars
terraform -chdir=infra/environments/dev init -reconfigure -backend-config=backend.hcl
terraform -chdir=infra/environments/dev plan -out dev.tfplan
```

Review the complete plan before apply. Applying with `desired_count = 0` creates
the runtime foundation but starts no application task. Change the value to `1`
and apply a reviewed plan to start DEV; return it to `0` to stop task compute.

Cleanup, when explicitly intended:

```powershell
terraform -chdir=infra/environments/dev plan -destroy -out dev-destroy.tfplan
terraform -chdir=infra/environments/dev apply dev-destroy.tfplan
```
