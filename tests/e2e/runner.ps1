# Master E2E Test Runner
# Orchestrates test execution across Tiers 1-4 for the build template.
# Conforms to AGENTS.md anti-vibe coding invariants (zero emoji, strict exit codes).

param(
    [ValidateSet("1", "2", "3", "4", "All")]
    [string]$Tier = "All",

    [ValidateSet("M1", "M2", "M3", "M4", "M5", "All")]
    [string]$Milestone = "All",

    [string]$Feature = "",

    [switch]$Strict,

    [string]$ProjectRoot = "."
)

$ErrorActionPreference = "Stop"
$scriptDir = $PSScriptRoot
. (Join-Path $scriptDir "helpers/test_harness.ps1")

# Resolve absolute project root
$resolvedRoot = (Resolve-Path (Join-Path $scriptDir "../..")).Path

Write-Host ""
Write-Host ("=" * 70)
Write-Host "build Template Master E2E Test Runner"
Write-Host "Configuration:"
Write-Host "  Project Root : $resolvedRoot"
Write-Host "  Tier Filter  : $Tier"
Write-Host "  Milestone    : $Milestone"
if ($Feature) {
    Write-Host "  Feature ID   : $Feature"
}
Write-Host ("=" * 70)
Write-Host ""

$masterContext = New-TestContext -SuiteName "build Template Master E2E Test Suite"

# ─── Execute Tier 1: Comprehensive Feature Coverage ───────────────────────────
if ($Tier -eq "1" -or $Tier -eq "All") {
    Write-Host "======================================================================"
    Write-Host "TIER 1: FEATURE COVERAGE (27 FEATURES, >=5 CASES PER FEATURE)"
    Write-Host "======================================================================"

    & (Join-Path $scriptDir "tier1_features/test_req_r1_elicitation_ux.ps1") -Context $masterContext -ProjectRoot $resolvedRoot
    & (Join-Path $scriptDir "tier1_features/test_req_r2_physics_states.ps1") -Context $masterContext -ProjectRoot $resolvedRoot
    & (Join-Path $scriptDir "tier1_features/test_req_r3_authenticity_theme.ps1") -Context $masterContext -ProjectRoot $resolvedRoot
    & (Join-Path $scriptDir "tier1_features/test_req_r4_backend_hexagonal.ps1") -Context $masterContext -ProjectRoot $resolvedRoot
    & (Join-Path $scriptDir "tier1_features/test_req_r5_tooling_packaging.ps1") -Context $masterContext -ProjectRoot $resolvedRoot
}

# ─── Execute Tier 2: Boundary & Corner Cases ──────────────────────────────────
if ($Tier -eq "2" -or $Tier -eq "All") {
    Write-Host ""
    Write-Host "======================================================================"
    Write-Host "TIER 2: BOUNDARY & CORNER CASES (>=5 CASES PER CATEGORY)"
    Write-Host "======================================================================"

    & (Join-Path $scriptDir "tier2_boundaries/test_bnd_api_payloads.ps1") -Context $masterContext -ProjectRoot $resolvedRoot
    & (Join-Path $scriptDir "tier2_boundaries/test_bnd_concurrency_load.ps1") -Context $masterContext -ProjectRoot $resolvedRoot
    & (Join-Path $scriptDir "tier2_boundaries/test_bnd_layout_viewports.ps1") -Context $masterContext -ProjectRoot $resolvedRoot
    & (Join-Path $scriptDir "tier2_boundaries/test_bnd_design_typography.ps1") -Context $masterContext -ProjectRoot $resolvedRoot
}

# ─── Execute Tier 3: Cross-Feature Combinations ───────────────────────────────
if ($Tier -eq "3" -or $Tier -eq "All") {
    Write-Host ""
    Write-Host "======================================================================"
    Write-Host "TIER 3: CROSS-FEATURE COMBINATIONS (PAIRWISE INTERACTIONS)"
    Write-Host "======================================================================"

    & (Join-Path $scriptDir "tier3_combinations/test_combo_skeleton_spring_domain.ps1") -Context $masterContext -ProjectRoot $resolvedRoot
    & (Join-Path $scriptDir "tier3_combinations/test_combo_indicator_persistence.ps1") -Context $masterContext -ProjectRoot $resolvedRoot
    & (Join-Path $scriptDir "tier3_combinations/test_combo_skeleton_stage_completion.ps1") -Context $masterContext -ProjectRoot $resolvedRoot
    & (Join-Path $scriptDir "tier3_combinations/test_combo_palette_theme_apca.ps1") -Context $masterContext -ProjectRoot $resolvedRoot
    & (Join-Path $scriptDir "tier3_combinations/test_combo_error_context_logging.ps1") -Context $masterContext -ProjectRoot $resolvedRoot
    & (Join-Path $scriptDir "tier3_combinations/test_combo_docker_scratch_health.ps1") -Context $masterContext -ProjectRoot $resolvedRoot
}

