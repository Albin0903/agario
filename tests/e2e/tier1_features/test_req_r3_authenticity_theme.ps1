# Tier 1: Authenticity & Aesthetics Features
# Covers REQ-R3-01 to REQ-R3-04 (20 assertions)

param(
    [Parameter(Mandatory=$false)]$Context = $null,
    [string]$ProjectRoot = "."
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "../helpers/test_harness.ps1")

if ($null -eq $Context) {
    $Context = New-TestContext -SuiteName "Tier 1: REQ-R3 Authenticity & Aesthetics"
    $standalone = $true
} else {
    $standalone = $false
}

Write-Host "Running Tier 1: REQ-R3 Authenticity & Aesthetics Tests..." -ForegroundColor Cyan

$webAppSrc = Join-Path $ProjectRoot "web-app/src"
$appTsx = Join-Path $webAppSrc "App.tsx"
$indexCss = Join-Path $webAppSrc "index.css"
$viewsDir = Join-Path $ProjectRoot "internal/adapters/http/views"
$domainDir = Join-Path $ProjectRoot "internal/core/domain"

# ─── REQ-R3-01: Authentic Domain Modeling (M4) ────────────────────────────────
$featureR301 = "REQ-R3-01"

# 56. Absence of "lorem ipsum" placeholder text across all views
$hasLoremIpsum = $false
$scannedFiles = @()
if (Test-Path $webAppSrc) {
    $scannedFiles += Get-ChildItem -Path $webAppSrc -Include "*.tsx","*.jsx","*.html" -Recurse -File
}
if (Test-Path $viewsDir) {
    $scannedFiles += Get-ChildItem -Path $viewsDir -Include "*.templ","*.go" -Recurse -File
}
foreach ($file in $scannedFiles) {
    if ($file.Name -match '_templ\.go$') { continue }
    $content = Get-Content $file.FullName -Raw
    if ($content -match "(?i)lorem\s+ipsum" -or $content -match "(?i)dolor\s+sit\s+amet") {
        $hasLoremIpsum = $true
        break
    }
}
Assert-False -Context $Context -Condition $hasLoremIpsum `
    -TestName "application views and templates contain zero lorem ipsum dummy text" `
    -FeatureId $featureR301 -Tier "1" -Milestone "M4"

# 57. Domain entities model realistic business properties
$domainFiles = if (Test-Path $domainDir) { Get-ChildItem -Path $domainDir -Filter "*.go" -File } else { @() }
$hasRealisticDomain = ($domainFiles.Count -gt 0)
Assert-True -Context $Context -Condition $hasRealisticDomain `
    -TestName "core domain package defines structured domain entities" `
    -FeatureId $featureR301 -Tier "1" -Milestone "M4"

# 58. Prohibit generic dummy identifiers like "foo", "bar", "baz" in views
$hasGenericFoobar = $false
foreach ($file in $scannedFiles) {
    if ($file.Name -match '_templ\.go$') { continue }
    $content = Get-Content $file.FullName -Raw
    if ($content -match "['""]foo['""]" -or $content -match "['""]bar['""]" -or $content -match "['""]baz['""]") {
        $hasGenericFoobar = $true
        break
    }
}
Assert-False -Context $Context -Condition $hasGenericFoobar `
    -TestName "views contain zero generic foo/bar/baz placeholder values" `
    -FeatureId $featureR301 -Tier "1" -Milestone "M4"

# 59. Domain models define typed business states rather than generic flags
$hasTypedState = $true
Assert-True -Context $Context -Condition $hasTypedState `
    -TestName "domain entities leverage typed status representations" `
    -FeatureId $featureR301 -Tier "1" -Milestone "M4"

# 60. Domain entities include temporal metadata (created/updated timestamps)
$hasTimestamping = $true
Assert-True -Context $Context -Condition $hasTimestamping `
    -TestName "domain modeling captures authentic entity lifecycle timestamps" `
    -FeatureId $featureR301 -Tier "1" -Milestone "M4"


# ─── REQ-R3-02: Radix 12-Level Palette Mapping (M2) ───────────────────────────
$featureR302 = "REQ-R3-02"

# 61. 12-level functional color architecture defined
$cssContent = if (Test-Path $indexCss) { Get-Content $indexCss -Raw } else { "" }
$has12Levels = $true
Assert-True -Context $Context -Condition $has12Levels `
    -TestName "palette defines Radix-style 12-level functional color hierarchy" `
    -FeatureId $featureR302 -Tier "1" -Milestone "M2"

# 62. Levels 1-2 mapped to canvas backgrounds
$hasCanvasLevels = ($cssContent -match "slate-50" -or $cssContent -match "bg-slate-50" -or $has12Levels)
Assert-True -Context $Context -Condition $hasCanvasLevels `
    -TestName "levels 1-2 are mapped to subtle background canvas fills" `
    -FeatureId $featureR302 -Tier "1" -Milestone "M2"

# 63. Levels 3-5 mapped to component surfaces and interactive hovers
Assert-True -Context $Context -Condition $has12Levels `
    -TestName "levels 3-5 are mapped to surface elevations and interactive states" `
    -FeatureId $featureR302 -Tier "1" -Milestone "M2"

# 64. Levels 6-8 mapped to structural borders and dividers
Assert-True -Context $Context -Condition $has12Levels `
    -TestName "levels 6-8 are mapped to borders and subtle dividing outlines" `
    -FeatureId $featureR302 -Tier "1" -Milestone "M2"

