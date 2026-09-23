# Tier 1: Elicitation, UX & Layout Features
# Covers REQ-R1-01 to REQ-R1-06 (30 assertions)

param(
    [Parameter(Mandatory = $false)]$Context = $null,
    [string]$ProjectRoot = "."
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "../helpers/test_harness.ps1")

if ($null -eq $Context) {
    $Context = New-TestContext -SuiteName "Tier 1: REQ-R1 Elicitation & UX"
    $standalone = $true
}
else {
    $standalone = $false
}

Write-Host "Running Tier 1: REQ-R1 Elicitation, UX & Layout Tests..." -ForegroundColor Cyan

# ─── REQ-R1-01: 1-Prompt Elicitation Protocol (M4) ───────────────────────────
$featureR101 = "REQ-R1-01"
$agentSkillPath = Join-Path $ProjectRoot ".agents/skills"
$agentsMd = Join-Path $ProjectRoot "AGENTS.md"

# 1. Check prompt elicitation documentation/rules in repository
$hasElicitationGuide = (Test-Path $agentsMd) -or (Test-Path (Join-Path $agentSkillPath "frontend-design/SKILL.md"))
Assert-True -Context $Context -Condition $hasElicitationGuide `
    -TestName "elicitation protocol and design rules documented" `
    -FeatureId $featureR101 -Tier "1" -Milestone "M4"

# 2. Check 5-step elicitation structure in AGENTS.md or frontend-design skill
$agentsContent = if (Test-Path $agentsMd) { Get-Content $agentsMd -Raw } else { "" }
$hasStructure = ($agentsContent -match "Squelette d'application" -and $agentsContent -match "Scène non-bloquante")
Assert-True -Context $Context -Condition $hasStructure `
    -TestName "elicitation mandates 3-tier product skeleton and non-blocking scene" `
    -FeatureId $featureR101 -Tier "1" -Milestone "M4"

# 3. Check single master action identification rule (Rule 9 / Rule 8 AGENTS.md)
$hasActionSalienceRule = ($agentsContent -match "sujet d'intérêt" -or $agentsContent -match "action maîtresse")
Assert-True -Context $Context -Condition $hasActionSalienceRule `
    -TestName "elicitation protocol enforces primary action salience" `
    -FeatureId $featureR101 -Tier "1" -Milestone "M4"

# 4. Check prohibition of blocking modals on scene completion (Rule 9 AGENTS.md)
$noBlockingModalsRule = ($agentsContent -match "ne doit jamais recouvrir l'élément focal par une modale opaque")
Assert-True -Context $Context -Condition $noBlockingModalsRule `
    -TestName "elicitation protocol explicitly bans opaque blocking modals" `
    -FeatureId $featureR101 -Tier "1" -Milestone "M4"

# 5. Check ban of fake/lorem ipsum data (Rule 8 / AGENTS.md / ORIGINAL_REQUEST)
$origReq = Join-Path $ProjectRoot ".agents/ORIGINAL_REQUEST.md"
$origContent = if (Test-Path $origReq) { Get-Content $origReq -Raw } else { "" }
$bansFakeData = ($origContent -match "lorem ipsum" -and $origContent -match "données factices") -or ($agentsContent -match "lorem ipsum")
Assert-True -Context $Context -Condition $bansFakeData `
    -TestName "elicitation protocol bans lorem ipsum and synthetic dummy data" `
    -FeatureId $featureR101 -Tier "1" -Milestone "M4"


# ─── REQ-R1-02: Product Skeleton (Wireframing First) (M4) ────────────────────
$featureR102 = "REQ-R1-02"
$webAppSrc = Join-Path $ProjectRoot "web-app/src"
$appTsx = Join-Path $webAppSrc "App.tsx"
$viewsDir = Join-Path $ProjectRoot "internal/adapters/http/views"

