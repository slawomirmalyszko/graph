#!/usr/bin/env bash
set -euo pipefail

operation="${1:-}"
requested_image_tag="${2:-}"
region="${AWS_REGION:?AWS_REGION is required}"
expected_account_id="${EXPECTED_AWS_ACCOUNT_ID:?EXPECTED_AWS_ACCOUNT_ID is required}"
state_bucket="${TF_STATE_BUCKET:?TF_STATE_BUCKET is required}"
image_parameter_name="${DEV_IMAGE_PARAMETER_NAME:?DEV_IMAGE_PARAMETER_NAME is required}"
repository_name="${ECR_REPOSITORY_NAME:-integration-catalogue}"
cluster_name="${ECS_CLUSTER_NAME:-integration-catalogue-dev}"
service_name="${ECS_SERVICE_NAME:-integration-catalogue-dev}"
load_balancer_name="${LOAD_BALANCER_NAME:-integration-catalogue-dev}"
runtime_directory="/workspace/infra/environments/dev"
edge_directory="/workspace/infra/environments/dev-edge"

runtime_plan="${runtime_directory}/dev-lifecycle.tfplan"
edge_plan="${edge_directory}/dev-lifecycle.tfplan"

cleanup() {
  rm -f "$runtime_plan" "$edge_plan"
}
trap cleanup EXIT

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "Required command '$1' is unavailable."
}

require_command aws
require_command terraform

identity_account="$(aws sts get-caller-identity --region "$region" --query Account --output text)"
identity_arn="$(aws sts get-caller-identity --region "$region" --query Arn --output text)"
[[ "$identity_account" == "$expected_account_id" ]] || fail "AWS account mismatch."
[[ "$identity_arn" == *":assumed-role/integration-catalogue-dev-lifecycle-codebuild/"* ]] \
  || fail "Unexpected AWS role for DEV lifecycle automation."
echo "AWS identity verified: account ending ${identity_account: -4}, CodeBuild lifecycle role, region ${region}."

validate_image_tag() {
  local tag="$1"
  [[ "$tag" =~ ^sha-[0-9a-f]{40}$ ]] \
    || fail "Image tag must use sha-<40 lowercase hexadecimal characters>."
}

current_image_tag() {
  local tag
  tag="$(aws ssm get-parameter \
    --name "$image_parameter_name" \
    --region "$region" \
    --query Parameter.Value \
    --output text)"
  validate_image_tag "$tag"
  printf '%s' "$tag"
}

image_digest() {
  local tag="$1"
  local digest
  digest="$(aws ecr describe-images \
    --repository-name "$repository_name" \
    --image-ids "imageTag=${tag}" \
    --region "$region" \
    --query 'imageDetails[0].imageDigest' \
    --output text)"
  [[ "$digest" =~ ^sha256:[0-9a-f]{64}$ ]] \
    || fail "ECR image '${repository_name}:${tag}' does not exist or has no valid digest."
  printf '%s' "$digest"
}

terraform_init() {
  local directory="$1"
  local state_key="$2"
  terraform -chdir="$directory" init \
    -reconfigure \
    -input=false \
    -no-color \
    -backend-config="bucket=${state_bucket}" \
    -backend-config="key=${state_key}" \
    -backend-config="region=${region}" \
    -backend-config="use_lockfile=true"
}

terraform_apply() {
  local directory="$1"
  local plan="$2"
  shift 2
  terraform -chdir="$directory" plan \
    -input=false \
    -no-color \
    -out="$(basename "$plan")" \
    "$@"
  terraform -chdir="$directory" apply -input=false -no-color "$(basename "$plan")"
}

terraform_destroy() {
  local directory="$1"
  local plan="$2"
  shift 2
  terraform -chdir="$directory" plan \
    -destroy \
    -input=false \
    -no-color \
    -out="$(basename "$plan")" \
    "$@"
  terraform -chdir="$directory" apply -input=false -no-color "$(basename "$plan")"
}

wait_for_runtime() {
  echo "Waiting for ECS service stability..."
  aws ecs wait services-stable \
    --cluster "$cluster_name" \
    --services "$service_name" \
    --region "$region"
}

