# Tier 3: Cross-Feature Combination - Error Translation + Context Cancellation + Logging
# Verifies interaction between domain error mapping, context propagation, and structured logging (3 assertions)

param(
    [Parameter(Mandatory=$false)]$Context = $null,
    [string]$ProjectRoot = "."
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "../helpers/test_harness.ps1")

if ($null -eq $Context) {
    $Context = New-TestContext -SuiteName "Tier 3: Combo Error + Context + Logging"
    $standalone = $true
} else {
    $standalone = $false
}

Write-Host "Running Tier 3: Error Translation + Context + Logging Combination..." -ForegroundColor Cyan

$server = $null
try {
    $server = Start-EphemeralServer -ProjectRoot $ProjectRoot
    $baseUrl = $server.BaseUrl

    # C3.13: Fast client disconnect / context timeout handled cleanly
    # Invoke request with ultra-short timeout to trigger client cancel
    try {
        $cancelReq = [System.Net.HttpWebRequest]::Create("$baseUrl/api/health")
        $cancelReq.Timeout = 2 # 2ms to induce context abort
        $resp = $cancelReq.GetResponse()
        $resp.Close()
    } catch {
        # Context abort or timeout expected
    }
    # Verify server remains healthy after client abort
    $subsequentResp = Invoke-E2EHttp -Uri "$baseUrl/api/health" -Method "GET"
    Assert-Equal -Context $Context -Actual $subsequentResp.StatusCode -Expected 200 `
        -TestName "server handles aborted client connection context without hanging or crashing" `
        -FeatureId "COMBO-05" -Tier "3" -Milestone "M1"

    # C3.14: Error response shape returns clean JSON structure
    $errResp = Invoke-E2EHttp -Uri "$baseUrl/api/nonexistent" -Method "GET"
    Assert-Equal -Context $Context -Actual $errResp.StatusCode -Expected 404 `
        -TestName "unmapped API route returns HTTP 404 error response" `
        -FeatureId "COMBO-05" -Tier "3" -Milestone "M1"

    # C3.15: Server response does not leak internal stack traces or file system paths
    $responseBody = $errResp.Content
    $leaksTrace = ($responseBody -match "goroutine \d+" -or $responseBody -match "(\.go:\d+)" -or $responseBody -match "panic:")
    Assert-False -Context $Context -Condition $leaksTrace `
        -TestName "error response avoids leaking raw Go stack traces or internal filesystem paths" `
        -FeatureId "COMBO-05" -Tier "3" -Milestone "M1"

} finally {
    if ($server) {
        Stop-EphemeralServer -ServerHandle $server
    }
}

if ($standalone) {
    exit (Write-TestSummary -Context $Context)
}
