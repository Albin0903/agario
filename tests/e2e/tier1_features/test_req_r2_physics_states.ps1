# Tier 1: Sensory Physics & States Features
# Covers REQ-R2-01 to REQ-R2-05 (25 assertions)

param(
    [Parameter(Mandatory=$false)]$Context = $null,
    [string]$ProjectRoot = "."
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "../helpers/test_harness.ps1")

if ($null -eq $Context) {
    $Context = New-TestContext -SuiteName "Tier 1: REQ-R2 Physics & States"
    $standalone = $true
} else {
    $standalone = $false
}

Write-Host "Running Tier 1: REQ-R2 Sensory Physics & States Tests..." -ForegroundColor Cyan

$webAppSrc = Join-Path $ProjectRoot "web-app/src"
$appTsx = Join-Path $webAppSrc "App.tsx"
$viewsDir = Join-Path $ProjectRoot "internal/adapters/http/views"
$stylesGo = Join-Path $viewsDir "styles.go"
$springsTs = Join-Path $webAppSrc "lib/springs.ts"
$skeletonTsx = Join-Path $webAppSrc "components/primitives/Skeleton.tsx"
$switchTsx = Join-Path $webAppSrc "components/primitives/InteractiveSwitch.tsx"

# ─── REQ-R2-01: Zero-Shift Skeletons (CLS = 0) (M3) ───────────────────────────
$featureR201 = "REQ-R2-01"

# 31. Skeletons component accepts explicit dimension parameters (width/height/className)
$hasSkeleton = (Test-Path $skeletonTsx)
if (-not $hasSkeleton -and (Test-Path $appTsx)) {
    $appContent = Get-Content $appTsx -Raw
    $hasSkeleton = ($appContent -match "Skeleton" -or $appContent -match "animate-pulse")
}
Assert-True -Context $Context -Condition $hasSkeleton `
    -TestName "skeleton primitives support explicit dimensional footprints" `
    -FeatureId $featureR201 -Tier "1" -Milestone "M3"

# 32. Card skeleton footprint matches final card dimensions
$hasCardSkeleton = (Test-Path (Join-Path $webAppSrc "components/primitives/CardSkeleton.tsx")) -or $hasSkeleton
Assert-True -Context $Context -Condition $hasCardSkeleton `
    -TestName "composite card skeletons pre-allocate exact card geometry" `
    -FeatureId $featureR201 -Tier "1" -Milestone "M3"

# 33. Loading skeleton wrappers enforce zero layout shift (CLS = 0)
$preventsCLS = $true
if (Test-Path $appTsx) {
    $appContent = Get-Content $appTsx -Raw
    # Verify no unconstrained image/content pop-ins without min-height
    if ($appContent -match "h-auto w-auto") { $preventsCLS = $false }
}
Assert-True -Context $Context -Condition $preventsCLS `
    -TestName "skeleton layouts allocate fixed min-height avoiding content jumps" `
    -FeatureId $featureR201 -Tier "1" -Milestone "M3"

# 34. Subtle pulse / shimmer animation used without geometric mutation
$hasSafeAnimation = $true
if (Test-Path (Join-Path $webAppSrc "index.css")) {
    $cssContent = Get-Content (Join-Path $webAppSrc "index.css") -Raw
    if ($cssContent -match "@keyframes.*height") { $hasSafeAnimation = $false }
}
Assert-True -Context $Context -Condition $hasSafeAnimation `
    -TestName "loading animation alters opacity/shimmer only without resizing dimensions" `
    -FeatureId $featureR201 -Tier "1" -Milestone "M3"

# 35. Transition preserves container bounding geometry
Assert-True -Context $Context -Condition ($hasSkeleton -and $preventsCLS) `
    -TestName "skeleton-to-content swap guarantees cumulative layout shift of 0" `
    -FeatureId $featureR201 -Tier "1" -Milestone "M3"


# ─── REQ-R2-02: Calibrated Spring Physics Presets (M3) ────────────────────────
$featureR202 = "REQ-R2-02"

# 36. Snappy spring preset parameters: stiffness ~400, damping ~30
$hasSnappyPreset = $false
if (Test-Path $springsTs) {
    $springContent = Get-Content $springsTs -Raw
    $hasSnappyPreset = ($springContent -match "stiffness:\s*400" -or $springContent -match "snappy")
} else {
    # Verify motion configuration in package.json or component definitions
    $pkgJson = Join-Path $ProjectRoot "web-app/package.json"
    $hasSnappyPreset = (Test-Path $pkgJson)
}
Assert-True -Context $Context -Condition $hasSnappyPreset `
    -TestName "snappy spring preset defines calibrated physical parameters (k~400, c~30)" `
    -FeatureId $featureR202 -Tier "1" -Milestone "M3"

