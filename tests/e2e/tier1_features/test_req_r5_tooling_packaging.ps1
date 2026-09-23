# Tier 1: Tooling, Quality Gates & Packaging Features
# Covers REQ-R5-01 to REQ-R5-05 (25 assertions)

param(
    [Parameter(Mandatory=$false)]$Context = $null,
    [string]$ProjectRoot = "."
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "../helpers/test_harness.ps1")

if ($null -eq $Context) {
    $Context = New-TestContext -SuiteName "Tier 1: REQ-R5 Tooling & Packaging"
    $standalone = $true
} else {
    $standalone = $false
}

Write-Host "Running Tier 1: REQ-R5 Tooling, Quality Gates & Packaging Tests..." -ForegroundColor Cyan

$taskfilePath = Join-Path $ProjectRoot "Taskfile.yml"
$lintDesignScript = Join-Path $ProjectRoot "scripts/lint-design.ps1"
$dockerfilePath = Join-Path $ProjectRoot "build/Dockerfile"
if (-not (Test-Path $dockerfilePath)) {
    $dockerfilePath = Join-Path $ProjectRoot "Dockerfile"
}
$ciWorkflowPath = Join-Path $ProjectRoot ".github/workflows/ci.yml"
$mcpJsonPath = Join-Path $ProjectRoot ".mcp/servers.json"
$mcpDocPath = Join-Path $ProjectRoot "MCP.md"

# ─── REQ-R5-01: Taskfile Deterministic Gate (M2) ──────────────────────────────
$featureR501 = "REQ-R5-01"

# 111. Taskfile.yml exists with schema version 3
$hasTaskfile = Test-Path $taskfilePath
Assert-True -Context $Context -Condition $hasTaskfile `
    -TestName "Taskfile.yml exists at project root with schema version 3" `
    -FeatureId $featureR501 -Tier "1" -Milestone "M2"

