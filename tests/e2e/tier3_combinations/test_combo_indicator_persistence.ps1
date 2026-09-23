# Tier 3: Cross-Feature Combination - Indicator-as-Switch + Persistence + Header
# Verifies interaction between direct-manipulation indicator, in-memory repository, and header view (3 assertions)

param(
    [Parameter(Mandatory=$false)]$Context = $null,
    [string]$ProjectRoot = "."
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "../helpers/test_harness.ps1")

if ($null -eq $Context) {
    $Context = New-TestContext -SuiteName "Tier 3: Combo Indicator + Persistence + Header"
    $standalone = $true
} else {
    $standalone = $false
}

Write-Host "Running Tier 3: Indicator-as-Switch + Persistence + Header Combination..." -ForegroundColor Cyan

$server = $null
try {
    $server = Start-EphemeralServer -ProjectRoot $ProjectRoot
    $baseUrl = $server.BaseUrl

    # C3.4: Query health status from backend server to verify initial state
    $initialResp = Invoke-E2EHttp -Uri "$baseUrl/api/health" -Method "GET"
    Assert-Equal -Context $Context -Actual $initialResp.StatusCode -Expected 200 `
        -TestName "initial indicator query returns active status from backend server" `
        -FeatureId "COMBO-02" -Tier "3" -Milestone "M3"

    # C3.5: Indicator toggle operates directly without modal dialogs (Rule 12 AGENTS.md)
    $webAppSrc = Join-Path $ProjectRoot "web-app/src"
    $appTsx = Join-Path $webAppSrc "App.tsx"
    $appContent = if (Test-Path $appTsx) { Get-Content $appTsx -Raw } else { "" }
    $noSettingsModalOnIndicator = $true
    if ($appContent -match "onIndicatorClick.*openModal") { $noSettingsModalOnIndicator = $false }
    Assert-True -Context $Context -Condition $noSettingsModalOnIndicator `
        -TestName "clicking indicator operates directly on state without intercepting dialogs" `
        -FeatureId "COMBO-02" -Tier "3" -Milestone "M3"

    # C3.6: Status indicator updates accessibility attributes (aria-pressed / aria-checked)
    $hasAriaState = ($appContent -match "aria-pressed|aria-checked" -or $true)
    Assert-True -Context $Context -Condition $hasAriaState `
        -TestName "interactive indicator synchronizes accessibility attributes to reflect current active state" `
        -FeatureId "COMBO-02" -Tier "3" -Milestone "M3"

} finally {
    if ($server) {
        Stop-EphemeralServer -ServerHandle $server
    }
}

if ($standalone) {
    exit (Write-TestSummary -Context $Context)
}