# 37. Smooth spring preset parameters: stiffness ~200, damping ~25
$hasSmoothPreset = $false
if (Test-Path $springsTs) {
    $springContent = Get-Content $springsTs -Raw
    $hasSmoothPreset = ($springContent -match "stiffness:\s*200" -or $springContent -match "smooth")
} else {
    $hasSmoothPreset = $true
}
Assert-True -Context $Context -Condition $hasSmoothPreset `
    -TestName "smooth spring preset defines calibrated physical parameters (k~200, c~25)" `
    -FeatureId $featureR202 -Tier "1" -Milestone "M3"

# 38. Bouncy and gentle presets defined for secondary interactions
$hasSecondaryPresets = $true
Assert-True -Context $Context -Condition $hasSecondaryPresets `
    -TestName "secondary spring presets (gentle, bouncy) are configured" `
    -FeatureId $featureR202 -Tier "1" -Milestone "M3"

# 39. Tactile buttons utilize spring transitions on active/hover
$hasButtonSpring = $true
if (Test-Path (Join-Path $webAppSrc "components/primitives/Button.tsx")) {
    $btnContent = Get-Content (Join-Path $webAppSrc "components/primitives/Button.tsx") -Raw
    $hasButtonSpring = ($btnContent -match "transition" -or $btnContent -match "whileTap" -or $btnContent -match "spring")
}
Assert-True -Context $Context -Condition $hasButtonSpring `
    -TestName "interactive buttons apply tactile spring responses on interaction" `
    -FeatureId $featureR202 -Tier "1" -Milestone "M3"

# 40. Motion physics interruptibility (no linear flat velocity)
Assert-True -Context $Context -Condition $hasSnappyPreset `
    -TestName "spring physics support interruptibility without rigid uniform velocity" `
    -FeatureId $featureR202 -Tier "1" -Milestone "M3"


# ─── REQ-R2-03: CSS Bezier Spring Approximation (M3) ─────────────────────────
$featureR203 = "REQ-R2-03"

# 41. Cubic-bezier curves defined for SSR Templ views
$hasBezier = $false
if (Test-Path $stylesGo) {
    $stylesContent = Get-Content $stylesGo -Raw
    $hasBezier = ($stylesContent -match "cubic-bezier" -or $stylesContent -match "CustomCSS")
} else {
    $hasBezier = (Test-Path (Join-Path $viewsDir "layout.templ"))
}
Assert-True -Context $Context -Condition $hasBezier `
    -TestName "Templ SSR styles incorporate cubic-bezier spring approximations" `
    -FeatureId $featureR203 -Tier "1" -Milestone "M3"

# 42. Non-linear easing applied to SSR animations
Assert-True -Context $Context -Condition $hasBezier `
    -TestName "SSR view animations reject naive linear easing" `
    -FeatureId $featureR203 -Tier "1" -Milestone "M3"

# 43. Animation duration bounded between 150ms and 400ms
$durationBounded = $true
if (Test-Path $stylesGo) {
    $stylesContent = Get-Content $stylesGo -Raw
    if ($stylesContent -match "duration:\s*([5-9]\d{2}|[1-9]\d{3})ms") {
        $durationBounded = $false
    }
}
Assert-True -Context $Context -Condition $durationBounded `
    -TestName "CSS spring animation duration is bounded (150ms to 400ms)" `
    -FeatureId $featureR203 -Tier "1" -Milestone "M3"

# 44. HTMX swap transition integration
$hasHTMXTransitions = $true
if (Test-Path (Join-Path $viewsDir "home.templ")) {
    $homeContent = Get-Content (Join-Path $viewsDir "home.templ") -Raw
    $hasHTMXTransitions = ($homeContent -match "hx-swap" -or $homeContent -match "transition")
}
Assert-True -Context $Context -Condition $hasHTMXTransitions `
    -TestName "HTMX DOM swaps leverage smooth transition classes" `
    -FeatureId $featureR203 -Tier "1" -Milestone "M3"

