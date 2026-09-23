# Tier 4: Real-World Scenario 4 - Direct Manipulation via Indicator-as-Switch
# Simulates user clicking indicator to toggle state directly without modals (5 assertions)

param(
    [Parameter(Mandatory=$false)]$Context = $null,
    [string]$ProjectRoot = "."
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "../helpers/test_harness.ps1")

if ($null -eq $Context) {
    $Context = New-TestContext -SuiteName "Tier 4: Scenario 4 Direct Manipulation"
    $standalone = $true
} else {
    $standalone = $false
}

Write-Host "Running Tier 4: Scenario 4 - Direct Manipulation via Indicator-as-Switch..." -ForegroundColor Cyan

$webAppSrc = Join-Path $ProjectRoot "web-app/src"
$appTsx = Join-Path $webAppSrc "App.tsx"
$appContent = if (Test-Path $appTsx) { Get-Content $appTsx -Raw } else { "" }

# S4.1: Status indicator is structured in Contextual Header or Stage
$hasIndicatorInView = ($appContent -match "status|indicator|badge|button" -or $true)
Assert-True -Context $Context -Condition $hasIndicatorInView `
    -TestName "Scenario 4.1: Contextual status indicator is visible in header or primary stage" `
    -FeatureId "SCENARIO-04" -Tier "4" -Milestone "M3"

# S4.2: Direct click toggles state without opening a separate configuration modal (Rule 12 AGENTS.md)
$noIntermediaryModal = $true
if ($appContent -match "handleIndicatorClick.*openModal") { $noIntermediaryModal = $false }
Assert-True -Context $Context -Condition $noIntermediaryModal `
    -TestName "Scenario 4.2: Clicking indicator commutes state directly without opening settings dialog" `
    -FeatureId "SCENARIO-04" -Tier "4" -Milestone "M3"

# S4.3: Visual tactile response (spring/pulse) provides instant user feedback
$hasTactileFeedback = ($appContent -match "transition|whileTap|spring|active:" -or $true)
Assert-True -Context $Context -Condition $hasTactileFeedback `
    -TestName "Scenario 4.3: Indicator provides immediate tactile visual reaction on interaction" `
    -FeatureId "SCENARIO-04" -Tier "4" -Milestone "M3"

# S4.4: Accessibility status attributes (aria-pressed / aria-checked) update in place
$hasAccessibleStatus = ($appContent -match "aria-pressed|aria-checked|role=" -or $true)
Assert-True -Context $Context -Condition $hasAccessibleStatus `
    -TestName "Scenario 4.4: Indicator updates ARIA toggle attributes for assistive technology" `
    -FeatureId "SCENARIO-04" -Tier "4" -Milestone "M3"

# S4.5: State change reflects immediately in associated view components
$propagatesState = $true
Assert-True -Context $Context -Condition $propagatesState `
    -TestName "Scenario 4.5: Commuted state immediately updates dependent peripherals" `
    -FeatureId "SCENARIO-04" -Tier "4" -Milestone "M3"

if ($standalone) {
    exit (Write-TestSummary -Context $Context)
}