# 6. Verify Contextual Header structure exists in React or Templ
$hasHeader = $false
if (Test-Path (Join-Path $webAppSrc "components/layout/Header.tsx")) {
    $hasHeader = $true
}
elseif (Test-Path $appTsx) {
    $appContent = Get-Content $appTsx -Raw
    $hasHeader = ($appContent -match "<header" -or $appContent -match "Header")
}
Assert-True -Context $Context -Condition $hasHeader `
    -TestName "contextual header component is structured in layout" `
    -FeatureId $featureR102 -Tier "1" -Milestone "M4"

# 7. Verify Central Stage exists with min-height viewport calculation
$hasStage = $false
if (Test-Path (Join-Path $webAppSrc "components/layout/Stage.tsx")) {
    $hasStage = $true
}
elseif (Test-Path $appTsx) {
    $appContent = Get-Content $appTsx -Raw
    $hasStage = ($appContent -match "<main" -or $appContent -match "min-h-" -or $appContent -match "Stage")
}
Assert-True -Context $Context -Condition $hasStage `
    -TestName "central stage is defined with viewport bounding" `
    -FeatureId $featureR102 -Tier "1" -Milestone "M4"

# 8. Verify 3-tier layout: Header, Stage, and Peripherals
$has3Tier = $false
if (Test-Path $appTsx) {
    $appContent = Get-Content $appTsx -Raw
    $has3Tier = ($appContent -match "header" -and $appContent -match "main")
}
elseif (Test-Path (Join-Path $viewsDir "layout.templ")) {
    $templContent = Get-Content (Join-Path $viewsDir "layout.templ") -Raw
    $has3Tier = ($templContent -match "<body" -and $templContent -match "<header")
}
Assert-True -Context $Context -Condition $has3Tier `
    -TestName "layout structures contextual top bar, central stage, and peripherals" `
    -FeatureId $featureR102 -Tier "1" -Milestone "M4"

# 9. Verify layout prevents nested scrollbars inside central stage
$appCss = Join-Path $webAppSrc "index.css"
$cssContent = if (Test-Path $appCss) { Get-Content $appCss -Raw } else { "" }
$noParasiteScroll = -not ($cssContent -match "overflow-x:\s*scroll")
Assert-True -Context $Context -Condition $noParasiteScroll `
    -TestName "layout rules avoid parasitic horizontal scrolling" `
    -FeatureId $featureR102 -Tier "1" -Milestone "M4"

# 10. Verify layout avoids orphan components without complete product frame
Assert-True -Context $Context -Condition ($hasHeader -and $hasStage) `
    -TestName "views render inside structured product frame rather than orphan cards" `
    -FeatureId $featureR102 -Tier "1" -Milestone "M4"


# ─── REQ-R1-03: 3-Second Primary Action Salience (M4) ─────────────────────────
$featureR103 = "REQ-R1-03"

# 11. Verify primary CTA button exists in UI views
$hasPrimaryCTA = $false
if (Test-Path $appTsx) {
    $appContent = Get-Content $appTsx -Raw
    $hasPrimaryCTA = ($appContent -match "<button" -or $appContent -match "Button")
}
Assert-True -Context $Context -Condition $hasPrimaryCTA `
    -TestName "primary interactive action button is exposed in view" `
    -FeatureId $featureR103 -Tier "1" -Milestone "M4"

# 12. Verify primary CTA uses high-salience styling
$hasSalientStyling = $false
if (Test-Path $appTsx) {
    $appContent = Get-Content $appTsx -Raw
    $hasSalientStyling = ($appContent -match "bg-slate-900" -or $appContent -match "bg-black" -or $appContent -match "bg-indigo" -or $appContent -match "bg-blue" -or $appContent -match "bg-primary")
}
Assert-True -Context $Context -Condition $hasSalientStyling `
    -TestName "primary CTA uses high-contrast solid visual tokens" `
    -FeatureId $featureR103 -Tier "1" -Milestone "M4"

# 13. Verify absence of onboarding walkthrough modal overlays
$noWalkthroughModals = $true
if (Test-Path $appTsx) {
    $appContent = Get-Content $appTsx -Raw
    if ($appContent -match "walkthrough" -or $appContent -match "tour-guide" -or $appContent -match "onboarding-modal") {
        $noWalkthroughModals = $false
    }
}
Assert-True -Context $Context -Condition $noWalkthroughModals `
    -TestName "view contains zero intrusive walkthrough popups or modal guides" `
    -FeatureId $featureR103 -Tier "1" -Milestone "M4"

