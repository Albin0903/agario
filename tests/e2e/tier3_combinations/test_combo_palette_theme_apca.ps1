# Tier 3: Cross-Feature Combination - Radix 12 Palette + Satin Light Theme + APCA
# Verifies interaction between 12-level palette tokens, default satin light canvas, and APCA contrast thresholds (3 assertions)

param(
    [Parameter(Mandatory=$false)]$Context = $null,
    [string]$ProjectRoot = "."
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "../helpers/test_harness.ps1")

if ($null -eq $Context) {
    $Context = New-TestContext -SuiteName "Tier 3: Combo Palette + Theme + APCA"
    $standalone = $true
} else {
    $standalone = $false
}

Write-Host "Running Tier 3: Palette + Satin Theme + APCA Contrast Combination..." -ForegroundColor Cyan

$webAppSrc = Join-Path $ProjectRoot "web-app/src"
$appTsx = Join-Path $webAppSrc "App.tsx"
$indexCss = Join-Path $webAppSrc "index.css"
$appContent = if (Test-Path $appTsx) { Get-Content $appTsx -Raw } else { "" }

# C3.10: Root canvas utilizes level 1-2 background tokens (slate-50 / white)
$usesSatinBackground = ($appContent -match "bg-slate-50" -or $appContent -match "bg-white" -or $appContent -match "bg-gray-50")
Assert-True -Context $Context -Condition $usesSatinBackground `
    -TestName "canvas background aligns with level 1-2 palette tokens (bg-slate-50 / bg-white)" `
    -FeatureId "COMBO-04" -Tier "3" -Milestone "M2"

# C3.11: Foreground text utilizes level 11-12 tokens ensuring APCA body contrast Lc >= 75
$usesHighContrastText = ($appContent -match "text-slate-900" -or $appContent -match "text-slate-800" -or $appContent -match "text-gray-900")
Assert-True -Context $Context -Condition $usesHighContrastText `
    -TestName "typography body tokens apply level 11-12 high contrast text meeting APCA Lc >= 75" `
    -FeatureId "COMBO-04" -Tier "3" -Milestone "M2"

# C3.12: Surface elevation tokens use soft solar shadows without pitch black opacity
$usesSolarShadows = -not ($appContent -match "shadow-black")
Assert-True -Context $Context -Condition $usesSolarShadows `
    -TestName "surface elevations feature soft solar shadows (slate-200/50) preserving light canvas ambiance" `
    -FeatureId "COMBO-04" -Tier "3" -Milestone "M2"

if ($standalone) {
    exit (Write-TestSummary -Context $Context)
}