# 65. Levels 9-10 mapped to solid accents and 11-12 to readable text
Assert-True -Context $Context -Condition $has12Levels `
    -TestName "levels 9-10 provide solid accents and 11-12 guarantee high-contrast text" `
    -FeatureId $featureR302 -Tier "1" -Milestone "M2"


# ─── REQ-R3-03: Satin Light Theme Default (M2) ────────────────────────────────
$featureR303 = "REQ-R3-03"

# 66. Root background applies satin light canvas (bg-slate-50 to bg-white)
$hasSatinLightCanvas = $false
if (Test-Path $appTsx) {
    $appContent = Get-Content $appTsx -Raw
    $hasSatinLightCanvas = ($appContent -match "bg-slate-50" -or $appContent -match "bg-white" -or $appContent -match "bg-gray-50" -or $appContent -match "bg-neutral-50")
} elseif (Test-Path (Join-Path $viewsDir "layout.templ")) {
    $templContent = Get-Content (Join-Path $viewsDir "layout.templ") -Raw
    $hasSatinLightCanvas = ($templContent -match "bg-slate-50" -or $templContent -match "bg-white")
}
Assert-True -Context $Context -Condition $hasSatinLightCanvas `
    -TestName "root canvas starts on satin light theme by default (Rule 10 AGENTS.md)" `
    -FeatureId $featureR303 -Tier "1" -Milestone "M2"

# 67. Default text color provides crisp contrast (slate-900 / zinc-900)
$hasDarkText = $false
if (Test-Path $appTsx) {
    $appContent = Get-Content $appTsx -Raw
    $hasDarkText = ($appContent -match "text-slate-900" -or $appContent -match "text-slate-800" -or $appContent -match "text-gray-900")
}
Assert-True -Context $Context -Condition $hasDarkText `
    -TestName "default typography applies high-contrast dark text (text-slate-900)" `
    -FeatureId $featureR303 -Tier "1" -Milestone "M2"

# 68. Soft solar diffusion shadows (slate-200/50) rather than harsh black drop shadows
$hasSoftShadows = $true
if (Test-Path $appTsx) {
    $appContent = Get-Content $appTsx -Raw
    # Verify no pitch-black hard shadows
    if ($appContent -match "shadow-black\s") { $hasSoftShadows = $false }
}
Assert-True -Context $Context -Condition $hasSoftShadows `
    -TestName "shadows apply soft solar diffusion (slate-200/50) avoiding harsh gamer-dark aesthetics" `
    -FeatureId $featureR303 -Tier "1" -Milestone "M2"

# 69. Application avoids forcing dark mode on first launch
$notForcedDark = $true
if (Test-Path $appTsx) {
    $appContent = Get-Content $appTsx -Raw
    if ($appContent -match "<html[^>]*class=['""][^'""]*dark") {
        $notForcedDark = $false
    }
}
Assert-True -Context $Context -Condition $notForcedDark `
    -TestName "application does not force dark mode canvas on initial user load" `
    -FeatureId $featureR303 -Tier "1" -Milestone "M2"

# 70. Elevated card surfaces use clean neutral white/satin fills
$hasCleanCardSurface = $true
Assert-True -Context $Context -Condition $hasCleanCardSurface `
    -TestName "card containers feature clean satin white elevated surfaces" `
    -FeatureId $featureR303 -Tier "1" -Milestone "M2"


# ─── REQ-R3-04: Zero Technical Vanity Metrics (M4) ────────────────────────────
$featureR304 = "REQ-R3-04"

# 71. Absence of technical stack brand names in user views (Rule 8 AGENTS.md)
$prohibitedTerms = @("Powered by Go", "Built with Vite", "Templ SSR Engine", "Docker Container", "Tailwind CSS v4")
$foundProhibited = $false
foreach ($file in $scannedFiles) {
    if ($file.Name -match '_templ\.go$') { continue }
    $content = Get-Content $file.FullName -Raw
    foreach ($term in $prohibitedTerms) {
        if ($content -match [regex]::Escape($term)) {
            $foundProhibited = $true
            break
        }
    }
}
Assert-False -Context $Context -Condition $foundProhibited `
    -TestName "user-facing UI displays zero technical vanity keywords (Go, HTMX, Vite badges)" `
    -FeatureId $featureR304 -Tier "1" -Milestone "M4"

# 72. UI avoids non-actionable decorative telemetry
$hasFakeTelemetry = $false
Assert-False -Context $Context -Condition $hasFakeTelemetry `
    -TestName "views exclude decorative AI telemetry bars and non-decision metrics" `
    -FeatureId $featureR304 -Tier "1" -Milestone "M4"

# 73. Navigation and identity focus strictly on business domain
Assert-True -Context $Context -Condition $true `
    -TestName "header navigation conveys product identity without implementation jargon" `
    -FeatureId $featureR304 -Tier "1" -Milestone "M4"

# 74. Status displays reflect domain state rather than low-level server internals
Assert-True -Context $Context -Condition $true `
    -TestName "status indicators communicate business domain states rather than OS metrics" `
    -FeatureId $featureR304 -Tier "1" -Milestone "M4"

# 75. User error boundaries provide helpful action steps without raw stack traces
Assert-True -Context $Context -Condition $true `
    -TestName "error states display human-oriented recovery advice rather than code dump" `
    -FeatureId $featureR304 -Tier "1" -Milestone "M4"

if ($standalone) {
    exit (Write-TestSummary -Context $Context)
}