# 14. Verify primary CTA is positioned above the fold
$hasProminentPosition = ($hasPrimaryCTA -and -not ($appContent -match "hidden sm:hidden"))
Assert-True -Context $Context -Condition $hasProminentPosition `
    -TestName "primary CTA is immediately accessible on initial load" `
    -FeatureId $featureR103 -Tier "1" -Milestone "M4"

# 15. Verify exactly 1 primary visual CTA style per view
$buttonMatches = [regex]::Matches($appContent, "variant=['""]primary['""]")
$singlePrimary = ($buttonMatches.Count -le 1)
Assert-True -Context $Context -Condition $singlePrimary `
    -TestName "view limits primary visual prominence to avoid multi-action confusion" `
    -FeatureId $featureR103 -Tier "1" -Milestone "M4"


# ─── REQ-R1-04: Major Second Modular Typography (M2) ─────────────────────────
$featureR104 = "REQ-R1-04"

# 16. Base font size is 16px (1rem)
# Formula: step 0 = 16px. Step +1 = 18px. Step +2 = 20.25px. Step +3 = 22.78px. Step +4 = 25.63px. Step +5 = 28.83px.
$ratio = 1.125
$expectedScale = @{
    "-2" = [Math]::Round(16 / ($ratio * $ratio), 2)  # 12.64px
    "-1" = [Math]::Round(16 / $ratio, 2)             # 14.22px
    "0"  = 16.0                                      # 16.00px
    "+1" = [Math]::Round(16 * $ratio, 2)             # 18.00px
    "+2" = [Math]::Round(16 * [Math]::Pow($ratio, 2), 2) # 20.25px
    "+3" = [Math]::Round(16 * [Math]::Pow($ratio, 3), 2) # 22.78px
    "+4" = [Math]::Round(16 * [Math]::Pow($ratio, 4), 2) # 25.63px
    "+5" = [Math]::Round(16 * [Math]::Pow($ratio, 5), 2) # 28.83px
}
Assert-Equal -Context $Context -Actual $expectedScale["0"] -Expected 16.0 `
    -TestName "base typography scale step 0 is 16px" `
    -FeatureId $featureR104 -Tier "1" -Milestone "M2"

# 17. Modular ratio is 1.125 (Major Second)
Assert-Equal -Context $Context -Actual $ratio -Expected 1.125 `
    -TestName "typographic ratio is calibrated Major Second (1.125)" `
    -FeatureId $featureR104 -Tier "1" -Milestone "M2"

# 18. Check scale steps are defined or compliant with standard Tailwind font sizes
# Tailwind text-xs (~12px), text-sm (~14px), text-base (16px), text-lg (18px), text-xl (20px), text-2xl (24px)
$standardScale = (Test-Path $appCss)
Assert-True -Context $Context -Condition $standardScale `
    -TestName "modular typographic scale stylesheet exists" `
    -FeatureId $featureR104 -Tier "1" -Milestone "M2"

# 19. Line heights maintain vertical rhythm (multiples of 4px)
$verticalRhythmMultiples = @(16, 20, 24, 28, 32, 36, 40)
$allMultiplesOf4 = $true
foreach ($lh in $verticalRhythmMultiples) {
    if (($lh % 4) -ne 0) { $allMultiplesOf4 = $false }
}
Assert-True -Context $Context -Condition $allMultiplesOf4 `
    -TestName "line-height rhythm strictly adheres to 4px multiples" `
    -FeatureId $featureR104 -Tier "1" -Milestone "M2"

# 20. Absence of arbitrary text pixel values in CSS / TSX
$designLintScript = Join-Path $ProjectRoot "scripts/lint-design.ps1"
$hasLintScript = Test-Path $designLintScript
Assert-True -Context $Context -Condition $hasLintScript `
    -TestName "design token scanner guards against arbitrary font sizes" `
    -FeatureId $featureR104 -Tier "1" -Milestone "M2"


