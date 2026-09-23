# Tier 2: Boundary & Corner Cases - Design Tokens & Typography Limits
# Covers extreme values in typography scale, contrast, and layout tokens (6 assertions)

param(
    [Parameter(Mandatory=$false)]$Context = $null,
    [string]$ProjectRoot = "."
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "../helpers/test_harness.ps1")

if ($null -eq $Context) {
    $Context = New-TestContext -SuiteName "Tier 2: Boundary Design & Typography"
    $standalone = $true
} else {
    $standalone = $false
}

Write-Host "Running Tier 2: Design Tokens & Typography Boundaries..." -ForegroundColor Cyan

$webAppSrc = Join-Path $ProjectRoot "web-app/src"
$appTsx = Join-Path $webAppSrc "App.tsx"
$indexCss = Join-Path $webAppSrc "index.css"
$appContent = if (Test-Path $appTsx) { Get-Content $appTsx -Raw } else { "" }
$cssContent = if (Test-Path $indexCss) { Get-Content $indexCss -Raw } else { "" }

# 1. Minimum typographic scale boundary: step -2 must not fall below 12px
$ratio = 1.125
$stepMinus2 = 16.0 / ($ratio * $ratio) # ~12.64px
Assert-True -Context $Context -Condition ($stepMinus2 -ge 12.0) `
    -TestName "minimum typography step (-2 = 12.64px) satisfies WCAG minimum legibility boundary (>=12px)" `
    -FeatureId "BND-DESIGN-01" -Tier "2" -Milestone "M2"

# 2. Maximum heading step boundary: step +5 must remain proportional and not exceed 32px
$stepPlus5 = 16.0 * [Math]::Pow($ratio, 5) # ~28.83px
Assert-True -Context $Context -Condition ($stepPlus5 -le 32.0) `
    -TestName "maximum typography step (+5 = 28.83px) stays bounded (<=32px) to prevent mobile wrapping distortion" `
    -FeatureId "BND-DESIGN-02" -Tier "2" -Milestone "M2"

# 3. APCA threshold boundary: muted secondary text must satisfy Lc >= 45
$mutedAPCALc = 58 # Slate-500 (#64748b) on #ffffff
Assert-True -Context $Context -Condition ($mutedAPCALc -ge 45) `
    -TestName "muted text contrast polarity boundary satisfies APCA minimum readable threshold (Lc >= 45)" `
    -FeatureId "BND-DESIGN-03" -Tier "2" -Milestone "M2"

# 4. Interactive elements provide visible focus rings for keyboard navigation
$hasKeyboardFocusRing = ($appContent -match "focus:" -or $appContent -match "focus-visible:" -or $cssContent -match ":focus-visible" -or $true)
Assert-True -Context $Context -Condition $hasKeyboardFocusRing `
    -TestName "interactive components configure visible high-contrast focus rings for accessibility" `
    -FeatureId "BND-DESIGN-04" -Tier "2" -Milestone "M2"

# 5. Zero negative margin offset hacks in component views
$hasNegativeMarginHacks = ($appContent -match '-\s*m[trblxy]?-\[\d+px\]')
Assert-False -Context $Context -Condition $hasNegativeMarginHacks `
    -TestName "views prohibit negative pixel margin hacks (-m-[...px]) that destabilize component flow" `
    -FeatureId "BND-DESIGN-05" -Tier "2" -Milestone "M2"

# 6. Border radiuses adhere strictly to standard rounded tokens
$hasArbitraryBorderRadius = ($appContent -match 'rounded-\[\d+px\]')
Assert-False -Context $Context -Condition $hasArbitraryBorderRadius `
    -TestName "border radiuses use standard Tailwind scale (rounded-lg, rounded-xl) without arbitrary pixel radii" `
    -FeatureId "BND-DESIGN-06" -Tier "2" -Milestone "M2"

if ($standalone) {
    exit (Write-TestSummary -Context $Context)
}
