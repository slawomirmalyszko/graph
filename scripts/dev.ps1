[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet("help", "status", "active", "maintenance")]
    [string]$Command = "help",
    [ValidatePattern("^\d{12}$")]
    [string]$ExpectedAccountId = $env:INTEGRATION_CATALOGUE_AWS_ACCOUNT_ID
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$AwsRegion = "eu-north-1"
$ExpectedRoleName = "AccountFullAccessRole"
$TerraformImage = "hashicorp/terraform:1.17.0"
$ClusterName = "integration-catalogue-dev"
$ServiceName = "integration-catalogue-dev"
$LoadBalancerName = "integration-catalogue-dev"
$EdgeCommentPrefix = "integration-catalogue-dev-"
$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$RuntimeTerraformDirectory = Join-Path $RepositoryRoot "infra\environments\dev"
$EdgeTerraformDirectory = Join-Path $RepositoryRoot "infra\environments\dev-edge"
$RuntimeVariablesPath = Join-Path $RuntimeTerraformDirectory "terraform.tfvars"
$RuntimeBackendPath = Join-Path $RuntimeTerraformDirectory "backend.hcl"
$EdgeBackendPath = Join-Path $EdgeTerraformDirectory "backend.hcl"
$AwsConfigurationDirectory = Join-Path $env:USERPROFILE ".aws"
$AwsLoginCacheDirectory = Join-Path $AwsConfigurationDirectory "login\cache"

function Show-Usage {
    @"
Integration Catalogue DEV lifecycle controller

Usage:
  .\scripts\dev.cmd <command>

Commands:
  status        Show the live DEV state and active cost profile. Read-only.
  active        Create the runtime, wait for health, then route CloudFront to it.
  maintenance   Serve the edge maintenance page, then destroy the runtime.
  help          Show this help.

Operational states:
  active        Persistent CloudFront forwards HTTPS traffic to the healthy DEV runtime.
  maintenance   Persistent CloudFront serves a maintenance page; DEV runtime is absent.

Safety:
  active requires separate reviewed runtime and edge Terraform confirmations.
  maintenance switches the edge first, then requires runtime-destroy confirmation.

Prerequisites:
  1. Docker Desktop and AWS CLI are installed.
  2. Run: aws login
  3. Set INTEGRATION_CATALOGUE_AWS_ACCOUNT_ID in the current shell.
  4. Configure ignored backend.hcl files for dev and dev-edge.
  5. Configure ignored infra/environments/dev/terraform.tfvars.

Examples:
  .\scripts\dev.cmd status
  .\scripts\dev.cmd active
  .\scripts\dev.cmd maintenance

No command defaults to this help and performs no AWS operation.
"@ | Write-Host
}

