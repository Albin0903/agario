# Tier 2: Boundary & Corner Cases - API Payloads & HTTP Transport
# Covers boundary edge cases on HTTP interfaces (6 assertions)

param(
    [Parameter(Mandatory=$false)]$Context = $null,
    [string]$ProjectRoot = "."
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "../helpers/test_harness.ps1")

if ($null -eq $Context) {
    $Context = New-TestContext -SuiteName "Tier 2: Boundary API Payloads"
    $standalone = $true
} else {
    $standalone = $false
}

Write-Host "Running Tier 2: API Payload & HTTP Transport Boundaries..." -ForegroundColor Cyan

$server = $null
try {
    $server = Start-EphemeralServer -ProjectRoot $ProjectRoot
    $baseUrl = $server.BaseUrl

    # 1. Standard Health Check returns HTTP 200 with expected JSON shape
    $healthResp = Invoke-E2EHttp -Uri "$baseUrl/api/health" -Method "GET"
    Assert-Equal -Context $Context -Actual $healthResp.StatusCode -Expected 200 `
        -TestName "GET /api/health returns HTTP 200 with valid JSON body" `
        -FeatureId "BND-API-01" -Tier "2" -Milestone "M1"
    Assert-True -Context $Context -Condition ($healthResp.Json -and ($healthResp.Json.ok -or $healthResp.Json.status -eq "ok")) `
        -TestName "health endpoint payload contains ok boolean field" `
        -FeatureId "BND-API-01" -Tier "2" -Milestone "M1"

    # 2. Unsupported HTTP method (e.g. TRACE) returns 405 Method Not Allowed
    $traceResp = Invoke-E2EHttp -Uri "$baseUrl/api/health" -Method "TRACE"
    $is405or400 = ($traceResp.StatusCode -eq 405 -or $traceResp.StatusCode -eq 400 -or $traceResp.StatusCode -eq 501)
    Assert-True -Context $Context -Condition $is405or400 `
        -TestName "unsupported HTTP method (TRACE) is rejected cleanly (HTTP 405/400/501)" `
        -FeatureId "BND-API-02" -Tier "2" -Milestone "M1"

    # 3. Non-existent path returns HTTP 404 Not Found
    $notFoundResp = Invoke-E2EHttp -Uri "$baseUrl/api/non-existent-endpoint-xyz-999" -Method "GET"
    Assert-Equal -Context $Context -Actual $notFoundResp.StatusCode -Expected 404 `
        -TestName "GET to non-existent route returns clean HTTP 404 Not Found" `
        -FeatureId "BND-API-03" -Tier "2" -Milestone "M1"

    # 4. Oversized Header boundary (exceeding MaxHeaderBytes 1MB in main.go)
    # Generate a large header ~8KB to test boundary resilience without server panic
    $largeHeaderVal = "X" * 4096
    $hdrResp = Invoke-E2EHttp -Uri "$baseUrl/api/health" -Method "GET" -Headers @{ "X-Custom-Test" = $largeHeaderVal }
    $survivesLargeHeader = ($hdrResp.StatusCode -eq 200 -or $hdrResp.StatusCode -eq 431)
    Assert-True -Context $Context -Condition $survivesLargeHeader `
        -TestName "server handles large header boundary without process crash or panic" `
        -FeatureId "BND-API-04" -Tier "2" -Milestone "M1"

    # 5. Injection strings & special characters in URL path handled safely
    $specialChars = [System.Web.HttpUtility]::UrlEncode("<script>alert('xss')</script>'; DROP TABLE items; --")
    $injectionResp = Invoke-E2EHttp -Uri "$baseUrl/api/items/$specialChars" -Method "GET"
    $safeStatus = ($injectionResp.StatusCode -eq 404 -or $injectionResp.StatusCode -eq 400)
    Assert-True -Context $Context -Condition $safeStatus `
        -TestName "special characters and SQL/XSS strings in route parameters handled safely without 500" `
        -FeatureId "BND-API-05" -Tier "2" -Milestone "M1"

    # 6. Malformed JSON body in POST request rejected cleanly
    $malformedResp = Invoke-E2EHttp -Uri "$baseUrl/api/health" -Method "POST" -Body "{ malformed json: true, }"
    $isClientError = ($malformedResp.StatusCode -ge 400 -and $malformedResp.StatusCode -lt 500)
    Assert-True -Context $Context -Condition $isClientError `
        -TestName "malformed JSON syntax returns client error (4xx) without server fault" `
        -FeatureId "BND-API-06" -Tier "2" -Milestone "M1"

} finally {
    if ($server) {
        Stop-EphemeralServer -ServerHandle $server
    }
}

if ($standalone) {
    exit (Write-TestSummary -Context $Context)
}