# ─── Execute Tier 4: Real-World Application Scenarios ─────────────────────────
if ($Tier -eq "4" -or $Tier -eq "All") {
    Write-Host ""
    Write-Host "======================================================================"
    Write-Host "TIER 4: REAL-WORLD APPLICATION SCENARIOS (5 END-TO-END FLOWS)"
    Write-Host "======================================================================"

    & (Join-Path $scriptDir "tier4_scenarios/test_scenario_1_first_launch.ps1") -Context $masterContext -ProjectRoot $resolvedRoot
    & (Join-Path $scriptDir "tier4_scenarios/test_scenario_2_domain_crud_lifecycle.ps1") -Context $masterContext -ProjectRoot $resolvedRoot
    & (Join-Path $scriptDir "tier4_scenarios/test_scenario_3_async_task_zero_shift.ps1") -Context $masterContext -ProjectRoot $resolvedRoot
    & (Join-Path $scriptDir "tier4_scenarios/test_scenario_4_direct_manipulation.ps1") -Context $masterContext -ProjectRoot $resolvedRoot
    & (Join-Path $scriptDir "tier4_scenarios/test_scenario_5_gate_and_container_integrity.ps1") -Context $masterContext -ProjectRoot $resolvedRoot
}

# ─── Milestone or Feature Filtering (if requested) ───────────────────────────
$activeResults = $masterContext.Results
if ($Milestone -ne "All") {
    $activeResults = $masterContext.Results | Where-Object { $_.Milestone -eq $Milestone }
}
if ($Feature -ne "") {
    $activeResults = $activeResults | Where-Object { $_.FeatureId -eq $Feature }
}

# ─── Tier Breakdown Reporting ─────────────────────────────────────────────────
$elapsed = [System.DateTime]::UtcNow - $masterContext.StartTime

Write-Host ""
Write-Host ("=" * 70)
Write-Host "MASTER E2E TEST REPORT"
Write-Host ("=" * 70)

$tiers = @("1", "2", "3", "4")
foreach ($t in $tiers) {
    $tierResults = $activeResults | Where-Object { $_.Tier -eq $t }
    $tTotal = $tierResults.Count
    $tPassed = ($tierResults | Where-Object { $_.Status -eq "PASS" }).Count
    $tFailed = ($tierResults | Where-Object { $_.Status -eq "FAIL" }).Count
    $tSkipped = ($tierResults | Where-Object { $_.Status -eq "SKIP" }).Count

    if ($tTotal -gt 0) {
        $color = if ($tFailed -gt 0) { "Red" } else { "Green" }
        Write-Host "  Tier $t : $tTotal tests | Passed: $tPassed | Failed: $tFailed | Skipped: $tSkipped" -ForegroundColor $color
    }
}

$totalAll   = $activeResults.Count
$passedAll  = ($activeResults | Where-Object { $_.Status -eq "PASS" }).Count
$failedAll  = ($activeResults | Where-Object { $_.Status -eq "FAIL" }).Count
$skippedAll = ($activeResults | Where-Object { $_.Status -eq "SKIP" }).Count

Write-Host ("-" * 70)
Write-Host "Total Assertions : $totalAll"
Write-Host "Total Passed     : $passedAll" -ForegroundColor Green
$failSummaryColor = if ($failedAll -gt 0) { "Red" } else { "Gray" }
$skipSummaryColor = if ($skippedAll -gt 0) { "Yellow" } else { "Gray" }
Write-Host "Total Failed     : $failedAll" -ForegroundColor $failSummaryColor
Write-Host "Total Skipped    : $skippedAll" -ForegroundColor $skipSummaryColor
Write-Host "Execution Time   : $([Math]::Round($elapsed.TotalSeconds, 2))s"
Write-Host ("=" * 70)

if ($failedAll -gt 0) {
    Write-Host ""
    Write-Host "FAILED ASSERTIONS DETAILS:" -ForegroundColor Red
    foreach ($item in ($activeResults | Where-Object { $_.Status -eq "FAIL" })) {
        Write-Host "  - [Tier $($item.Tier)] [$($item.FeatureId)] $($item.TestName)" -ForegroundColor Red
        if ($item.Details) {
            Write-Host "    Details: $($item.Details)" -ForegroundColor DarkGray
        }
    }
    Write-Host ""
    exit 1
}

Write-Host ""
Write-Host "ALL E2E TESTS PASSED" -ForegroundColor Green
Write-Host ""
exit 0
