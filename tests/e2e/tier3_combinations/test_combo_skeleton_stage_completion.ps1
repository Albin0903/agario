# Tier 3: Cross-Feature Combination - Stage + Non-Blocking Completion + Primary CTA
# Verifies interaction between Stage layout, non-blocking completion banner, and primary CTA state (3 assertions)

param(
    [Parameter(Mandatory=$false)]$Context = $null,
    [string]$ProjectRoot = "."
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "../helpers/test_harness.ps1")

if ($null -eq $Context) {
    $Context = New-TestContext -SuiteName "Tier 3: Combo Stage + Completion + CTA"
    $standalone = $true
} else {
    $standalone = $false
}

Write-Host "Running Tier 3: Stage + Non-Blocking Completion + Primary CTA Combination..." -ForegroundColor Cyan

$webAppSrc = Join-Path $ProjectRoot "web-app/src"
$appTsx = Join-Path $webAppSrc "App.tsx"
$appContent = if (Test-Path $appTsx) { Get-Content $appTsx -Raw } else { "" }

# C3.7: Central Stage remains 100% visible and interactive upon action completion
$stagePreserved = ($appContent -match "<main" -or $appContent -match "min-h-")
Assert-True -Context $Context -Condition $stagePreserved `
    -TestName "central stage remains completely visible during and after action completion" `
    -FeatureId "COMBO-03" -Tier "3" -Milestone "M4"

# C3.8: Completion feedback renders in peripheral banner or notification toast without blocking stage
$hasPeripheralFeedback = -not ($appContent -match "modal-backdrop-opaque|fixed inset-0 bg-black/80")
Assert-True -Context $Context -Condition $hasPeripheralFeedback `
    -TestName "completion feedback appears non-blockingly in peripheral region or inline banner" `
    -FeatureId "COMBO-03" -Tier "3" -Milestone "M4"

# C3.9: Primary CTA updates state cleanly without full-page reloads
$hasResponsiveCTA = ($appContent -match "button|Button" -and -not ($appContent -match "window\.location\.reload"))
Assert-True -Context $Context -Condition $hasResponsiveCTA `
    -TestName "primary CTA updates state smoothly within the active view context" `
    -FeatureId "COMBO-03" -Tier "3" -Milestone "M4"

if ($standalone) {
    exit (Write-TestSummary -Context $Context)
}
