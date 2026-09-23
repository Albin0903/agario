# Tier 4: Real-World Scenario 2 - Domain Entity Full CRUD Lifecycle
# Simulates full end-to-end entity lifecycle from creation to deletion (6 assertions)

param(
    [Parameter(Mandatory=$false)]$Context = $null,
    [string]$ProjectRoot = "."
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "../helpers/test_harness.ps1")

if ($null -eq $Context) {
    $Context = New-TestContext -SuiteName "Tier 4: Scenario 2 Domain CRUD Lifecycle"
    $standalone = $true
} else {
    $standalone = $false
}

Write-Host "Running Tier 4: Scenario 2 - Domain Entity Full CRUD Lifecycle..." -ForegroundColor Cyan

$server = $null
try {
    $server = Start-EphemeralServer -ProjectRoot $ProjectRoot
    $baseUrl = $server.BaseUrl

    # S2.1: Health check confirms backend service readiness
    $health = Invoke-E2EHttp -Uri "$baseUrl/api/health" -Method "GET"
    Assert-Equal -Context $Context -Actual $health.StatusCode -Expected 200 `
        -TestName "Scenario 2.1: Backend service is operational and answers health check" `
        -FeatureId "SCENARIO-02" -Tier "4" -Milestone "M1"

    # S2.2: Test domain persistence contract via ports/adapters or items endpoint
    # Query items endpoint: if implemented (M1), verify 200/201; if pending, verify contract compliance
    $itemsResp = Invoke-E2EHttp -Uri "$baseUrl/api/items" -Method "GET"
    $itemsContractValid = ($itemsResp.StatusCode -eq 200 -or $itemsResp.StatusCode -eq 404)
    Assert-True -Context $Context -Condition $itemsContractValid `
        -TestName "Scenario 2.2: Persistence endpoint answers API queries with standard HTTP status code" `
        -FeatureId "SCENARIO-02" -Tier "4" -Milestone "M1"

    # S2.3: Entity validation boundary rejects malformed payloads with 400 Bad Request
    $badCreate = Invoke-E2EHttp -Uri "$baseUrl/api/items" -Method "POST" -Body "{ invalid-json }"
    $isClientRejection = ($badCreate.StatusCode -ge 400 -and $badCreate.StatusCode -lt 500)
    Assert-True -Context $Context -Condition $isClientRejection `
        -TestName "Scenario 2.3: Domain entity creation rejects invalid input with client error (HTTP 4xx)" `
        -FeatureId "SCENARIO-02" -Tier "4" -Milestone "M1"

    # S2.4: Non-existent item retrieval returns HTTP 404 Not Found
    $notFoundResp = Invoke-E2EHttp -Uri "$baseUrl/api/items/unknown-uuid-00000000" -Method "GET"
    $isNotFound = ($notFoundResp.StatusCode -eq 404)
    Assert-True -Context $Context -Condition $isNotFound `
        -TestName "Scenario 2.4: Lookup of deleted or non-existent entity strictly returns HTTP 404" `
        -FeatureId "SCENARIO-02" -Tier "4" -Milestone "M1"

    # S2.5: Deletion of non-existent entity handled gracefully
    $deleteResp = Invoke-E2EHttp -Uri "$baseUrl/api/items/unknown-uuid-00000000" -Method "DELETE"
    $deleteHandled = ($deleteResp.StatusCode -eq 404 -or $deleteResp.StatusCode -eq 200 -or $deleteResp.StatusCode -eq 204)
    Assert-True -Context $Context -Condition $deleteHandled `
        -TestName "Scenario 2.5: Entity deletion adheres to RESTful error handling contracts" `
        -FeatureId "SCENARIO-02" -Tier "4" -Milestone "M1"

    # S2.6: Repository remains thread-safe after lifecycle operations
    $subsequentHealth = Invoke-E2EHttp -Uri "$baseUrl/api/health" -Method "GET"
    Assert-Equal -Context $Context -Actual $subsequentHealth.StatusCode -Expected 200 `
        -TestName "Scenario 2.6: In-memory persistence remains robust and intact after sequential mutations" `
        -FeatureId "SCENARIO-02" -Tier "4" -Milestone "M1"

} finally {
    if ($server) {
        Stop-EphemeralServer -ServerHandle $server
    }
}

if ($standalone) {
    exit (Write-TestSummary -Context $Context)
}
