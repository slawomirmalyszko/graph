[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet("help", "status", "activate", "maintain", "update")]
    [string]$Command = "help",
    [ValidatePattern("^\d{12}$")]
    [string]$ExpectedAccountId = $env:INTEGRATION_CATALOGUE_AWS_ACCOUNT_ID,
    [ValidatePattern("^sha-[0-9a-f]{40}$")]
    [string]$ImageTag
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$AwsRegion = "eu-north-1"
$ExpectedRoleName = "AccountFullAccessRole"
$BuildProjectName = "integration-catalogue-dev-lifecycle"
$ClusterName = "integration-catalogue-dev"
$ServiceName = "integration-catalogue-dev"
$LoadBalancerName = "integration-catalogue-dev"
$EcrRepositoryName = "integration-catalogue"
$EdgeCommentPrefix = "integration-catalogue-dev-"

function Show-Usage {
    @"
Integration Catalogue DEV lifecycle remote control

Usage:
  .\scripts\dev.ps1 <command>

Commands:
  status        Show the live DEV state and active cost profile. Read-only.
  activate      Ask CodeBuild to create the runtime and activate the stable edge.
  update        Ask CodeBuild to deploy a published immutable image to active DEV.
  maintain      Ask CodeBuild to serve maintenance and destroy the DEV runtime.
  help          Show this help.

Execution model:
  status reads AWS directly and never starts a build.
  activate, update, and maintain start the same CodeBuild lifecycle executor used
  by EventBridge Scheduler. Terraform never runs on this laptop.

Prerequisites:
  1. AWS CLI 2.32 or later is installed.
  2. Run: aws login
  3. Set INTEGRATION_CATALOGUE_AWS_ACCOUNT_ID in the current shell.
  4. Bootstrap infra/environments/dev-automation once through Terraform.

Examples:
  .\scripts\dev.ps1 status
  .\scripts\dev.ps1 activate
  .\scripts\dev.ps1 update -ImageTag sha-0123456789abcdef0123456789abcdef01234567
  .\scripts\dev.ps1 maintain

No command defaults to this help and performs no AWS operation.
"@ | Write-Host
}
function Assert-CommandAvailable {
    param([Parameter(Mandatory = $true)][string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' is unavailable."
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
        if ($AllowEmpty) { return $null }
        $Operation = ($Arguments | Select-Object -First 2) -join " "
        throw "AWS CLI operation '$Operation' returned no JSON output."
    }
    return ($Output | ConvertFrom-Json)
}

function Assert-AwsIdentity {
    Assert-CommandAvailable -Name "aws"
    if ([string]::IsNullOrWhiteSpace($ExpectedAccountId)) {
        throw "Expected AWS account ID is required. Set INTEGRATION_CATALOGUE_AWS_ACCOUNT_ID locally or pass -ExpectedAccountId."
    }
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
    $Response = Invoke-AwsJson -Arguments @("cloudfront", "list-distributions", "--output", "json") -AllowEmpty
    if ($null -eq $Response) {
        return [pscustomobject]@{ State = "not-provisioned"; Distribution = $null }
    }
    $Distributions = if ($Response.DistributionList.PSObject.Properties.Name -contains "Items") {
        @($Response.DistributionList.Items)
    } else { @() }
    $Distribution = $Distributions | Where-Object { $_.Comment -like "$EdgeCommentPrefix*" } | Select-Object -First 1
    if ($null -eq $Distribution) {
        return [pscustomobject]@{ State = "not-provisioned"; Distribution = $null }
    }
    $State = if ($Distribution.Comment -eq "${EdgeCommentPrefix}active") {
        "active"
    } elseif ($Distribution.Comment -eq "${EdgeCommentPrefix}maintenance") {
        "maintenance"
    } else { "incomplete" }
    return [pscustomobject]@{ State = $State; Distribution = $Distribution }
}

function Get-ServiceImageDigest {
    param([Parameter(Mandatory = $true)]$Service)
    $Response = Invoke-AwsJson -Arguments @("ecs", "describe-task-definition", "--task-definition", $Service.taskDefinition, "--region", $AwsRegion, "--output", "json")
    $Container = @($Response.taskDefinition.containerDefinitions) | Select-Object -First 1
    if ($null -eq $Container -or $Container.image -notmatch "@(sha256:[0-9a-f]{64})$") { return $null }
    return $Matches[1]
}

function Get-EcrImageTags {
    param([Parameter(Mandatory = $true)][string]$Digest)
    try {
        $Response = Invoke-AwsJson -Arguments @("ecr", "describe-images", "--repository-name", $EcrRepositoryName, "--image-ids", "imageDigest=$Digest", "--region", $AwsRegion, "--output", "json")
    }
    catch { return @() }
    $Details = @($Response.imageDetails) | Select-Object -First 1
    if ($null -eq $Details) { return @() }
    return @($Details.imageTags) | Sort-Object
}

function Show-DevStatus {
    $RuntimeStatus = Get-DevRuntimeStatus
    $EdgeStatus = Get-DevEdgeStatus
    $OperationalState = if ($EdgeStatus.State -eq "active" -and $RuntimeStatus.State -eq "ready") {
        "active"
    } elseif ($EdgeStatus.State -eq "maintenance" -and $RuntimeStatus.State -eq "absent") {
        "maintenance"
    } elseif ($EdgeStatus.State -eq "not-provisioned" -and $RuntimeStatus.State -eq "absent") {
        "not provisioned"
    } else { "transition or incomplete" }

    Write-Host "DEV operational state: $OperationalState"
    Write-Host "Edge state: $($EdgeStatus.State); runtime state: $($RuntimeStatus.State)"
    if ($null -ne $EdgeStatus.Distribution) {
        Write-Host "Stable URL: https://$($EdgeStatus.Distribution.DomainName)"
        Write-Host "CloudFront deployment: $($EdgeStatus.Distribution.Status)"
    }
    if ($null -ne $RuntimeStatus.Service) {
        Write-Host ("ECS tasks: desired={0}, running={1}, pending={2}" -f $RuntimeStatus.Service.desiredCount, $RuntimeStatus.Service.runningCount, $RuntimeStatus.Service.pendingCount)
        $Digest = Get-ServiceImageDigest -Service $RuntimeStatus.Service
        if ($null -ne $Digest) {
            Write-Host "ECS image digest: $Digest"
            $Tags = @(Get-EcrImageTags -Digest $Digest)
            $TagText = if ($Tags.Count -gt 0) { $Tags -join ", " } else { "<untagged or unavailable>" }
            Write-Host "ECS image tag: $TagText"
        }
    }
    switch ($OperationalState) {
        "active" { Write-Host "Cost profile: persistent edge plus ALB/public IPv4 and one Fargate task." }
        "maintenance" { Write-Host "Cost profile: persistent CloudFront edge only; disposable DEV runtime is absent." }
        "not provisioned" { Write-Host "Cost profile: no DEV edge or runtime resources detected." }
        default { Write-Warning "DEV is between its two supported states. Review the latest CodeBuild execution." }
    }
}

function Read-ExactConfirmation {
    param([Parameter(Mandatory = $true)][string]$Expected)
    if ((Read-Host "This starts a remote CodeBuild Terraform operation. Type '$Expected' to continue") -cne $Expected) {
        throw "Confirmation did not match. No CodeBuild execution was started."
    }
}

function Start-LifecycleBuild {
    param(
        [Parameter(Mandatory = $true)][string]$Operation,
        [string]$RequestedImageTag
    )
    $Overrides = @("name=DEV_OPERATION,value=$Operation,type=PLAINTEXT")
    if (-not [string]::IsNullOrWhiteSpace($RequestedImageTag)) {
        $Overrides += "name=DEV_IMAGE_TAG,value=$RequestedImageTag,type=PLAINTEXT"
    }
    $Arguments = @(
        "codebuild", "start-build",
        "--project-name", $BuildProjectName,
        "--environment-variables-override"
    ) + $Overrides + @("--region", $AwsRegion, "--output", "json")
    $Response = Invoke-AwsJson -Arguments $Arguments
    $BuildId = $Response.build.id
    if ([string]::IsNullOrWhiteSpace($BuildId)) { throw "CodeBuild returned no build identifier." }
    Write-Host "Started CodeBuild execution: $BuildId"
    Write-Host "AWS Console: https://$AwsRegion.console.aws.amazon.com/codesuite/codebuild/projects/$BuildProjectName/history?region=$AwsRegion"

    $PreviousStatus = ""
    while ($true) {
        $BuildResponse = Invoke-AwsJson -Arguments @("codebuild", "batch-get-builds", "--ids", $BuildId, "--region", $AwsRegion, "--output", "json")
        $Build = @($BuildResponse.builds) | Select-Object -First 1
        if ($null -eq $Build) { throw "CodeBuild execution '$BuildId' could not be read." }
        if ($Build.buildStatus -ne $PreviousStatus) {
            Write-Host "CodeBuild status: $($Build.buildStatus)"
            $PreviousStatus = $Build.buildStatus
        }
        if ($Build.buildStatus -in @("SUCCEEDED", "FAILED", "FAULT", "STOPPED", "TIMED_OUT")) {
            if ($Build.buildStatus -ne "SUCCEEDED") {
                throw "CodeBuild lifecycle execution ended with status $($Build.buildStatus). Review its CloudWatch logs."
            }
            Write-Host "CodeBuild lifecycle execution completed successfully."
            return
        }
        Start-Sleep -Seconds 10
    }
}

if ($Command -eq "help") { Show-Usage; exit 0 }

Assert-AwsIdentity

switch ($Command) {
    "status" { Show-DevStatus }
    "activate" {
        Read-ExactConfirmation -Expected "START DEV ACTIVATE"
        Start-LifecycleBuild -Operation "activate"
        Show-DevStatus
    }
    "maintain" {
        Read-ExactConfirmation -Expected "START DEV MAINTAIN"
        Start-LifecycleBuild -Operation "maintain"
        Show-DevStatus
    }
    "update" {
        if ([string]::IsNullOrWhiteSpace($ImageTag)) {
            throw "update requires -ImageTag with an immutable sha-<40 lowercase hex characters> tag."
        }
        Read-ExactConfirmation -Expected "START DEV UPDATE"
        Start-LifecycleBuild -Operation "update" -RequestedImageTag $ImageTag
        Show-DevStatus
    }
}