function Assert-CommandAvailable {
    param([Parameter(Mandatory = $true)][string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' is unavailable."
    }
}

function Get-BackendSetting {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Name
    )
    $Content = Get-Content -Raw -LiteralPath $Path
    $Match = [regex]::Match(
        $Content,
        "(?m)^$([regex]::Escape($Name))\s*=\s*`"([^`"]+)`"\s*$"
    )
    if (-not $Match.Success) {
        throw "Backend configuration '$Path' must define '$Name'."
    }
    return $Match.Groups[1].Value
}

function Assert-LocalConfiguration {
    if ([string]::IsNullOrWhiteSpace($ExpectedAccountId)) {
        throw "Expected AWS account ID is required. Set INTEGRATION_CATALOGUE_AWS_ACCOUNT_ID locally or pass -ExpectedAccountId."
    }
    foreach ($Path in @($RuntimeVariablesPath, $RuntimeBackendPath, $EdgeBackendPath)) {
        if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
            throw "Missing ignored configuration: $Path"
        }
    }
    if (-not (Test-Path -LiteralPath $AwsLoginCacheDirectory -PathType Container)) {
        throw "AWS login cache is unavailable. Run 'aws login' and retry."
    }

    $RuntimeBucket = Get-BackendSetting -Path $RuntimeBackendPath -Name "bucket"
    $EdgeBucket = Get-BackendSetting -Path $EdgeBackendPath -Name "bucket"
    if ($EdgeBucket -eq "replace-with-bootstrap-state-bucket") {
        throw (
            "DEV edge backend still contains the example bucket placeholder. " +
            "Use the same bucket as infra/environments/dev/backend.hcl."
        )
    }
    if ($EdgeBucket -ne $RuntimeBucket) {
        throw "DEV runtime and edge backends must use the same protected state bucket."
    }

    $RuntimeKey = Get-BackendSetting -Path $RuntimeBackendPath -Name "key"
    $EdgeKey = Get-BackendSetting -Path $EdgeBackendPath -Name "key"
    if ($RuntimeKey -ne "runtime/dev/terraform.tfstate") {
        throw "DEV runtime backend key must be runtime/dev/terraform.tfstate."
    }
    if ($EdgeKey -ne "edge/dev/terraform.tfstate") {
        throw "DEV edge backend key must be edge/dev/terraform.tfstate."
    }
}

function Invoke-AwsJson {
    param(
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [switch]$AllowEmpty
    )
    $PreviousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $Output = & aws @Arguments 2>&1
        $ExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $PreviousErrorActionPreference
    }
    if ($ExitCode -ne 0) {
        $Operation = ($Arguments | Select-Object -First 2) -join " "
        throw "AWS CLI operation '$Operation' failed with exit code $ExitCode."
    }
    if ([string]::IsNullOrWhiteSpace(($Output -join ""))) {
        if ($AllowEmpty) {
            return $null
        }
        $Operation = ($Arguments | Select-Object -First 2) -join " "
        throw "AWS CLI operation '$Operation' returned no JSON output."
    }
    return ($Output | ConvertFrom-Json)
}

function Assert-AwsIdentity {
    Assert-CommandAvailable -Name "aws"
    try {
        $Identity = Invoke-AwsJson -Arguments @("sts", "get-caller-identity", "--region", $AwsRegion, "--output", "json")
    }
    catch {
        throw "AWS authentication is unavailable or expired. Run 'aws login' and retry."
    }
    if ($Identity.Account -ne $ExpectedAccountId) {
        throw "AWS account mismatch. Refusing to operate on the selected account."
    }
    if ($Identity.Arn -notmatch "/$([regex]::Escape($ExpectedRoleName))/") {
        throw "AWS role mismatch. Expected an assumed $ExpectedRoleName session."
    }
    $AccountSuffix = $Identity.Account.Substring($Identity.Account.Length - 4)
    Write-Host "AWS identity verified: account ending $AccountSuffix, role $ExpectedRoleName, region $AwsRegion."
}

function Get-DevRuntimeStatus {
    $Clusters = Invoke-AwsJson -Arguments @("ecs", "list-clusters", "--region", $AwsRegion, "--output", "json")
    $ClusterArn = @($Clusters.clusterArns) | Where-Object { $_ -match "/$([regex]::Escape($ClusterName))$" } | Select-Object -First 1
    $Service = $null
    if ($null -ne $ClusterArn) {
        $Service = Invoke-AwsJson -Arguments @("ecs", "describe-services", "--cluster", $ClusterArn, "--services", $ServiceName, "--region", $AwsRegion, "--output", "json")
    }
    $LoadBalancers = Invoke-AwsJson -Arguments @("elbv2", "describe-load-balancers", "--region", $AwsRegion, "--output", "json")
    $ServiceRecord = $null
    if ($null -ne $Service -and @($Service.services).Count -gt 0) {
        $Candidate = @($Service.services)[0]
        if ($Candidate.status -ne "INACTIVE") { $ServiceRecord = $Candidate }
    }
    $LoadBalancerRecord = @($LoadBalancers.LoadBalancers) | Where-Object { $_.LoadBalancerName -eq $LoadBalancerName } | Select-Object -First 1
    if ($null -eq $ServiceRecord -and $null -eq $LoadBalancerRecord) {
        return [pscustomobject]@{ State = "absent"; Service = $null; LoadBalancer = $null }
    }
    if ($null -eq $ServiceRecord -or $null -eq $LoadBalancerRecord) {
        return [pscustomobject]@{ State = "incomplete"; Service = $ServiceRecord; LoadBalancer = $LoadBalancerRecord }
    }
    $State = if ($ServiceRecord.desiredCount -eq 1 -and $ServiceRecord.runningCount -eq 1) { "ready" } else { "incomplete" }
    return [pscustomobject]@{ State = $State; Service = $ServiceRecord; LoadBalancer = $LoadBalancerRecord }
}