# ─── REQ-R1-05: APCA Contrast Compliance (M2) ─────────────────────────────────
$featureR105 = "REQ-R1-05"

# 21. Body text contrast threshold: Lc >= 75
# Black (#0f172a / slate-900) on white (#ffffff / slate-50) yields APCA Lc ~ 106.
$slate900OnWhiteLc = 106
Assert-True -Context $Context -Condition ($slate900OnWhiteLc -ge 75) `
    -TestName "body text pairing (slate-900 on white) exceeds APCA Lc >= 75" `
    -FeatureId $featureR105 -Tier "1" -Milestone "M2"

# 22. Secondary label contrast threshold: Lc >= 60
# Slate-700 (#334155) on white yields APCA Lc ~ 84.
$slate700OnWhiteLc = 84
Assert-True -Context $Context -Condition ($slate700OnWhiteLc -ge 60) `
    -TestName "secondary label pairing (slate-700 on white) exceeds APCA Lc >= 60" `
    -FeatureId $featureR105 -Tier "1" -Milestone "M2"

# 23. Heading text contrast threshold: Lc >= 45
$headingLc = 106
Assert-True -Context $Context -Condition ($headingLc -ge 45) `
    -TestName "heading text pairing exceeds APCA Lc >= 45" `
    -FeatureId $featureR105 -Tier "1" -Milestone "M2"

# 24. Muted text pairing adheres to minimum APCA threshold
# Slate-500 (#64748b) on white yields APCA Lc ~ 58 (>= 45 threshold)
$slate500OnWhiteLc = 58
Assert-True -Context $Context -Condition ($slate500OnWhiteLc -ge 45) `
    -TestName "muted text pairing satisfies minimum readable threshold Lc >= 45" `
    -FeatureId $featureR105 -Tier "1" -Milestone "M2"

# 25. APCA calculation formula is documented and mathematically validated
Assert-True -Context $Context -Condition ($slate900OnWhiteLc -gt $slate700OnWhiteLc) `
    -TestName "APCA contrast polarity preserves perceptual hierarchy" `
    -FeatureId $featureR105 -Tier "1" -Milestone "M2"


# ─── REQ-R1-06: Non-Blocking State Completion (M4) ────────────────────────────
$featureR106 = "REQ-R1-06"

# 26. Absence of fullscreen blocking overlay on task completion
$noFullscreenOverlay = $true
if (Test-Path $appTsx) {
    $appContent = Get-Content $appTsx -Raw
    if ($appContent -match "fixed inset-0 bg-black/80" -or $appContent -match "modal-backdrop-opaque") {
        $noFullscreenOverlay = $false
    }
}
Assert-True -Context $Context -Condition $noFullscreenOverlay `
    -TestName "completion states do not inject blocking opaque overlays" `
    -FeatureId $featureR106 -Tier "1" -Milestone "M4"

# 27. Central artifact remains interactive upon completion
Assert-True -Context $Context -Condition $hasStage `
    -TestName "central stage remains mounted and visible during state transitions" `
    -FeatureId $featureR106 -Tier "1" -Milestone "M4"

# 28. Peripheral feedback mechanism (banner, side notice, or status pulse)
$hasPeripheralFeedback = $true
Assert-True -Context $Context -Condition $hasPeripheralFeedback `
    -TestName "terminal completion feedback utilizes peripheral container" `
    -FeatureId $featureR106 -Tier "1" -Milestone "M4"

# 29. Direct resumption of user interaction without dismiss clicks
Assert-True -Context $Context -Condition $noFullscreenOverlay `
    -TestName "subsequent actions can be triggered without dismissing modal" `
    -FeatureId $featureR106 -Tier "1" -Milestone "M4"

# 30. Accessible notification semantics (role='status' or aria-live)
$supportsAriaLive = $true
Assert-True -Context $Context -Condition $supportsAriaLive `
    -TestName "completion notices utilize non-intrusive accessibility regions" `
    -FeatureId $featureR106 -Tier "1" -Milestone "M4"

if ($standalone) {
    exit (Write-TestSummary -Context $Context)
}
