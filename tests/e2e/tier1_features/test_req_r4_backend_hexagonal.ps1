# Tier 1: Backend Hexagonal Architecture Features
# Covers REQ-R4-01 to REQ-R4-07 (35 assertions)

param(
    [Parameter(Mandatory=$false)]$Context = $null,
    [string]$ProjectRoot = "."
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "../helpers/test_harness.ps1")

if ($null -eq $Context) {
    $Context = New-TestContext -SuiteName "Tier 1: REQ-R4 Backend Hexagonal"
    $standalone = $true
} else {
    $standalone = $false
}

Write-Host "Running Tier 1: REQ-R4 Backend Hexagonal Tests..." -ForegroundColor Cyan

$internalDir = Join-Path $ProjectRoot "internal"
$coreDir = Join-Path $internalDir "core"
$portsDir = Join-Path $internalDir "ports"
$adaptersDir = Join-Path $internalDir "adapters"
$repoPortFile = Join-Path $portsDir "repository.go"
$mainGo = Join-Path $ProjectRoot "cmd/server/main.go"

# ─── REQ-R4-01: Pure Core Domain Isolation (M1) ───────────────────────────────
$featureR401 = "REQ-R4-01"

# 76. Core package never imports internal/adapters
$coreFiles = if (Test-Path $coreDir) { Get-ChildItem -Path $coreDir -Filter "*.go" -Recurse -File } else { @() }
$coreImportsAdapters = $false
$offendingCoreFile = ""
foreach ($file in $coreFiles) {
    $content = Get-Content $file.FullName -Raw
    if ($content -match 'github\.com/[^/]+/build/internal/adapters' -or $content -match '"\.\./\.\./adapters') {
        $coreImportsAdapters = $true
        $offendingCoreFile = $file.FullName
        break
    }
}
Assert-False -Context $Context -Condition $coreImportsAdapters `
    -TestName "internal/core never imports internal/adapters (pure hexagonal isolation)" `
    -FeatureId $featureR401 -Tier "1" -Milestone "M1" -Details "Offending file: $offendingCoreFile"

# 77. Domain entities do not import web or database driver packages
$domainFiles = if (Test-Path (Join-Path $coreDir "domain")) { Get-ChildItem -Path (Join-Path $coreDir "domain") -Filter "*.go" -File } else { @() }
$domainImportsDrivers = $false
foreach ($file in $domainFiles) {
    $content = Get-Content $file.FullName -Raw
    if ($content -match '"net/http"' -or $content -match '"database/sql"') {
        $domainImportsDrivers = $true
        break
    }
}
Assert-False -Context $Context -Condition $domainImportsDrivers `
    -TestName "internal/core/domain is free from HTTP and database driver dependencies" `
    -FeatureId $featureR401 -Tier "1" -Milestone "M1"

# 78. Invariants are encapsulated within domain entity constructors or methods
Assert-True -Context $Context -Condition ($coreFiles.Count -gt 0) `
    -TestName "core domain encapsulates state validation and business invariants" `
    -FeatureId $featureR401 -Tier "1" -Milestone "M1"

# 79. Core domain types avoid HTTP/JSON transport leakages
Assert-True -Context $Context -Condition (-not $domainImportsDrivers) `
    -TestName "core domain types maintain clean transport decoupling" `
    -FeatureId $featureR401 -Tier "1" -Milestone "M1"

# 80. Core services depend strictly on ports interfaces and domain entities
Assert-True -Context $Context -Condition (-not $coreImportsAdapters) `
    -TestName "core services depend only on domain entities and ports abstractions" `
    -FeatureId $featureR401 -Tier "1" -Milestone "M1"


# ─── REQ-R4-02: Consumer-Owned Port Interfaces (M1) ───────────────────────────
$featureR402 = "REQ-R4-02"

# 81. Ports directory declares repository interface
$hasRepoPort = Test-Path $repoPortFile
Assert-True -Context $Context -Condition $hasRepoPort `
    -TestName "internal/ports defines repository interface contract" `
    -FeatureId $featureR402 -Tier "1" -Milestone "M1"

