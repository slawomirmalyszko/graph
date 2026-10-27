# Architecture decisions and open questions

This lightweight log records decisions made before formal ADRs are warranted.

## Accepted

### AWS home region

The project uses Europe (Stockholm), `eu-north-1`, as its AWS home region.
The new AWS experience assigns European Free Plan projects to this region and
does not allow their project region to be changed. Region-dependent service and
Bedrock model availability must still be verified before implementation.

### Core graph path

An end-to-end flow starts and ends at an `Application` and can traverse other
applications:

```text
(Application)-[:EXPOSES]->(Interface)-[:SOURCE_OF]->(Integration)
  -[:TARGETS]->(Interface)<-[:USES]-(Application)
```

Consecutive integration hops connect through shared Interface nodes. An
end-to-end flow is a traversed path between Application nodes; `flow_id` and
`sequence` properties do not create topology.

### Core node concepts

- `Application`
- `Interface`
- `Integration`
- `InformationObject`

`Interface` abstracts technology-specific concepts such as APIs, events, topics,
queues, and file endpoints. A defined type property and/or additional labels will
retain their concrete meaning.

An `Integration` connects exactly two interfaces: one incoming `SOURCE_OF` and
one outgoing `TARGETS`. Applications, interfaces, and information objects may
participate in multiple relationships.

### Application minimum attributes

- `apm_id`
- `name`
- `status`: one of `planned`, `active`, `deprecated`, `decommissioning`,
  `decommissioned`, or `unknown`

### Canonical property policy

Each canonical node type will define:

- Required properties.
- Optional but formally defined properties.
- Additional source-specific properties.

Additional source properties use `x_<source>_<property>` names and must contain
Neo4j-compatible scalar values or lists of scalar values. The complete contract
is defined in `schema/catalogue-schema.yaml`.

### Platform representation

Platform is metadata on an Integration, represented by required
`platform_apm_id`. It references the ServiceNow APM ID of an Application master
record whose role is `integration_platform` or `both`. Platform is not a graph
node and does not participate in end-to-end topology.

### Query approach

The first version uses focused natural-language-to-Cypher generation rather than
a general autonomous agent. Prompts include selected schema context, worked
NL-to-Cypher examples, and initially a bounded application list or lookup context.

### Bedrock text-generation adapter

The first NL-to-Cypher implementation uses the Amazon Bedrock Converse API with
Amazon Nova Lite (`amazon.nova-lite-v1:0`) directly in `eu-north-1`. Direct
regional invocation avoids cross-region routing. The model remains configurable
for evaluation, but the AWS region is fixed to Stockholm. The adapter uses the
standard boto3 credential chain, adaptive retries, explicit timeouts, and an
explicit output-token limit. Credentials are never application configuration.

### AWS workload authentication

Local development uses `aws login` short-lived, auto-rotating credentials through
the standard boto3 credential chain. Deployed AWS workloads will use runtime IAM
roles. GitHub Actions normally uses OIDC, but the simplified project blocks IAM
OIDC-provider creation. The ECR-only, expiring publisher exception is documented
under AWS deployment foundation below. Long-lived keys are not used by the
application, Terraform, deployment automation, or any other CI/CD permission.

### AWS deployment foundation

AWS infrastructure is defined with Terraform and split into two roots:

- `infra/bootstrap` owns the S3 remote-state bucket and narrowly scoped GitHub
  ECR publisher identity.
- `infra/platform` initially owns the shared application image repository. DEV
  and PRD runtime resources will use separate state objects when introduced.

Terraform uses native S3 lock files rather than the deprecated DynamoDB locking
mechanism. The state bucket has versioning, encryption, blocked public access,
TLS-only access, and deletion protection.

The simplified AWS project applies an AWS-managed policy that blocks creation of
the GitHub IAM OIDC provider. For this demo account only, GitHub Actions uses a
dedicated non-console IAM user's long-lived access key from the protected
`image-publishing` GitHub environment. The user can obtain an ECR authorization
token and push only to the project repository. It cannot deploy infrastructure
or ECS services and has no Bedrock, Secrets Manager, S3, or IAM permissions.
Its policy has a UTC expiry and the key must rotate within 180 days. The key is
created manually, never by Terraform, so its secret is absent from state.

This is a constrained-account exception, not the target corporate pattern.
OIDC and temporary credentials remain preferred whenever the account permits
them. Images use immutable commit-SHA tags and one shared repository so DEV and
PRD promote the same artifact rather than rebuilding it.

The ECR repository uses immutable tags, basic scan-on-push, AES-256 encryption,
and automatic expiry of untagged images. Basic scanning is selected initially
to avoid Amazon Inspector enhanced-scanning cost.

### Container vulnerability gate

The application container pins the Python base image by digest and removes build
package-management tools from the runtime after dependency installation. GitHub
Actions builds and scans the exact local image with Trivy before publishing it.
The workflow fails for fixable HIGH or CRITICAL OS or Python vulnerabilities;
an image that fails the gate is not pushed to ECR.

Unfixed distribution findings remain recorded by ECR scanning and in this
decision; the blocking CI scan excludes them because no remediation is yet
available. The initial accepted findings affect Debian utilities that the
non-root application does not invoke, and the image runs without elevated
privileges. Dependabot monitors the pinned base digest and workflow actions
weekly so upstream remediations can be adopted by a normal reviewed pull
request.

## Open

### Identity resolution

Automatic matching will use deterministic and later probabilistic evidence.
Unresolved mappings require human review. Git is the system of record for
reviewed rules and mappings; the graph contains their projected relationships.

The mapping file format, confidence model, and review workflow remain open.

### Information-object evidence

Define which evidence establishes that an interface or integration carries an
information object: naming, tags, descriptions, message schemas, manual mapping,
or semantic inference.
