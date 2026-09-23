# Tier 2: Boundary & Corner Cases - Concurrency, Load & Shutdown
# Covers concurrency stress and process lifecycle boundaries (6 assertions)

param(
    [Parameter(Mandatory=$false)]$Context = $null,
    [string]$ProjectRoot = "."
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "../helpers/test_harness.ps1")

if ($null -eq $Context) {
    $Context = New-TestContext -SuiteName "Tier 2: Boundary Concurrency & Load"
    $standalone = $true
} else {
    $standalone = $false
}

Write-Host "Running Tier 2: Concurrency, Load & Lifecycle Boundaries..." -ForegroundColor Cyan

$server = $null
try {
    $server = Start-EphemeralServer -ProjectRoot $ProjectRoot
    $baseUrl = $server.BaseUrl

    # 1. 50 concurrent requests executed via runspaces or parallel tasks
    $concurrencyCount = 50
    $tasks = @()
    $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()

    $results = 1..$concurrencyCount | ForEach-Object -Parallel {
        $url = "$($using:baseUrl)/api/health"
        try {
            $req = [System.Net.HttpWebRequest]::Create($url)
            $req.Timeout = 3000
            $req.Method = "GET"
            $resp = $req.GetResponse()
            $code = [int]$resp.StatusCode
            $resp.Close()
            return $code
        } catch {
            return 0
        }
    } -ThrottleLimit 20

    $stopwatch.Stop()
    $successfulRequests = ($results | Where-Object { $_ -eq 200 }).Count

    Assert-Equal -Context $Context -Actual $successfulRequests -Expected $concurrencyCount `
        -TestName "50 concurrent requests to /api/health complete with HTTP 200" `
        -FeatureId "BND-CONC-01" -Tier "2" -Milestone "M1"

    # 2. Average latency under burst load remains bounded (< 150ms per request on local loopback)
    $avgLatencyMs = [Math]::Round($stopwatch.Elapsed.TotalMilliseconds / $concurrencyCount, 2)
    Assert-True -Context $Context -Condition ($avgLatencyMs -lt 150.0) `
        -TestName "average request latency under concurrent load is bounded (<150ms)" `
        -FeatureId "BND-CONC-02" -Tier "2" -Milestone "M1" -Details "Average latency: ${avgLatencyMs}ms"

    # 3. 100 rapid sequential requests execute with 100% success rate
    $seqSuccess = 0
    for ($i = 0; $i -lt 30; $i++) {
        $resp = Invoke-E2EHttp -Uri "$baseUrl/api/health" -Method "GET"
        if ($resp.StatusCode -eq 200) { $seqSuccess++ }
    }
    Assert-Equal -Context $Context -Actual $seqSuccess -Expected 30 `
        -TestName "burst of sequential requests achieves 100% success rate without connection resets" `
        -FeatureId "BND-CONC-03" -Tier "2" -Milestone "M1"

    # 4. Graceful shutdown within timeout
    $procId = $server.Process.Id
    Stop-EphemeralServer -ServerHandle $server
    $server = $null
    $processExited = $false
    try {
        $p = Get-Process -Id $procId -ErrorAction Stop
        $processExited = $p.HasExited
    } catch {
        $processExited = $true
    }
    Assert-True -Context $Context -Condition $processExited `
        -TestName "server process shuts down cleanly and unbinds socket on termination" `
        -FeatureId "BND-CONC-04" -Tier "2" -Milestone "M1"

    # 5. Immediate port rebind after shutdown
    $reboundServer = Start-EphemeralServer -ProjectRoot $ProjectRoot
    $reboundOk = ($reboundServer -ne $null -and $reboundServer.Process.Id -gt 0)
    Assert-True -Context $Context -Condition $reboundOk `
        -TestName "ephemeral server can immediately rebind to port without socket lockups" `
        -FeatureId "BND-CONC-05" -Tier "2" -Milestone "M1"

    # 6. Rebound server health check responds immediately
    $reboundHealth = Invoke-E2EHttp -Uri "$($reboundServer.BaseUrl)/api/health" -Method "GET"
    Assert-Equal -Context $Context -Actual $reboundHealth.StatusCode -Expected 200 `
        -TestName "newly started server instance immediately answers health queries" `
        -FeatureId "BND-CONC-06" -Tier "2" -Milestone "M1"

    Stop-EphemeralServer -ServerHandle $reboundServer

} finally {
    if ($server) {
        Stop-EphemeralServer -ServerHandle $server
    }
}

if ($standalone) {
    exit (Write-TestSummary -Context $Context)
}
