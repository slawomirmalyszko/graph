# External account bootstrap

Account creation contains manual identity, billing, and terms-of-service steps.
Do not put tokens, passwords, downloaded credential files, or connection strings
in this repository.

## Recommended order

1. Harden the GitHub repository and enable the baseline CI workflow.
2. Create and secure the AWS account; configure cost controls before workloads.
3. Create one free Neo4j AuraDB instance and record only secret *names* in Git.
4. Create the Kong environment after the canonical interface model begins.
5. Create Solace after Kong, unless the first vertical slice is deliberately
   changed to event-driven discovery.

This order prevents expiring product trials while foundational design is still
underway.

## GitHub checklist

- [ ] Confirm `main` is the default branch.
- [ ] Enable branch protection/ruleset for `main`.
- [ ] Require the `test` status check before merge.
- [ ] Require pull requests and prevent force pushes to `main`.
- [ ] Enable Dependabot alerts and secret scanning where available.
- [ ] Confirm GitHub Actions has read-only default repository permissions.
- [ ] Use GitHub Environments for later deployment separation.
- [ ] Use GitHub OIDC for AWS; do not create long-lived AWS access keys.

## AWS account checklist

- [ ] Create a dedicated learning-project account, not a corporate account.
- [ ] Protect the root user with a unique password and MFA.
- [ ] Do not create root access keys.
- [ ] Choose a home region after checking Bedrock model availability.
- [ ] Create a small budget and multiple cost alerts before provisioning.
- [ ] Enable Free Tier and billing alerts.
- [ ] Use IAM Identity Center or another administrative identity for daily use.
- [ ] Later create a narrowly scoped GitHub Actions OIDC role.
- [ ] Record the account ID and region in a local uncommitted `.env`, never here.

The AWS free-plan and service access rules change over time. Verify the selected
plan's duration, credit limits, Bedrock access, and permitted services during
signup.

## Neo4j AuraDB checklist

- [ ] Create an Aura account and one free AuraDB instance.
- [ ] Select a region close to the intended AWS home region when possible.
- [ ] Download or securely save the generated password immediately.
- [ ] Store the URI, username, and password outside Git.
- [ ] Verify connection from Neo4j Browser before writing an extractor.
- [ ] Do not load synthetic data until graph constraints and IDs are defined.

One free Aura instance per account is currently documented, so the initial
environment should remain intentionally simple.

## Kong checklist

- [ ] Delay starting a time-limited Konnect trial until its extractor work begins.
- [ ] Decide between Konnect trial and local containerized Kong Gateway.
- [ ] If using Konnect, create a dedicated system-account token for automation
      when supported; use a personal token only for initial exploration.
- [ ] Store all tokens outside Git and plan their rotation.
- [ ] Create synthetic services, routes, consumers, and OpenAPI specifications.
- [ ] Confirm the management APIs expose the metadata needed by the extractor.

A local Kong container is reproducible and does not expire; Konnect demonstrates
a realistic managed control-plane API. This choice should be made immediately
before the Kong vertical slice.

## Solace connectivity check

The manually triggered `Test Solace connectivity` workflow publishes one JSON
message with MQTT QoS 1 to the `test/github/actions` topic over secure
WebSockets (WSS).

Create a GitHub environment named `development`, then add these environment
secrets:

- `SOLACE_WSS_URL`: the secured MQTT WebSocket URI (`wss://...`) copied from the
  service's **Connect > MQTT** details
- `SOLACE_USERNAME`: a dedicated, enabled messaging client username
- `SOLACE_PASSWORD`: that messaging client's password

The client ACL must allow publishing to `test/github/actions`. Run the check
from **Actions > Test Solace connectivity > Run workflow**. A successful run
prints only a confirmation; credentials are never written to the log.