wait_for_edge() {
  local distribution_id
  distribution_id="$(terraform -chdir="$edge_directory" output -raw distribution_id)"
  echo "Waiting for CloudFront distribution ${distribution_id}..."
  aws cloudfront wait distribution-deployed --id "$distribution_id"
}

runtime_origin() {
  aws elbv2 describe-load-balancers \
    --region "$region" \
    --query "LoadBalancers[?LoadBalancerName=='${load_balancer_name}'].DNSName | [0]" \
    --output text
}

activate() {
  local tag origin
  tag="$(current_image_tag)"
  image_digest "$tag" >/dev/null
  echo "Activating DEV with immutable image ${tag}."

  terraform_init "$runtime_directory" "runtime/dev/terraform.tfstate"
  terraform_apply "$runtime_directory" "$runtime_plan" \
    -var="image_tag=${tag}" \
    -var="desired_count=1"
  wait_for_runtime

  origin="$(runtime_origin)"
  [[ -n "$origin" && "$origin" != "None" ]] || fail "DEV load balancer was not found after runtime apply."
  terraform_init "$edge_directory" "edge/dev/terraform.tfstate"
  terraform_apply "$edge_directory" "$edge_plan" \
    -var="maintenance_mode=false" \
    -var="origin_domain_name=${origin}"
  wait_for_edge
  echo "DEV lifecycle operation completed: active"
}

maintain() {
  local tag origin
  tag="$(current_image_tag)"
  origin="$(runtime_origin)"
  if [[ -z "$origin" || "$origin" == "None" ]]; then
    origin="maintenance.invalid"
  fi
  echo "Switching the persistent DEV edge to maintenance."

  terraform_init "$edge_directory" "edge/dev/terraform.tfstate"
  terraform_apply "$edge_directory" "$edge_plan" \
    -var="maintenance_mode=true" \
    -var="origin_domain_name=${origin}"
  wait_for_edge

  terraform_init "$runtime_directory" "runtime/dev/terraform.tfstate"
  terraform_destroy "$runtime_directory" "$runtime_plan" \
    -var="image_tag=${tag}" \
    -var="desired_count=1"
  echo "DEV lifecycle operation completed: maintenance"
}

update() {
  local expected_digest task_definition_arn deployed_image deployed_digest
  validate_image_tag "$requested_image_tag"
  expected_digest="$(image_digest "$requested_image_tag")"
  echo "Updating active DEV to immutable image ${requested_image_tag}."

  # JMESPath backticks are literal syntax, not shell command substitution.
  # shellcheck disable=SC2016
  aws ecs describe-services \
    --cluster "$cluster_name" \
    --services "$service_name" \
    --region "$region" \
    --query 'services[?status==`ACTIVE`] | length(@)' \
    --output text | grep -qx '1' \
    || fail "DEV must be active before an in-place image update."

  terraform_init "$runtime_directory" "runtime/dev/terraform.tfstate"
  terraform_apply "$runtime_directory" "$runtime_plan" \
    -var="image_tag=${requested_image_tag}" \
    -var="desired_count=1"
  wait_for_runtime

  task_definition_arn="$(aws ecs describe-services \
    --cluster "$cluster_name" \
    --services "$service_name" \
    --region "$region" \
    --query 'services[0].taskDefinition' \
    --output text)"
  deployed_image="$(aws ecs describe-task-definition \
    --task-definition "$task_definition_arn" \
    --region "$region" \
    --query 'taskDefinition.containerDefinitions[0].image' \
    --output text)"
  deployed_digest="${deployed_image##*@}"
  [[ "$deployed_digest" == "$expected_digest" ]] \
    || fail "ECS stabilized without the digest referenced by the requested image tag."

  aws ssm put-parameter \
    --name "$image_parameter_name" \
    --type String \
    --value "$requested_image_tag" \
    --overwrite \
    --region "$region" >/dev/null
  echo "DEV lifecycle operation completed: image ${requested_image_tag}"
}

case "$operation" in
  activate) activate ;;
  maintain) maintain ;;
  update) update ;;
  *) fail "Unsupported DEV lifecycle operation '${operation}'." ;;
esac