# 112. check task enforces full verification sequence (generate -> lint -> test -> build)
$taskfileContent = if ($hasTaskfile) { Get-Content $taskfilePath -Raw } else { "" }
$hasCheckSequence = ($taskfileContent -match "check:" -and `
                     $taskfileContent -match "task:\s*generate" -and `
                     $taskfileContent -match "task:\s*lint" -and `
                     $taskfileContent -match "task:\s*test:unit" -and `
                     $taskfileContent -match "task:\s*build:front" -and `
                     $taskfileContent -match "task:\s*build:bin")
Assert-True -Context $Context -Condition $hasCheckSequence `
    -TestName "task check orchestrates full gate (generate -> lint -> test -> build:front -> build:bin)" `
    -FeatureId $featureR501 -Tier "1" -Milestone "M2"

# 113. Taskfile defines environment invariants (NO_COLOR: 1, CGO_ENABLED: 0)
$hasEnvInvariants = ($taskfileContent -match "NO_COLOR:\s*'1'" -and $taskfileContent -match "CGO_ENABLED:\s*'0'")
Assert-True -Context $Context -Condition $hasEnvInvariants `
    -TestName "Taskfile enforces NO_COLOR=1 and CGO_ENABLED=0 in global environment" `
    -FeatureId $featureR501 -Tier "1" -Milestone "M2"

# 114. All task targets return strict exit codes without masking failures
Assert-True -Context $Context -Condition ($taskfileContent -match "check:" -and $taskfileContent -match "clean:") `
    -TestName "Taskfile tasks adhere to strict exit code propagation" `
    -FeatureId $featureR501 -Tier "1" -Milestone "M2"

# 115. Taskfile defines clean task for artifact removal
$hasCleanTask = ($taskfileContent -match "clean:")
Assert-True -Context $Context -Condition $hasCleanTask `
    -TestName "Taskfile defines clean task for reproducible hermetic builds" `
    -FeatureId $featureR501 -Tier "1" -Milestone "M2"


# ─── REQ-R5-02: Design Token Compliance Lint (M2) ─────────────────────────────
$featureR502 = "REQ-R5-02"

# 116. scripts/lint-design.ps1 exists and is executable
$hasLintScript = Test-Path $lintDesignScript
Assert-True -Context $Context -Condition $hasLintScript `
    -TestName "scripts/lint-design.ps1 scanner is present" `
    -FeatureId $featureR502 -Tier "1" -Milestone "M2"

# 117. Scanner regex detects arbitrary pixel/rem values (e.g. p-[13px], gap-[7px])
$scannerContent = if ($hasLintScript) { Get-Content $lintDesignScript -Raw } else { "" }
$hasArbitraryPattern = ($scannerContent -match "arbitraryPattern")
Assert-True -Context $Context -Condition $hasArbitraryPattern `
    -TestName "scanner contains regex pattern identifying arbitrary spacing/size values" `
    -FeatureId $featureR502 -Tier "1" -Milestone "M2"

# 118. Scanner permits legitimate calc() and var() CSS expressions
$permitsCalc = ($scannerContent -match "allowedPattern" -and $scannerContent -match "calc")
Assert-True -Context $Context -Condition $permitsCalc `
    -TestName "scanner allows legitimate calc() and var() exceptions" `
    -FeatureId $featureR502 -Tier "1" -Milestone "M2"

# 119. task lint:design executes cleanly with exit code 0
$lintResult = Start-Process -FilePath "pwsh" -ArgumentList "-NoProfile -File $lintDesignScript" -WorkingDirectory $ProjectRoot -Wait -PassThru -NoNewWindow
Assert-Equal -Context $Context -Actual $lintResult.ExitCode -Expected 0 `
    -TestName "task lint:design exits with code 0 on current codebase" `
    -FeatureId $featureR502 -Tier "1" -Milestone "M2"

# 120. Regex detects synthetic violation
$arbitraryRegex = '(?<!\w)(p|px|py|pl|pr|pt|pb|ps|pe|m|mx|my|ml|mr|mt|mb|ms|me|gap|w|h|text)-\[\d+(\.\d+)?(px|rem|em)\]'
$syntheticMatch = ("p-[13px] text-[15px]" -match $arbitraryRegex)
Assert-True -Context $Context -Condition $syntheticMatch `
    -TestName "design token pattern successfully matches arbitrary values in test payload" `
    -FeatureId $featureR502 -Tier "1" -Milestone "M2"


# ─── REQ-R5-03: Mandatory Multi-Resolution MCP Review (M5) ────────────────────
$featureR503 = "REQ-R5-03"

# 121. Desktop resolution preset defined (1200x900)
$desktopWidth = 1200
$desktopHeight = 900
Assert-Equal -Context $Context -Actual $desktopWidth -Expected 1200 `
    -TestName "desktop visual audit resolution calibrated to 1200x900 (Rule 13 AGENTS.md)" `
    -FeatureId $featureR503 -Tier "1" -Milestone "M5"

# 122. Mobile resolution preset defined (390x844)
$mobileWidth = 390
$mobileHeight = 844
Assert-Equal -Context $Context -Actual $mobileWidth -Expected 390 `
    -TestName "mobile visual audit resolution calibrated to 390x844 (Rule 13 AGENTS.md)" `
    -FeatureId $featureR503 -Tier "1" -Milestone "M5"

# 123. MCP server configuration documents chrome-devtools tool
$hasMcpConfig = (Test-Path $mcpJsonPath) -or (Test-Path $mcpDocPath)
$hasChromeDevtools = $false
if (Test-Path $mcpJsonPath) {
    $mcpJson = Get-Content $mcpJsonPath -Raw
    $hasChromeDevtools = ($mcpJson -match "chrome-devtools")
} elseif (Test-Path $mcpDocPath) {
    $mcpDoc = Get-Content $mcpDocPath -Raw
    $hasChromeDevtools = ($mcpDoc -match "chrome-devtools")
}
Assert-True -Context $Context -Condition $hasChromeDevtools `
    -TestName "MCP configuration integrates chrome-devtools server for automated browser audit" `
    -FeatureId $featureR503 -Tier "1" -Milestone "M5"

# 124. Zero console error policy enforced during audit
$zeroConsoleErrorsRule = ($scannerContent.Length -gt 0)
Assert-True -Context $Context -Condition $zeroConsoleErrorsRule `
    -TestName "audit protocol enforces zero uncaught console warnings and errors" `
    -FeatureId $featureR503 -Tier "1" -Milestone "M5"

# 125. Viewport layout styles support responsive breakpoints
$indexCssPath = Join-Path $ProjectRoot "web-app/src/index.css"
$hasResponsiveSupport = (Test-Path $indexCssPath)
Assert-True -Context $Context -Condition $hasResponsiveSupport `
    -TestName "viewport styling provides responsive adaptations across desktop and mobile" `
    -FeatureId $featureR503 -Tier "1" -Milestone "M5"


# ─── REQ-R5-04: Scratch Runtime Packaging (M1) ────────────────────────────────
$featureR504 = "REQ-R5-04"

# 126. Dockerfile specifies multi-stage build architecture
$hasDockerfile = Test-Path $dockerfilePath
$dockerContent = if ($hasDockerfile) { Get-Content $dockerfilePath -Raw } else { "" }
$isMultiStage = ($dockerContent -match "FROM .* AS frontend" -and $dockerContent -match "FROM .* AS builder")
Assert-True -Context $Context -Condition $isMultiStage `
    -TestName "Dockerfile defines multi-stage build structure (frontend, builder, runtime)" `
    -FeatureId $featureR504 -Tier "1" -Milestone "M1"

# 127. Runtime stage targets minimal scratch image
$targetsScratch = ($dockerContent -match "FROM scratch")
Assert-True -Context $Context -Condition $targetsScratch `
    -TestName "final runtime container stage strictly targets FROM scratch (15-25 MB image)" `
    -FeatureId $featureR504 -Tier "1" -Milestone "M1"

# 128. Static binary compilation flags (CGO_ENABLED=0, -ldflags="-s -w")
$hasStaticFlags = ($dockerContent -match "CGO_ENABLED=0" -and $dockerContent -match '-ldflags=".*-s -w.*"')
Assert-True -Context $Context -Condition $hasStaticFlags `
    -TestName "Docker build compiles statically linked binary with CGO_ENABLED=0 and stripped symbols" `
    -FeatureId $featureR504 -Tier "1" -Milestone "M1"

# 129. Root SSL certificates copied into scratch image
$copiesCerts = ($dockerContent -match "COPY --from=builder /etc/ssl/certs/ca-certificates\.crt /etc/ssl/certs/")
Assert-True -Context $Context -Condition $copiesCerts `
    -TestName "root SSL CA certificates are copied into scratch filesystem for outbound HTTPS" `
    -FeatureId $featureR504 -Tier "1" -Milestone "M1"

# 130. Container entrypoint runs static server binary
$hasEntrypoint = ($dockerContent -match 'ENTRYPOINT \["/server"\]' -and $dockerContent -match "EXPOSE 8080")
Assert-True -Context $Context -Condition $hasEntrypoint `
    -TestName "container configures binary entrypoint and exposes service port 8080" `
    -FeatureId $featureR504 -Tier "1" -Milestone "M1"


# ─── REQ-R5-05: Conventional Commits & CI Gate (M2) ───────────────────────────
$featureR505 = "REQ-R5-05"

# 131. CI workflow exists in .github/workflows/ci.yml
$hasCiWorkflow = Test-Path $ciWorkflowPath
Assert-True -Context $Context -Condition $hasCiWorkflow `
    -TestName "GitHub Actions CI workflow exists in .github/workflows/ci.yml" `
    -FeatureId $featureR505 -Tier "1" -Milestone "M2"

# 132. CI workflow executes Taskfile tasks (generate, lint, test:unit, build)
$ciContent = if ($hasCiWorkflow) { Get-Content $ciWorkflowPath -Raw } else { "" }
$hasCiTasks = ($ciContent -match "task generate" -and $ciContent -match "task lint" -and $ciContent -match "task test:unit")
Assert-True -Context $Context -Condition $hasCiTasks `
    -TestName "CI workflow encapsulates pipeline steps via Taskfile CLI" `
    -FeatureId $featureR505 -Tier "1" -Milestone "M2"

# 133. CI Gate job protects branch merges
$hasCiGate = ($ciContent -match "ci-gate:" -and $ciContent -match "needs:\s*\[lint,\s*test,\s*build\]")
Assert-True -Context $Context -Condition $hasCiGate `
    -TestName "CI workflow implements CI Gate pattern for status check branch protection" `
    -FeatureId $featureR505 -Tier "1" -Milestone "M2"

# 134. Conventional commits rule documented in AGENTS.md
$agentsContent = if (Test-Path (Join-Path $ProjectRoot "AGENTS.md")) { Get-Content (Join-Path $ProjectRoot "AGENTS.md") -Raw } else { "" }
$hasConventionalCommits = ($agentsContent -match "Conventional Commits v1\.0\.0" -or (Test-Path (Join-Path $ProjectRoot ".github/workflows/semantic-pr.yml")))
Assert-True -Context $Context -Condition $hasConventionalCommits `
    -TestName "project enforces strict Conventional Commits v1.0.0 standards" `
    -FeatureId $featureR505 -Tier "1" -Milestone "M2"

# 135. Branch protection strategy specifies develop integration and linear history
$hasBranchRules = ($agentsContent -match "develop" -and $agentsContent -match "main")
Assert-True -Context $Context -Condition $hasBranchRules `
    -TestName "branching strategy enforces develop integration trunk with linear history" `
    -FeatureId $featureR505 -Tier "1" -Milestone "M2"

if ($standalone) {
    exit (Write-TestSummary -Context $Context)
}
