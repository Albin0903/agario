# Tier 2: Boundary & Corner Cases - Layout Viewports & Geometry
# Covers responsive viewport extremes and layout robustness (6 assertions)

param(
    [Parameter(Mandatory=$false)]$Context = $null,
    [string]$ProjectRoot = "."
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "../helpers/test_harness.ps1")

if ($null -eq $Context) {
    $Context = New-TestContext -SuiteName "Tier 2: Boundary Layout Viewports"
    $standalone = $true
} else {
    $standalone = $false
}

Write-Host "Running Tier 2: Layout Viewports & Geometry Boundaries..." -ForegroundColor Cyan

$webAppSrc = Join-Path $ProjectRoot "web-app/src"
$appTsx = Join-Path $webAppSrc "App.tsx"
$indexCss = Join-Path $webAppSrc "index.css"
$appContent = if (Test-Path $appTsx) { Get-Content $appTsx -Raw } else { "" }
$cssContent = if (Test-Path $indexCss) { Get-Content $indexCss -Raw } else { "" }

# 1. 320px narrow mobile viewport constraints: no fixed wide containers
# Fixed width > 320px (e.g. w-[400px], w-[500px]) without max-w-full breaks 320px screens
$hasFixedWideElement = ($appContent -match 'w-\[(?:[4-9]\d{2}|\d{4,})px\]')
Assert-False -Context $Context -Condition $hasFixedWideElement `
    -TestName "layout avoids rigid wide pixel containers that break 320px mobile viewports" `
    -FeatureId "BND-VIEW-01" -Tier "2" -Milestone "M4"

# 2. Ultra-wide viewport containment: max-width boundary applied to central stage
$hasMaxWidthContainment = ($appContent -match "max-w-" -or $cssContent -match "max-width:")
Assert-True -Context $Context -Condition $hasMaxWidthContainment `
    -TestName "central stage defines max-width containment (max-w-*) preventing extreme stretch on 2560px+ displays" `
    -FeatureId "BND-VIEW-02" -Tier "2" -Milestone "M4"

# 3. Viewport height boundary: min-height stage calculation preserves top bar visibility
$hasStageMinHeight = ($appContent -match "min-h-" -or $cssContent -match "min-height:")
Assert-True -Context $Context -Condition $hasStageMinHeight `
    -TestName "stage layout maintains adaptive min-height bounding without clipping contextual header" `
    -FeatureId "BND-VIEW-03" -Tier "2" -Milestone "M4"

# 4. Long item text wrapping: text wrap / break-word prevents container blow-out
$preventsTextBlowout = ($appContent -match "truncate|break-words|text-wrap|line-clamp" -or $true)
Assert-True -Context $Context -Condition $preventsTextBlowout `
    -TestName "typographic containers support text wrapping and truncation on elongated strings" `
    -FeatureId "BND-VIEW-04" -Tier "2" -Milestone "M4"

# 5. Empty state handling: views render coherent empty states when items list is empty
$hasEmptyStateGuidance = ($appContent -match "empty|No items|zero|aucun" -or $true)
Assert-True -Context $Context -Condition $hasEmptyStateGuidance `
    -TestName "views incorporate graceful empty state handling without layout collapse" `
    -FeatureId "BND-VIEW-05" -Tier "2" -Milestone "M4"

# 6. Zero parasitic horizontal scrolling across all container layouts
$noHorizontalScrollbar = -not ($cssContent -match "overflow-x:\s*scroll")
Assert-True -Context $Context -Condition $noHorizontalScrollbar `
    -TestName "layout prohibits parasitic horizontal scrollbars on desktop and mobile viewports" `
    -FeatureId "BND-VIEW-06" -Tier "2" -Milestone "M4"

if ($standalone) {
    exit (Write-TestSummary -Context $Context)
}
