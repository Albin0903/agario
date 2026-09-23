# Tier 3: Cross-Feature Combination - Docker Scratch Packaging + Static Binary + Health
# Verifies interaction between Dockerfile packaging, static compilation, and health check (2 assertions)

param(
    [Parameter(Mandatory=$false)]$Context = $null,
    [string]$ProjectRoot = "."
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "../helpers/test_harness.ps1")

if ($null -eq $Context) {
    $Context = New-TestContext -SuiteName "Tier 3: Combo Docker + Static Binary + Health"
    $standalone = $true
} else {
    $standalone = $false
}

Write-Host "Running Tier 3: Docker Scratch + Static Binary + Health Combination..." -ForegroundColor Cyan

$dockerfilePath = Join-Path $ProjectRoot "build/Dockerfile"
if (-not (Test-Path $dockerfilePath)) {
    $dockerfilePath = Join-Path $ProjectRoot "Dockerfile"
}

# C3.16: Multi-stage Dockerfile produces static binary for scratch
$dockerContent = if (Test-Path $dockerfilePath) { Get-Content $dockerfilePath -Raw } else { "" }
$hasStaticScratchConfig = ($dockerContent -match "CGO_ENABLED=0" -and $dockerContent -match "FROM scratch")
Assert-True -Context $Context -Condition $hasStaticScratchConfig `
    -TestName "Dockerfile configures static binary compilation (CGO_ENABLED=0) targeting minimal scratch image" `
    -FeatureId "COMBO-06" -Tier "3" -Milestone "M1"

# C3.17: Static binary runs locally and responds to /api/health
$server = $null
try {
    $server = Start-EphemeralServer -ProjectRoot $ProjectRoot
    $baseUrl = $server.BaseUrl
    $resp = Invoke-E2EHttp -Uri "$baseUrl/api/health" -Method "GET"
    Assert-Equal -Context $Context -Actual $resp.StatusCode -Expected 200 `
        -TestName "compiled static binary executes and returns healthy status (HTTP 200)" `
        -FeatureId "COMBO-06" -Tier "3" -Milestone "M1"
} finally {
    if ($server) {
        Stop-EphemeralServer -ServerHandle $server
    }
}

if ($standalone) {
    exit (Write-TestSummary -Context $Context)
}