function Get-DevEdgeStatus {
    $Response = Invoke-AwsJson `
        -Arguments @("cloudfront", "list-distributions", "--output", "json") `
        -AllowEmpty
    if ($null -eq $Response) {
        return [pscustomobject]@{ State = "not-provisioned"; Distribution = $null }
    }
    $Distributions = if ($Response.DistributionList.PSObject.Properties.Name -contains "Items") {
        @($Response.DistributionList.Items)
    } else {
        @()
    }
    $Distribution = $Distributions | Where-Object { $_.Comment -like "$EdgeCommentPrefix*" } | Select-Object -First 1
    if ($null -eq $Distribution) {
        return [pscustomobject]@{ State = "not-provisioned"; Distribution = $null }
    }
    $State = if ($Distribution.Comment -eq "${EdgeCommentPrefix}active") { "active" } elseif ($Distribution.Comment -eq "${EdgeCommentPrefix}maintenance") { "maintenance" } else { "incomplete" }
    return [pscustomobject]@{ State = $State; Distribution = $Distribution }
}

function Show-DevStatus {
    param([Parameter(Mandatory = $true)]$RuntimeStatus, [Parameter(Mandatory = $true)]$EdgeStatus)
    $OperationalState = if ($EdgeStatus.State -eq "active" -and $RuntimeStatus.State -eq "ready") {
        "active"
    } elseif ($EdgeStatus.State -eq "maintenance" -and $RuntimeStatus.State -eq "absent") {
        "maintenance"
    } elseif ($EdgeStatus.State -eq "not-provisioned" -and $RuntimeStatus.State -eq "absent") {
        "not provisioned"
    } else {
        "transition or incomplete"
    }
    Write-Host "DEV operational state: $OperationalState"
    Write-Host "Edge state: $($EdgeStatus.State); runtime state: $($RuntimeStatus.State)"
    if ($null -ne $EdgeStatus.Distribution) {
        Write-Host "Stable URL: https://$($EdgeStatus.Distribution.DomainName)"
        Write-Host "CloudFront deployment: $($EdgeStatus.Distribution.Status)"
    }
    if ($null -ne $RuntimeStatus.Service) {
        Write-Host ("ECS tasks: desired={0}, running={1}, pending={2}" -f $RuntimeStatus.Service.desiredCount, $RuntimeStatus.Service.runningCount, $RuntimeStatus.Service.pendingCount)
    }
    switch ($OperationalState) {
        "active" { Write-Host "Cost profile: persistent edge plus ALB/public IPv4 and one Fargate task." }
        "maintenance" { Write-Host "Cost profile: persistent CloudFront edge only; disposable DEV runtime is absent." }
        "not provisioned" { Write-Host "Cost profile: no DEV edge or runtime resources detected." }
        default { Write-Warning "DEV is between its two supported states. Complete or recover the interrupted transition." }
    }
}

function Set-DesiredCountOne {
    $Content = Get-Content -Raw -LiteralPath $RuntimeVariablesPath
    $Pattern = "(?m)^desired_count\s*=\s*\d+\s*$"
    if ([regex]::Matches($Content, $Pattern).Count -ne 1) {
        throw "terraform.tfvars must contain exactly one desired_count assignment."
    }
    [System.IO.File]::WriteAllText($RuntimeVariablesPath, [regex]::Replace($Content, $Pattern, "desired_count = 1"))
}

