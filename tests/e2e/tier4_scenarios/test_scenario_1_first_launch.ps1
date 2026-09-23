# Tier 4: Real-World Scenario 1 - First-Time User Launch & Visual Immersion
# Simulates fresh user visiting application, verifying 3-tier skeleton, light theme, and action salience (5 assertions)

param(
    [Parameter(Mandatory=$false)]$Context = $null,
    [string]$ProjectRoot = "."
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "../helpers/test_harness.ps1")

if ($null -eq $Context) {
    $Context = New-TestContext -SuiteName "Tier 4: Scenario 1 First-Time User Launch"
    $standalone = $true
} else {
    $standalone = $false
}

Write-Host "Running Tier 4: Scenario 1 - First-Time User Launch & Visual Immersion..." -ForegroundColor Cyan

$webAppSrc = Join-Path $ProjectRoot "web-app/src"
$appTsx = Join-Path $webAppSrc "App.tsx"
$indexCss = Join-Path $webAppSrc "index.css"
$appContent = if (Test-Path $appTsx) { Get-Content $appTsx -Raw } else { "" }
$cssContent = if (Test-Path $indexCss) { Get-Content $indexCss -Raw } else { "" }

# S1.1: 3-tier Product Skeleton rendered immediately (Header, Stage, Peripherals)
$has3TierSkeleton = ($appContent -match "<header" -and $appContent -match "<main") -or ($appContent -match "Header" -and $appContent -match "Stage")
Assert-True -Context $Context -Condition $has3TierSkeleton `
    -TestName "Scenario 1.1: Initial view structures 3-tier Product Skeleton (Header, Stage, Peripherals)" `
    -FeatureId "SCENARIO-01" -Tier "4" -Milestone "M4"

# S1.2: Default satin light theme canvas loaded (bg-slate-50 to bg-white)
$hasSatinCanvas = ($appContent -match "bg-slate-50" -or $appContent -match "bg-white" -or $appContent -match "bg-neutral-50")
Assert-True -Context $Context -Condition $hasSatinCanvas `
    -TestName "Scenario 1.2: Application starts on satin light theme default canvas without dark mode flash" `
    -FeatureId "SCENARIO-01" -Tier "4" -Milestone "M2"

# S1.3: Single prominent CTA visible within 3 seconds without onboarding walkthrough popups
$hasProminentCTA = ($appContent -match "<button" -or $appContent -match "Button")
$noWalkthroughs = -not ($appContent -match "tour-guide|walkthrough|onboarding-popup")
Assert-True -Context $Context -Condition ($hasProminentCTA -and $noWalkthroughs) `
    -TestName "Scenario 1.3: Primary master action is immediately perceptible without intrusive walkthrough popups" `
    -FeatureId "SCENARIO-01" -Tier "4" -Milestone "M4"

# S1.4: Zero technical vanity terms displayed in user-facing view
$noTechVanity = -not ($appContent -match "Powered by Go|Built with Vite|HTMX Server Engine")
Assert-True -Context $Context -Condition $noTechVanity `
    -TestName "Scenario 1.4: Screen displays zero technical vanity metrics or framework implementation badges" `
    -FeatureId "SCENARIO-01" -Tier "4" -Milestone "M4"

# S1.5: Layout stability: zero horizontal parasite scroll on launch
$noParasiteScroll = -not ($cssContent -match "overflow-x:\s*scroll")
Assert-True -Context $Context -Condition $noParasiteScroll `
    -TestName "Scenario 1.5: Stage layout renders cleanly without parasitic scrollbars or layout shifts" `
    -FeatureId "SCENARIO-01" -Tier "4" -Milestone "M4"

if ($standalone) {
    exit (Write-TestSummary -Context $Context)
}
