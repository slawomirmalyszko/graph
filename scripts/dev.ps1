[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet("help", "status", "start", "stop", "hibernate")]
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

$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$TerraformDirectory = Join-Path $RepositoryRoot "infra\environments\dev"
$TerraformVariablesPath = Join-Path $TerraformDirectory "terraform.tfvars"
$BackendConfigurationPath = Join-Path $TerraformDirectory "backend.hcl"
$AwsConfigurationDirectory = Join-Path $env:USERPROFILE ".aws"

function Show-Usage {
    @"
Integration Catalogue DEV lifecycle controller

Usage:
  .\scripts\dev.cmd <command>

Commands:
  status      Show the live DEV state and active cost profile. Read-only.
  start       Start paused DEV or recreate a hibernated DEV environment.
  stop        Set ECS desired count to zero; retain ALB and networking.
  hibernate   Destroy the disposable DEV runtime to minimize idle cost.
  help        Show this help.

States:
  running     ALB/public IPv4 and one Fargate task are active.
  paused      Fargate is stopped; ALB/public IPv4 remain active.
  hibernated  DEV runtime resources are absent; shared foundations remain.

Safety:
  start requires:      APPLY START DEV
  stop requires:       APPLY STOP DEV
  hibernate requires:  HIBERNATE DEV

Prerequisites:
  1. Docker Desktop and AWS CLI are installed.
  2. Run: aws login
  3. Set INTEGRATION_CATALOGUE_AWS_ACCOUNT_ID in the current shell.
  4. Keep ignored backend.hcl and terraform.tfvars files configured locally.

Examples:
  .\scripts\dev.cmd status
  .\scripts\dev.cmd stop
  .\scripts\dev.cmd start

No command defaults to this help and performs no AWS operation.
"@ | Write-Host
}

function Assert-CommandAvailable {
    param([Parameter(Mandatory = $true)][string]$Name)

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' is unavailable."
    }
}

function Assert-LocalConfiguration {
    if ([string]::IsNullOrWhiteSpace($ExpectedAccountId)) {
        throw (
            "Expected AWS account ID is required. Set " +
            "INTEGRATION_CATALOGUE_AWS_ACCOUNT_ID locally or pass -ExpectedAccountId."
        )
    }

    if (-not (Test-Path -LiteralPath $TerraformVariablesPath -PathType Leaf)) {
        throw "Missing ignored configuration: $TerraformVariablesPath"
    }

    if (-not (Test-Path -LiteralPath $BackendConfigurationPath -PathType Leaf)) {
        throw "Missing ignored backend configuration: $BackendConfigurationPath"
    }
}

function Assert-AwsIdentity {
    Assert-CommandAvailable -Name "aws"

    try {
        $Identity = Invoke-AwsJson -Arguments @(
            "sts", "get-caller-identity",
            "--region", $AwsRegion,
            "--output", "json"
        )
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

function Invoke-AwsJson {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)

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
        throw "AWS CLI returned no JSON output."
    }

    return ($Output | ConvertFrom-Json)
}

function Get-DevRuntimeStatus {
    $Clusters = Invoke-AwsJson -Arguments @(
        "ecs", "list-clusters",
        "--region", $AwsRegion,
        "--output", "json"
    )

    $ClusterArn = @($Clusters.clusterArns) |
        Where-Object { $_ -match "/$([regex]::Escape($ClusterName))$" } |
        Select-Object -First 1

    $Service = $null
    if ($null -ne $ClusterArn) {
        $Service = Invoke-AwsJson -Arguments @(
            "ecs", "describe-services",
            "--cluster", $ClusterArn,
            "--services", $ServiceName,
            "--region", $AwsRegion,
            "--output", "json"
        )
    }

    $LoadBalancers = Invoke-AwsJson -Arguments @(
        "elbv2", "describe-load-balancers",
        "--region", $AwsRegion,
        "--output", "json"
    )

    $ServiceRecord = $null
    if ($null -ne $Service -and $Service.services.Count -gt 0) {
        $Candidate = $Service.services[0]
        if ($Candidate.status -ne "INACTIVE") {
            $ServiceRecord = $Candidate
        }
    }

    $LoadBalancerRecord = @($LoadBalancers.LoadBalancers) |
        Where-Object { $_.LoadBalancerName -eq $LoadBalancerName } |
        Select-Object -First 1

    if ($null -eq $ServiceRecord -and $null -eq $LoadBalancerRecord) {
        return [pscustomobject]@{
            State = "hibernated"
            Service = $null
            LoadBalancer = $null
        }
    }

    if ($null -eq $ServiceRecord) {
        return [pscustomobject]@{
            State = "incomplete"
            Service = $null
            LoadBalancer = $LoadBalancerRecord
        }
    }

    $State = if ($ServiceRecord.desiredCount -eq 0) { "paused" } else { "running" }
    return [pscustomobject]@{
        State = $State
        Service = $ServiceRecord
        LoadBalancer = $LoadBalancerRecord
    }
}