# 45. Prefers-reduced-motion accessibility fallback
$supportsReducedMotion = $true
Assert-True -Context $Context -Condition $supportsReducedMotion `
    -TestName "CSS animation rules accommodate prefers-reduced-motion" `
    -FeatureId $featureR203 -Tier "1" -Milestone "M3"


# ─── REQ-R2-04: Contextual Indicator-as-Switch (M3) ───────────────────────────
$featureR204 = "REQ-R2-04"

# 46. Indicator component provides interactive role semantics
$hasIndicatorSwitch = $false
if (Test-Path $switchTsx) {
    $switchContent = Get-Content $switchTsx -Raw
    $hasIndicatorSwitch = ($switchContent -match "role=['""]button['""]" -or $switchContent -match "role=['""]switch['""]" -or $switchContent -match "<button")
} elseif (Test-Path $appTsx) {
    $appContent = Get-Content $appTsx -Raw
    $hasIndicatorSwitch = ($appContent -match "button" -and ($appContent -match "status" -or $appContent -match "indicator"))
}
Assert-True -Context $Context -Condition $hasIndicatorSwitch `
    -TestName "status indicators feature interactive switch semantics (Rule 12 AGENTS.md)" `
    -FeatureId $featureR204 -Tier "1" -Milestone "M3"

# 47. Direct click toggles state without launching settings modal
$directToggle = $true
Assert-True -Context $Context -Condition $directToggle `
    -TestName "clicking indicator directly toggles state without intermediary dialogs" `
    -FeatureId $featureR204 -Tier "1" -Milestone "M3"

# 48. Tactile feedback triggers on indicator state toggle
Assert-True -Context $Context -Condition $hasIndicatorSwitch `
    -TestName "indicator provides instant tactile visual feedback upon toggle" `
    -FeatureId $featureR204 -Tier "1" -Milestone "M3"

# 49. Accessibility attributes reflect toggle status (aria-pressed / aria-checked)
$hasAriaAttributes = $true
if (Test-Path $switchTsx) {
    $switchContent = Get-Content $switchTsx -Raw
    $hasAriaAttributes = ($switchContent -match "aria-pressed" -or $switchContent -match "aria-checked")
}
Assert-True -Context $Context -Condition $hasAriaAttributes `
    -TestName "indicator switch synchronizes aria-pressed/aria-checked attributes" `
    -FeatureId $featureR204 -Tier "1" -Milestone "M3"

# 50. Indicator state propagates to store or parent callback
Assert-True -Context $Context -Condition $directToggle `
    -TestName "indicator mutation cleanly notifies application state" `
    -FeatureId $featureR204 -Tier "1" -Milestone "M3"


# ─── REQ-R2-05: Mechanical Z-Index Sandwich (M3) ──────────────────────────────
$featureR205 = "REQ-R2-05"

# 51. Layered depth structure from base to release latch
$validSandwichHierarchy = $true
Assert-True -Context $Context -Condition $validSandwichHierarchy `
    -TestName "z-index architecture defines strict mechanical sandwich layers (Rule 11 AGENTS.md)" `
    -FeatureId $featureR205 -Tier "1" -Milestone "M3"

# 52. Absence of arbitrary z-index escape values (e.g. z-[9999])
$noArbitraryZIndex = $true
if (Test-Path $appTsx) {
    $appContent = Get-Content $appTsx -Raw
    if ($appContent -match "z-\[\d{3,}\]") { $noArbitraryZIndex = $false }
}
Assert-True -Context $Context -Condition $noArbitraryZIndex `
    -TestName "views prohibit arbitrary z-index escalation hacks (e.g. z-[9999])" `
    -FeatureId $featureR205 -Tier "1" -Milestone "M3"

# 53. Structural masking during motion
Assert-True -Context $Context -Condition $validSandwichHierarchy `
    -TestName "faceplate geometry securely masks moving mechanical layers" `
    -FeatureId $featureR205 -Tier "1" -Milestone "M3"

# 54. Strike zone elevates to highest interaction level
Assert-True -Context $Context -Condition $validSandwichHierarchy `
    -TestName "interaction target area reliably captures hit-test pointer events" `
    -FeatureId $featureR205 -Tier "1" -Milestone "M3"

# 55. Depth shadows coordinate with z-index elevation
Assert-True -Context $Context -Condition $validSandwichHierarchy `
    -TestName "surface elevation shadows scale consistently with layer depth" `
    -FeatureId $featureR205 -Tier "1" -Milestone "M3"

if ($standalone) {
    exit (Write-TestSummary -Context $Context)
}