function Invoke-Terraform {
    param([Parameter(Mandatory = $true)][string]$TerraformDirectory, [Parameter(Mandatory = $true)][string[]]$Arguments)
    Assert-CommandAvailable -Name "docker"
    if (-not (Test-Path -LiteralPath $AwsConfigurationDirectory -PathType Container)) {
        throw "AWS login cache directory is unavailable. Run 'aws login' and retry."
    }
    $RelativeDirectory = $TerraformDirectory.Substring($RepositoryRoot.Length).TrimStart("\").Replace("\", "/")
    $DockerArguments = @("run", "--rm", "-e", "AWS_REGION=$AwsRegion", "-e", "AWS_DEFAULT_REGION=$AwsRegion", "-e", "AWS_SDK_LOAD_CONFIG=1", "-v", "${AwsConfigurationDirectory}:/root/.aws:ro", "-v", "${AwsLoginCacheDirectory}:/root/.aws/login/cache", "-v", "${RepositoryRoot}:/workspace", "-w", "/workspace/$RelativeDirectory", $TerraformImage) + $Arguments
    & docker @DockerArguments
    if ($LASTEXITCODE -ne 0) { throw "Terraform command failed." }
}

function Initialize-Terraform {
    param([Parameter(Mandatory = $true)][string]$TerraformDirectory)
    Invoke-Terraform -TerraformDirectory $TerraformDirectory -Arguments @("init", "-reconfigure", "-input=false", "-no-color", "-backend-config=backend.hcl")
}

function Read-ExactConfirmation {
    param([Parameter(Mandatory = $true)][string]$Prompt, [Parameter(Mandatory = $true)][string]$Expected)
    if ((Read-Host "$Prompt Type '$Expected' to continue") -cne $Expected) {
        throw "Confirmation did not match. No Terraform apply was performed."
    }
}

function Invoke-ReviewedPlan {
    param(
        [Parameter(Mandatory = $true)][string]$TerraformDirectory,
        [Parameter(Mandatory = $true)][string]$PlanName,
        [Parameter(Mandatory = $true)][string]$Confirmation,
        [string[]]$Variables = @(),
        [switch]$Destroy
    )
    $PlanPath = Join-Path $TerraformDirectory $PlanName
    if (Test-Path -LiteralPath $PlanPath) { Remove-Item -LiteralPath $PlanPath -Force }
    try {
        $PlanArguments = @("plan", "-input=false", "-no-color", "-out=$PlanName")
        foreach ($Variable in $Variables) { $PlanArguments += "-var=$Variable" }
        if ($Destroy) { $PlanArguments += "-destroy" }
        Invoke-Terraform -TerraformDirectory $TerraformDirectory -Arguments $PlanArguments
        Read-ExactConfirmation -Prompt "Review the complete plan above." -Expected $Confirmation
        Invoke-Terraform -TerraformDirectory $TerraformDirectory -Arguments @("apply", "-input=false", "-no-color", $PlanName)
    }
    finally {
        if (Test-Path -LiteralPath $PlanPath) { Remove-Item -LiteralPath $PlanPath -Force }
    }
}

function Wait-ForServiceStability {
    Write-Host "Waiting for the ECS service to become stable..."
    & aws ecs wait services-stable --cluster $ClusterName --services $ServiceName --region $AwsRegion
    if ($LASTEXITCODE -ne 0) { throw "ECS did not reach a stable state within the AWS CLI wait period." }
}

function Wait-ForEdgeDeployment {
    $EdgeStatus = Get-DevEdgeStatus
    if ($null -eq $EdgeStatus.Distribution) { throw "CloudFront distribution was not found after apply." }
    Write-Host "Waiting for the CloudFront distribution to deploy..."
    & aws cloudfront wait distribution-deployed --id $EdgeStatus.Distribution.Id
    if ($LASTEXITCODE -ne 0) { throw "CloudFront did not reach a deployed state within the AWS CLI wait period." }
}

if ($Command -eq "help") { Show-Usage; exit 0 }

Assert-LocalConfiguration
Assert-AwsIdentity
$RuntimeStatus = Get-DevRuntimeStatus
$EdgeStatus = Get-DevEdgeStatus

switch ($Command) {
    "status" { Show-DevStatus -RuntimeStatus $RuntimeStatus -EdgeStatus $EdgeStatus }
    "active" {
        if ($EdgeStatus.State -eq "active" -and $RuntimeStatus.State -eq "ready") {
            Write-Host "DEV is already active."
            Show-DevStatus -RuntimeStatus $RuntimeStatus -EdgeStatus $EdgeStatus
            break
        }
        if ($RuntimeStatus.State -eq "incomplete") { throw "DEV runtime is incomplete. Review Terraform before activating it." }
        Set-DesiredCountOne
        Initialize-Terraform -TerraformDirectory $RuntimeTerraformDirectory
        Invoke-ReviewedPlan -TerraformDirectory $RuntimeTerraformDirectory -PlanName "dev-active.tfplan" -Confirmation "APPLY ACTIVE DEV RUNTIME"
        Wait-ForServiceStability
        $RuntimeStatus = Get-DevRuntimeStatus
        if ($RuntimeStatus.State -ne "ready") { throw "DEV runtime did not become ready; CloudFront remains in its previous state." }
        Initialize-Terraform -TerraformDirectory $EdgeTerraformDirectory
        Invoke-ReviewedPlan -TerraformDirectory $EdgeTerraformDirectory -PlanName "dev-edge-active.tfplan" -Confirmation "APPLY ACTIVE DEV EDGE" -Variables @("maintenance_mode=false", "origin_domain_name=$($RuntimeStatus.LoadBalancer.DNSName)")
        Wait-ForEdgeDeployment
        Show-DevStatus -RuntimeStatus (Get-DevRuntimeStatus) -EdgeStatus (Get-DevEdgeStatus)
    }
    "maintenance" {
        if ($EdgeStatus.State -eq "maintenance" -and $RuntimeStatus.State -eq "absent") {
            Write-Host "DEV is already in maintenance."
            Show-DevStatus -RuntimeStatus $RuntimeStatus -EdgeStatus $EdgeStatus
            break
        }
        $OriginDomainName = if ($null -ne $RuntimeStatus.LoadBalancer) { $RuntimeStatus.LoadBalancer.DNSName } else { "maintenance.invalid" }
        Initialize-Terraform -TerraformDirectory $EdgeTerraformDirectory
        Invoke-ReviewedPlan -TerraformDirectory $EdgeTerraformDirectory -PlanName "dev-edge-maintenance.tfplan" -Confirmation "APPLY MAINTENANCE DEV EDGE" -Variables @("maintenance_mode=true", "origin_domain_name=$OriginDomainName")
        Wait-ForEdgeDeployment
        if ($RuntimeStatus.State -ne "absent") {
            if ($RuntimeStatus.State -eq "incomplete") { throw "The edge is in maintenance, but the runtime is incomplete. Review Terraform before destroying it." }
            Write-Warning "CloudFront now serves maintenance. The reviewed destroy removes the disposable DEV runtime."
            Initialize-Terraform -TerraformDirectory $RuntimeTerraformDirectory
            Invoke-ReviewedPlan -TerraformDirectory $RuntimeTerraformDirectory -PlanName "dev-maintenance.tfplan" -Confirmation "DESTROY DEV RUNTIME" -Destroy
        }
        Show-DevStatus -RuntimeStatus (Get-DevRuntimeStatus) -EdgeStatus (Get-DevEdgeStatus)
    }
}