function Show-DevRuntimeStatus {
    param([Parameter(Mandatory = $true)]$RuntimeStatus)

    Write-Host "DEV state: $($RuntimeStatus.State)"

    if ($null -ne $RuntimeStatus.Service) {
        Write-Host (
            "ECS tasks: desired={0}, running={1}, pending={2}" -f
            $RuntimeStatus.Service.desiredCount,
            $RuntimeStatus.Service.runningCount,
            $RuntimeStatus.Service.pendingCount
        )
    }

    if ($null -ne $RuntimeStatus.LoadBalancer) {
        Write-Host "URL: http://$($RuntimeStatus.LoadBalancer.DNSName)"
    }

    switch ($RuntimeStatus.State) {
        "running" { Write-Host "Cost profile: ALB/public IPv4 and Fargate task are active." }
        "paused" { Write-Host "Cost profile: Fargate task is stopped; ALB/public IPv4 remain active." }
        "hibernated" { Write-Host "Cost profile: DEV runtime resources are absent." }
        default { Write-Warning "DEV resources are only partially present. Review Terraform before changing them." }
    }
}

function Set-DesiredCount {
    param([Parameter(Mandatory = $true)][ValidateSet(0, 1)][int]$Value)

    $Content = Get-Content -Raw -LiteralPath $TerraformVariablesPath
    $Pattern = "(?m)^desired_count\s*=\s*\d+\s*$"
    if ($Content -notmatch $Pattern) {
        throw "terraform.tfvars does not contain exactly one desired_count assignment."
    }

    $Matches = [regex]::Matches($Content, $Pattern)
    if ($Matches.Count -ne 1) {
        throw "terraform.tfvars must contain exactly one desired_count assignment."
    }

    $Updated = [regex]::Replace($Content, $Pattern, "desired_count         = $Value")
    [System.IO.File]::WriteAllText($TerraformVariablesPath, $Updated)
}

function Invoke-Terraform {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)

    Assert-CommandAvailable -Name "docker"
    if (-not (Test-Path -LiteralPath $AwsConfigurationDirectory -PathType Container)) {
        throw "AWS login cache directory is unavailable. Run 'aws login' and retry."
    }

    $DockerArguments = @(
        "run", "--rm",
        "-e", "AWS_REGION=$AwsRegion",
        "-e", "AWS_DEFAULT_REGION=$AwsRegion",
        "-e", "AWS_SDK_LOAD_CONFIG=1",
        "-v", "${AwsConfigurationDirectory}:/root/.aws:ro",
        "-v", "${RepositoryRoot}:/workspace",
        "-w", "/workspace/infra/environments/dev",
        $TerraformImage
    ) + $Arguments

    & docker @DockerArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Terraform command failed."
    }
}

function Initialize-Terraform {
    Invoke-Terraform -Arguments @(
        "init", "-reconfigure", "-input=false", "-no-color",
        "-backend-config=backend.hcl"
    )
}

function Read-ExactConfirmation {
    param(
        [Parameter(Mandatory = $true)][string]$Prompt,
        [Parameter(Mandatory = $true)][string]$Expected
    )

    $Response = Read-Host "$Prompt Type '$Expected' to continue"
    if ($Response -cne $Expected) {
        throw "Confirmation did not match. No Terraform apply was performed."
    }
}

