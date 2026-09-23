# Tier 4: Real-World Scenario 5 - Pipeline Gate, Lint & Container Integrity
# Simulates full CI build gate, token compliance, architecture check, and scratch container validation (5 assertions)

param(
    [Parameter(Mandatory=$false)]$Context = $null,
    [string]$ProjectRoot = "."
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "../helpers/test_harness.ps1")

if ($null -eq $Context) {
    $Context = New-TestContext -SuiteName "Tier 4: Scenario 5 Pipeline & Packaging Gate"
    $standalone = $true
} else {
    $standalone = $false
}

Write-Host "Running Tier 4: Scenario 5 - Pipeline Gate, Lint & Container Integrity..." -ForegroundColor Cyan

# S5.1: Full pipeline check executes cleanly
Write-Host "Verifying full pipeline check..."
$env:NO_COLOR = "1"
$taskCheck = Start-Process -FilePath "task" -ArgumentList "check" -WorkingDirectory $ProjectRoot -Wait -PassThru -NoNewWindow
Assert-Equal -Context $Context -Actual $taskCheck.ExitCode -Expected 0 `
    -TestName "Scenario 5.1: Full validation pipeline (task check) exits with code 0" `
    -FeatureId "SCENARIO-05" -Tier "4" -Milestone "M2"

# S5.2: Design token compliance scanner verifies zero arbitrary Tailwind values
Write-Host "Verifying design token compliance..."
$lintScript = Join-Path $ProjectRoot "scripts/lint-design.ps1"
$lintDesign = Start-Process -FilePath "pwsh" -ArgumentList "-NoProfile -File $lintScript" -WorkingDirectory $ProjectRoot -Wait -PassThru -NoNewWindow
Assert-Equal -Context $Context -Actual $lintDesign.ExitCode -Expected 0 `
    -TestName "Scenario 5.2: Design token audit (task lint:design) confirms zero arbitrary Tailwind values" `
    -FeatureId "SCENARIO-05" -Tier "4" -Milestone "M2"

# S5.3: Pure core domain isolation is intact across all Go packages
$coreDir = Join-Path $ProjectRoot "internal/core"
$coreFiles = Get-ChildItem -Path $coreDir -Filter "*.go" -Recurse -File
$coreLeaksAdapters = $false
foreach ($cf in $coreFiles) {
    $c = Get-Content $cf.FullName -Raw
    if ($c -match 'github\.com/[^/]+/build/internal/adapters' -or $c -match '"\.\./\.\./adapters') {
        $coreLeaksAdapters = $true
        break
    }
}
Assert-False -Context $Context -Condition $coreLeaksAdapters `
    -TestName "Scenario 5.3: Pure core domain isolation is preserved without adapter imports" `
    -FeatureId "SCENARIO-05" -Tier "4" -Milestone "M1"

# S5.4: Scratch Dockerfile configures minimal runtime with CA certs and static flags
$dockerfile = Join-Path $ProjectRoot "build/Dockerfile"
if (-not (Test-Path $dockerfile)) { $dockerfile = Join-Path $ProjectRoot "Dockerfile" }
$dockerContent = if (Test-Path $dockerfile) { Get-Content $dockerfile -Raw } else { "" }
$hasValidScratchConfig = ($dockerContent -match "FROM scratch" -and `
                          $dockerContent -match "CGO_ENABLED=0" -and `
                          $dockerContent -match "ca-certificates\.crt")
Assert-True -Context $Context -Condition $hasValidScratchConfig `
    -TestName "Scenario 5.4: Multi-stage Dockerfile builds static binary for minimal scratch runtime" `
    -FeatureId "SCENARIO-05" -Tier "4" -Milestone "M1"

# S5.5: Codebase strictly adheres to zero emoji policy in source files (Rule 1 & Rule 5 AGENTS.md)
$scannedSourceFiles = Get-ChildItem -Path $ProjectRoot -Include "*.go","*.ts","*.tsx","*.templ","*.css","*.json","*.yaml","*.yml" -Recurse -File |
    Where-Object { $_.FullName -notmatch '\\(tmp|web-app\\dist|\.git|\.task|\.agents|node_modules)\\' }
# Target astral plane emojis (emoticons, pictographs, symbols) via surrogate pairs
$emojiPattern = '[\uD83C-\uD83E][\uDC00-\uDFFF]'
$foundEmoji = $false
$emojiOffendingFile = ""
foreach ($sf in $scannedSourceFiles) {
    if ($sf.Name -match '_templ\.go$') { continue }
    if ($sf.Length -gt 500000) { continue }
    $sc = Get-Content $sf.FullName -Raw -ErrorAction SilentlyContinue
    if ($sc -match $emojiPattern) {
        $foundEmoji = $true
        $emojiOffendingFile = $sf.FullName
        break
    }
}
Assert-False -Context $Context -Condition $foundEmoji `
    -TestName "Scenario 5.5: Source files strictly adhere to zero emoji policy (Rule 5 AGENTS.md)" `
    -FeatureId "SCENARIO-05" -Tier "4" -Milestone "M1" -Details "Offending file: $emojiOffendingFile"

if ($standalone) {
    exit (Write-TestSummary -Context $Context)
}