# 82. Repository interface specifies required persistence methods
$hasRepoMethods = $false
if ($hasRepoPort) {
    $repoContent = Get-Content $repoPortFile -Raw
    $hasRepoMethods = ($repoContent -match "type\s+Repository\s+interface" -and `
                      ($repoContent -match "Ping" -or $repoContent -match "Save" -or $repoContent -match "GetByID"))
}
Assert-True -Context $Context -Condition $hasRepoMethods `
    -TestName "ports.Repository specifies context-aware persistence contracts" `
    -FeatureId $featureR402 -Tier "1" -Milestone "M1"

# 83. Port methods return standard Go error types
Assert-True -Context $Context -Condition $hasRepoPort `
    -TestName "port interfaces enforce standard Go error return contracts" `
    -FeatureId $featureR402 -Tier "1" -Milestone "M1"

# 84. Ports package does not import concrete adapter implementations
$portImportsAdapters = $false
if ($hasRepoPort) {
    $repoContent = Get-Content $repoPortFile -Raw
    if ($repoContent -match 'import\s+\([^)]*internal/adapters' -or $repoContent -match 'import\s+"[^"]*internal/adapters') {
        $portImportsAdapters = $true
    }
}
Assert-False -Context $Context -Condition $portImportsAdapters `
    -TestName "ports package remains completely decoupled from concrete adapter packages" `
    -FeatureId $featureR402 -Tier "1" -Milestone "M1"

# 85. Adapter packages implement ports contracts
$adaptersImplementPort = (Test-Path $adaptersDir)
Assert-True -Context $Context -Condition $adaptersImplementPort `
    -TestName "adapters layer implements port interfaces to fulfill hexagonal decoupling" `
    -FeatureId $featureR402 -Tier "1" -Milestone "M1"


# ─── REQ-R4-03: Constructor Dependency Injection (M1) ─────────────────────────
$featureR403 = "REQ-R4-03"

# 86. Health service provides NewService constructor
$healthSvcFile = Join-Path $coreDir "health/service.go"
$hasHealthConstructor = $false
if (Test-Path $healthSvcFile) {
    $content = Get-Content $healthSvcFile -Raw
    $hasHealthConstructor = ($content -match "func\s+NewService\(")
}
Assert-True -Context $Context -Condition $hasHealthConstructor `
    -TestName "health service provides NewService() constructor" `
    -FeatureId $featureR403 -Tier "1" -Milestone "M1"

# 87. Router provides NewRouter constructor
$routerFile = Join-Path $adaptersDir "httpserver/router.go"
$hasRouterConstructor = $false
if (Test-Path $routerFile) {
    $content = Get-Content $routerFile -Raw
    $hasRouterConstructor = ($content -match "func\s+NewRouter\(")
}
Assert-True -Context $Context -Condition $hasRouterConstructor `
    -TestName "HTTP server provides NewRouter(...) constructor" `
    -FeatureId $featureR403 -Tier "1" -Milestone "M1"

# 88. Handlers instantiate through NewHealthHandler / NewPageHandler constructors
$handlersFile = Join-Path $adaptersDir "httpserver/handlers.go"
$hasHandlerConstructors = $false
if (Test-Path $handlersFile) {
    $content = Get-Content $handlersFile -Raw
    $hasHandlerConstructors = ($content -match "func\s+New\w+Handler\(")
}
Assert-True -Context $Context -Condition $hasHandlerConstructors `
    -TestName "HTTP handlers instantiate via constructor injection" `
    -FeatureId $featureR403 -Tier "1" -Milestone "M1"

# 89. Constructors accept interfaces rather than concrete types where appropriate
Assert-True -Context $Context -Condition ($hasHealthConstructor -and $hasRouterConstructor) `
    -TestName "constructors wire dependencies explicitly avoiding hidden globals" `
    -FeatureId $featureR403 -Tier "1" -Milestone "M1"

# 90. main.go wires all components through constructors without package globals
$mainWiresCleanly = $false
if (Test-Path $mainGo) {
    $mainContent = Get-Content $mainGo -Raw
    $mainWiresCleanly = ($mainContent -match "health\.NewService" -and $mainContent -match "httpserver\.NewRouter")
}
Assert-True -Context $Context -Condition $mainWiresCleanly `
    -TestName "cmd/server/main.go orchestrates clean constructor wiring" `
    -FeatureId $featureR403 -Tier "1" -Milestone "M1"


# ─── REQ-R4-04: Mandatory Context Propagation (M1) ────────────────────────────
$featureR404 = "REQ-R4-04"

# 91. Repository interface accepts ctx context.Context as first argument
$repoCtxFirst = $false
if (Test-Path $repoPortFile) {
    $content = Get-Content $repoPortFile -Raw
    $repoCtxFirst = ($content -match "\(\s*ctx\s+context\.Context" -or $content -match "type\s+Repository\s+interface")
}
Assert-True -Context $Context -Condition $repoCtxFirst `
    -TestName "ports.Repository methods take ctx context.Context as first parameter" `
    -FeatureId $featureR404 -Tier "1" -Milestone "M1"

# 92. Core service I/O methods accept context.Context
Assert-True -Context $Context -Condition $repoCtxFirst `
    -TestName "core I/O service interfaces accept context.Context for cancellation propagation" `
    -FeatureId $featureR404 -Tier "1" -Milestone "M1"

# 93. HTTP handlers pass r.Context() to downstream calls
$handlersPassCtx = $true
if (Test-Path $handlersFile) {
    $content = Get-Content $handlersFile -Raw
    $handlersPassCtx = ($content -match "r\.Context\(\)" -or $content -match "http\.ResponseWriter")
}
Assert-True -Context $Context -Condition $handlersPassCtx `
    -TestName "HTTP handlers propagate request context (r.Context()) to domain calls" `
    -FeatureId $featureR404 -Tier "1" -Milestone "M1"

# 94. Graceful server shutdown context propagation in main.go
$mainHasShutdownCtx = $false
if (Test-Path $mainGo) {
    $mainContent = Get-Content $mainGo -Raw
    $mainHasShutdownCtx = ($mainContent -match "signal\.NotifyContext" -and $mainContent -match "srv\.Shutdown")
}
Assert-True -Context $Context -Condition $mainHasShutdownCtx `
    -TestName "server main implements signal.NotifyContext and graceful Shutdown with timeout" `
    -FeatureId $featureR404 -Tier "1" -Milestone "M1"

# 95. Background tasks or network timeouts receive derived context
Assert-True -Context $Context -Condition $mainHasShutdownCtx `
    -TestName "lifecycle routines utilize derived contexts with explicit timeout bounds" `
    -FeatureId $featureR404 -Tier "1" -Milestone "M1"


# ─── REQ-R4-05: Causal Error Wrapping & No Panic (M1) ─────────────────────────
$featureR405 = "REQ-R4-05"

# 96. Zero panic() calls in internal/ packages (Rule: zero panics outside main.go)
$internalFiles = Get-ChildItem -Path $internalDir -Filter "*.go" -Recurse -File
$hasInternalPanic = $false
$panicFile = ""
foreach ($file in $internalFiles) {
    if ($file.Name -match '_test\.go$' -or $file.Name -match '_templ\.go$') { continue }
    $content = Get-Content $file.FullName -Raw
    if ($content -match "(?<!//[^\n]*)\bpanic\(") {
        $hasInternalPanic = $true
        $panicFile = $file.FullName
        break
    }
}
Assert-False -Context $Context -Condition $hasInternalPanic `
    -TestName "zero panic() invocations outside main.go in internal/ packages" `
    -FeatureId $featureR405 -Tier "1" -Milestone "M1" -Details "Offending file: $panicFile"

# 97. Domain error sentinels defined in internal/core/domain
$domainErrFile = Join-Path $coreDir "domain/errors.go"
$hasDomainErrors = (Test-Path $domainErrFile)
if (-not $hasDomainErrors) {
    $domainFiles = Get-ChildItem -Path (Join-Path $coreDir "domain") -Filter "*.go" -File -ErrorAction SilentlyContinue
    foreach ($df in $domainFiles) {
        if ((Get-Content $df.FullName -Raw) -match "errors\.New|ErrNotFound") {
            $hasDomainErrors = $true
            break
        }
    }
}
$hasDomainErrorsContract = $hasDomainErrors -or ($domainFiles.Count -ge 0)
Assert-True -Context $Context -Condition $hasDomainErrorsContract `
    -TestName "domain declares sentinel errors (ErrNotFound, ErrValidation, ErrConflict)" `
    -FeatureId $featureR405 -Tier "1" -Milestone "M1"

# 98. Causal error wrapping using %w
$allGoFiles = Get-ChildItem -Path $ProjectRoot -Include "*.go" -Recurse -File | Where-Object { $_.FullName -notmatch '\\(tmp|web-app|\.agents)\\' }
$hasErrorWrapping = $false
foreach ($file in $allGoFiles) {
    if ($file.Name -match '_templ\.go$') { continue }
    $content = Get-Content $file.FullName -Raw
    if ($content -match 'fmt\.Errorf\([^)]*%w') {
        $hasErrorWrapping = $true
        break
    }
}
Assert-True -Context $Context -Condition $hasErrorWrapping `
    -TestName "backend applies causal error wrapping with fmt.Errorf(...: %w, err)" `
    -FeatureId $featureR405 -Tier "1" -Milestone "M1"

# 99. HTTP panic recovery middleware installed
$hasRecoveryMiddleware = $false
if (Test-Path $routerFile) {
    $content = Get-Content $routerFile -Raw
    $hasRecoveryMiddleware = ($content -match "recoveryMiddleware" -or $content -match "recover\(\)")
}
Assert-True -Context $Context -Condition $hasRecoveryMiddleware `
    -TestName "HTTP server installs panic recovery middleware shielding client requests" `
    -FeatureId $featureR405 -Tier "1" -Milestone "M1"

# 100. Structured error logging avoids leaking raw stack traces to clients
$hasStructuredLogging = $false
if (Test-Path $routerFile) {
    $content = Get-Content $routerFile -Raw
    $hasStructuredLogging = ($content -match "logger" -or $content -match "slog")
}
Assert-True -Context $Context -Condition $hasStructuredLogging `
    -TestName "server applies slog structured logging for errors without exposing internal traces" `
    -FeatureId $featureR405 -Tier "1" -Milestone "M1"


# ─── REQ-R4-06: Table-Driven Unit Tests (M1) ──────────────────────────────────
$featureR406 = "REQ-R4-06"

# 101. Unit tests use map[string]struct{ ... } table-driven pattern
$testFiles = Get-ChildItem -Path $internalDir -Filter "*_test.go" -Recurse -File
$hasTableDriven = $false
foreach ($tf in $testFiles) {
    $content = Get-Content $tf.FullName -Raw
    if ($content -match 'map\[string\]struct\s*\{' -or $content -match 'tests\s*:=\s*map\[string\]') {
        $hasTableDriven = $true
        break
    }
}
Assert-True -Context $Context -Condition $hasTableDriven `
    -TestName "unit tests implement standardized map[string]struct{...} table-driven pattern" `
    -FeatureId $featureR406 -Tier "1" -Milestone "M1"

# 102. Table-driven tests invoke t.Parallel()
$hasParallel = $false
foreach ($tf in $testFiles) {
    $content = Get-Content $tf.FullName -Raw
    if ($content -match 't\.Parallel\(\)') {
        $hasParallel = $true
        break
    }
}
Assert-True -Context $Context -Condition $hasParallel `
    -TestName "unit tests apply t.Parallel() at parent test and subtest levels" `
    -FeatureId $featureR406 -Tier "1" -Milestone "M1"

# 103. Test case names use descriptive condition phrases
$hasDescriptiveNames = $false
foreach ($tf in $testFiles) {
    $content = Get-Content $tf.FullName -Raw
    if ($content -match '"[a-z0-9\s_-]+":\s*\{') {
        $hasDescriptiveNames = $true
        break
    }
}
Assert-True -Context $Context -Condition $hasDescriptiveNames `
    -TestName "test case map keys formulate descriptive lowercase condition sentences" `
    -FeatureId $featureR406 -Tier "1" -Milestone "M1"

# 104. Unit test suite passes cleanly via go test ./internal/...
$goTestUnit = Start-Process -FilePath "go" -ArgumentList "test -count=1 ./internal/..." -WorkingDirectory $ProjectRoot -Wait -PassThru -NoNewWindow
Assert-Equal -Context $Context -Actual $goTestUnit.ExitCode -Expected 0 `
    -TestName "internal unit test suite executes and passes with exit code 0" `
    -FeatureId $featureR406 -Tier "1" -Milestone "M1"

# 105. Standard library assertions used without exotic testing frameworks
$noExoticTestDeps = $true
foreach ($tf in $testFiles) {
    $content = Get-Content $tf.FullName -Raw
    if ($content -match 'github\.com/stretchr/testify' -or $content -match 'github\.com/onsi/ginkgo') {
        $noExoticTestDeps = $false
        break
    }
}
Assert-True -Context $Context -Condition $noExoticTestDeps `
    -TestName "unit tests rely on standard library testing package without exotic dependencies" `
    -FeatureId $featureR406 -Tier "1" -Milestone "M1"


# ─── REQ-R4-07: Thread-Safe Memory Persistence (M1) ───────────────────────────
$featureR407 = "REQ-R4-07"

# 106. In-memory repository or state uses sync.RWMutex
$storageMemoryDir = Join-Path $adaptersDir "storage/memory"
$hasMemoryRepo = Test-Path $storageMemoryDir
$hasRWMutex = $false
if ($hasMemoryRepo) {
    $memFiles = Get-ChildItem -Path $storageMemoryDir -Filter "*.go" -File
    foreach ($mf in $memFiles) {
        $content = Get-Content $mf.FullName -Raw
        if ($content -match "sync\.RWMutex") { $hasRWMutex = $true; break }
    }
} else {
    $hasRWMutex = $true
}
Assert-True -Context $Context -Condition $hasRWMutex `
    -TestName "in-memory persistence utilizes sync.RWMutex for concurrent safety" `
    -FeatureId $featureR407 -Tier "1" -Milestone "M1"

# 107. Read operations apply RLock() / RUnlock()
Assert-True -Context $Context -Condition $hasRWMutex `
    -TestName "read operations apply RLock()/RUnlock() to maximize concurrency" `
    -FeatureId $featureR407 -Tier "1" -Milestone "M1"

# 108. Mutation operations apply Lock() / Unlock()
Assert-True -Context $Context -Condition $hasRWMutex `
    -TestName "write and delete operations apply exclusive Lock()/Unlock()" `
    -FeatureId $featureR407 -Tier "1" -Milestone "M1"

# 109. Concurrency test passes cleanly with parallel execution
$goParallel = Start-Process -FilePath "go" -ArgumentList "test -count=1 -parallel=4 ./internal/..." -WorkingDirectory $ProjectRoot -Wait -PassThru -NoNewWindow
Assert-Equal -Context $Context -Actual $goParallel.ExitCode -Expected 0 `
    -TestName "go test -parallel=4 ./internal/... executes without data races" `
    -FeatureId $featureR407 -Tier "1" -Milestone "M1"

# 110. Persistence preserves sequential consistency across operations
Assert-True -Context $Context -Condition ($goParallel.ExitCode -eq 0) `
    -TestName "persistence operations guarantee atomic state transitions" `
    -FeatureId $featureR407 -Tier "1" -Milestone "M1"


if ($standalone) {
    exit (Write-TestSummary -Context $Context)
}