function Invoke-ReviewedPlan {
    param(
        [Parameter(Mandatory = $true)][string]$PlanName,
        [Parameter(Mandatory = $true)][string]$Confirmation,
        [switch]$Destroy
    )

    $PlanPath = Join-Path $TerraformDirectory $PlanName
    if (Test-Path -LiteralPath $PlanPath) {
        Remove-Item -LiteralPath $PlanPath -Force
    }

    try {
        $PlanArguments = @("plan", "-input=false", "-no-color", "-out=$PlanName")
        if ($Destroy) {
            $PlanArguments += "-destroy"
        }

        Invoke-Terraform -Arguments $PlanArguments
        Read-ExactConfirmation -Prompt "Review the complete plan above." -Expected $Confirmation
        Invoke-Terraform -Arguments @("apply", "-input=false", "-no-color", $PlanName)
    }
    finally {
        if (Test-Path -LiteralPath $PlanPath) {
            Remove-Item -LiteralPath $PlanPath -Force
        }
    }
}

function Wait-ForServiceStability {
    Write-Host "Waiting for the ECS service to become stable..."
    & aws ecs wait services-stable `
        --cluster $ClusterName `
        --services $ServiceName `
        --region $AwsRegion

    if ($LASTEXITCODE -ne 0) {
        throw "ECS did not reach a stable state within the AWS CLI wait period."
    }
}

if ($Command -eq "help") {
    Show-Usage
    exit 0
}

Assert-LocalConfiguration
Assert-AwsIdentity
$RuntimeStatus = Get-DevRuntimeStatus

switch ($Command) {
    "status" {
        Show-DevRuntimeStatus -RuntimeStatus $RuntimeStatus
    }
    "start" {
        if ($RuntimeStatus.State -eq "running" -and $RuntimeStatus.Service.desiredCount -eq 1) {
            Write-Host "DEV is already running."
            Show-DevRuntimeStatus -RuntimeStatus $RuntimeStatus
            break
        }

        Set-DesiredCount -Value 1
        Initialize-Terraform
        Invoke-ReviewedPlan -PlanName "dev-start.tfplan" -Confirmation "APPLY START DEV"
        Wait-ForServiceStability
        Show-DevRuntimeStatus -RuntimeStatus (Get-DevRuntimeStatus)
    }
    "stop" {
        if ($RuntimeStatus.State -eq "hibernated") {
            Write-Host "DEV is already hibernated; there is no task to stop."
            break
        }
        if ($RuntimeStatus.State -eq "incomplete") {
            throw "DEV resources are incomplete. Review Terraform before stopping."
        }
        if ($RuntimeStatus.Service.desiredCount -eq 0) {
            Write-Host "DEV is already paused."
            Show-DevRuntimeStatus -RuntimeStatus $RuntimeStatus
            break
        }

        Set-DesiredCount -Value 0
        Initialize-Terraform
        Invoke-ReviewedPlan -PlanName "dev-stop.tfplan" -Confirmation "APPLY STOP DEV"
        Wait-ForServiceStability
        Show-DevRuntimeStatus -RuntimeStatus (Get-DevRuntimeStatus)
    }
    "hibernate" {
        if ($RuntimeStatus.State -eq "hibernated") {
            Write-Host "DEV is already hibernated."
            break
        }
        if ($RuntimeStatus.State -eq "incomplete") {
            throw "DEV resources are incomplete. Review Terraform before hibernating."
        }

        Write-Warning (
            "Hibernate destroys the DEV ALB, ECS runtime, VPC, IAM runtime roles, " +
            "and CloudWatch log group. The next start creates a new ALB hostname."
        )
        Initialize-Terraform
        Invoke-ReviewedPlan `
            -PlanName "dev-hibernate.tfplan" `
            -Confirmation "HIBERNATE DEV" `
            -Destroy
        Show-DevRuntimeStatus -RuntimeStatus (Get-DevRuntimeStatus)
    }
}
