# E2E Test Harness Utility Module
# Provides assertion helpers, ephemeral process lifecycle management,
# and structured reporting without emojis.

$ErrorActionPreference = "Stop"

function New-TestContext {
    param(
        [string]$SuiteName = "E2E Test Suite"
    )
    return [PSCustomObject]@{
        SuiteName = $SuiteName
        StartTime = [System.DateTime]::UtcNow
        Results   = [System.Collections.Generic.List[PSCustomObject]]::new()
    }
}

function Record-Result {
    param(
        [Parameter(Mandatory=$true)]$Context,
        [Parameter(Mandatory=$true)][string]$Status, # PASS, FAIL, SKIP
        [Parameter(Mandatory=$true)][string]$TestName,
        [string]$FeatureId = "N/A",
        [string]$Tier = "1",
        [string]$Milestone = "M0",
        [string]$Details = "",
        [double]$DurationMs = 0.0
    )
    $result = [PSCustomObject]@{
        Status     = $Status
        TestName   = $TestName
        FeatureId  = $FeatureId
        Tier       = $Tier
        Milestone  = $Milestone
        Details    = $Details
        DurationMs = [Math]::Round($DurationMs, 2)
    }
    $Context.Results.Add($result)

    $color = "Green"
    if ($Status -eq "FAIL") { $color = "Red" }
    elseif ($Status -eq "SKIP") { $color = "Yellow" }

    Write-Host "  [$Status] [Tier $Tier] [$FeatureId] $TestName" -ForegroundColor $color
    if ($Status -eq "FAIL" -and $Details) {
        Write-Host "         Detail: $Details" -ForegroundColor Red
    }
}

function Assert-True {
    param(
        [Parameter(Mandatory=$true)]$Context,
        [Parameter(Mandatory=$true)][bool]$Condition,
        [Parameter(Mandatory=$true)][string]$TestName,
        [string]$FeatureId = "N/A",
        [string]$Tier = "1",
        [string]$Milestone = "M0",
        [string]$Details = ""
    )
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    if ($Condition) {
        $sw.Stop()
        Record-Result -Context $Context -Status "PASS" -TestName $TestName -FeatureId $FeatureId -Tier $Tier -Milestone $Milestone -Details $Details -DurationMs $sw.Elapsed.TotalMilliseconds
    } else {
        $sw.Stop()
        $msg = if ($Details) { $Details } else { "Condition asserted to false, expected true" }
        Record-Result -Context $Context -Status "FAIL" -TestName $TestName -FeatureId $FeatureId -Tier $Tier -Milestone $Milestone -Details $msg -DurationMs $sw.Elapsed.TotalMilliseconds
    }
}

function Assert-False {
    param(
        [Parameter(Mandatory=$true)]$Context,
        [Parameter(Mandatory=$true)][bool]$Condition,
        [Parameter(Mandatory=$true)][string]$TestName,
        [string]$FeatureId = "N/A",
        [string]$Tier = "1",
        [string]$Milestone = "M0",
        [string]$Details = ""
    )
    Assert-True -Context $Context -Condition (-not $Condition) -TestName $TestName -FeatureId $FeatureId -Tier $Tier -Milestone $Milestone -Details $Details
}

function Assert-Equal {
    param(
        [Parameter(Mandatory=$true)]$Context,
        $Actual,
        $Expected,
        [Parameter(Mandatory=$true)][string]$TestName,
        [string]$FeatureId = "N/A",
        [string]$Tier = "1",
        [string]$Milestone = "M0",
        [string]$Details = ""
    )
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $condition = ($Actual -eq $Expected)
    $sw.Stop()
    if ($condition) {
        Record-Result -Context $Context -Status "PASS" -TestName $TestName -FeatureId $FeatureId -Tier $Tier -Milestone $Milestone -Details $Details -DurationMs $sw.Elapsed.TotalMilliseconds
    } else {
        $msg = "Expected '$Expected', got '$Actual'. $Details"
        Record-Result -Context $Context -Status "FAIL" -TestName $TestName -FeatureId $FeatureId -Tier $Tier -Milestone $Milestone -Details $msg -DurationMs $sw.Elapsed.TotalMilliseconds
    }
}

function Assert-Match {
    param(
        [Parameter(Mandatory=$true)]$Context,
        [string]$InputString,
        [string]$Pattern,
        [Parameter(Mandatory=$true)][string]$TestName,
        [string]$FeatureId = "N/A",
        [string]$Tier = "1",
        [string]$Milestone = "M0",
        [string]$Details = ""
    )
    $condition = ($InputString -match $Pattern)
    $msg = if ($condition) { $Details } else { "Pattern '$Pattern' did not match input. $Details" }
    Assert-True -Context $Context -Condition $condition -TestName $TestName -FeatureId $FeatureId -Tier $Tier -Milestone $Milestone -Details $msg
}

function Assert-NotMatch {
    param(
        [Parameter(Mandatory=$true)]$Context,
        [string]$InputString,
        [string]$Pattern,
        [Parameter(Mandatory=$true)][string]$TestName,
        [string]$FeatureId = "N/A",
        [string]$Tier = "1",
        [string]$Milestone = "M0",
        [string]$Details = ""
    )
    $condition = -not ($InputString -match $Pattern)
    $msg = if ($condition) { $Details } else { "Pattern '$Pattern' was found in input when prohibited. $Details" }
    Assert-True -Context $Context -Condition $condition -TestName $TestName -FeatureId $FeatureId -Tier $Tier -Milestone $Milestone -Details $msg
}

function Assert-FileExists {
    param(
        [Parameter(Mandatory=$true)]$Context,
        [string]$FilePath,
        [Parameter(Mandatory=$true)][string]$TestName,
        [string]$FeatureId = "N/A",
        [string]$Tier = "1",
        [string]$Milestone = "M0",
        [string]$Details = ""
    )
    $exists = Test-Path -Path $FilePath
    $msg = if ($exists) { $Details } else { "File not found: '$FilePath'. $Details" }
    Assert-True -Context $Context -Condition $exists -TestName $TestName -FeatureId $FeatureId -Tier $Tier -Milestone $Milestone -Details $msg
}

function Assert-FileContains {
    param(
        [Parameter(Mandatory=$true)]$Context,
        [string]$FilePath,
        [string]$Pattern,
        [Parameter(Mandatory=$true)][string]$TestName,
        [string]$FeatureId = "N/A",
        [string]$Tier = "1",
        [string]$Milestone = "M0",
        [string]$Details = ""
    )
    if (-not (Test-Path -Path $FilePath)) {
        Assert-True -Context $Context -Condition $false -TestName $TestName -FeatureId $FeatureId -Tier $Tier -Milestone $Milestone -Details "File '$FilePath' not found"
        return
    }
    $content = Get-Content -Path $FilePath -Raw
    $condition = ($content -match $Pattern)
    $msg = if ($condition) { $Details } else { "Pattern '$Pattern' not found in '$FilePath'. $Details" }
    Assert-True -Context $Context -Condition $condition -TestName $TestName -FeatureId $FeatureId -Tier $Tier -Milestone $Milestone -Details $msg
}

function Assert-FileNotContains {
    param(
        [Parameter(Mandatory=$true)]$Context,
        [string]$FilePath,
        [string]$Pattern,
        [Parameter(Mandatory=$true)][string]$TestName,
        [string]$FeatureId = "N/A",
        [string]$Tier = "1",
        [string]$Milestone = "M0",
        [string]$Details = ""
    )
    if (-not (Test-Path -Path $FilePath)) {
        Assert-True -Context $Context -Condition $true -TestName $TestName -FeatureId $FeatureId -Tier $Tier -Milestone $Milestone -Details "File not found"
        return
    }
    $content = Get-Content -Path $FilePath -Raw
    $condition = -not ($content -match $Pattern)
    $msg = if ($condition) { $Details } else { "Prohibited pattern '$Pattern' found in '$FilePath'. $Details" }
    Assert-True -Context $Context -Condition $condition -TestName $TestName -FeatureId $FeatureId -Tier $Tier -Milestone $Milestone -Details $msg
}

function Skip-Test {
    param(
        [Parameter(Mandatory=$true)]$Context,
        [string]$Reason,
        [Parameter(Mandatory=$true)][string]$TestName,
        [string]$FeatureId = "N/A",
        [string]$Tier = "1",
        [string]$Milestone = "M0"
    )
    Record-Result -Context $Context -Status "SKIP" -TestName $TestName -FeatureId $FeatureId -Tier $Tier -Milestone $Milestone -Details $Reason -DurationMs 0.0
}

function Find-FreePort {
    param([int]$StartPort = 19000)
    for ($port = $StartPort; $port -lt ($StartPort + 500); $port++) {
        $listener = $null
        try {
            $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $port)
            $listener.Start()
            $listener.Stop()
            return $port
        } catch {
            if ($listener) { $listener.Stop() }
        }
    }
    return 18080
}

function Start-EphemeralServer {
    param(
        [string]$ProjectRoot = ".",
        [int]$Port = 0
    )
    if ($Port -eq 0) {
        $Port = Find-FreePort -StartPort 19100
    }

    $binPath = Join-Path $ProjectRoot "tmp/server.exe"
    if (-not (Test-Path $binPath)) {
        # Build binary if not already built
        $buildCmd = "task build:bin"
        Write-Host "Building server binary via $buildCmd..."
        $procBuild = Start-Process -FilePath "task" -ArgumentList "build:bin" -WorkingDirectory $ProjectRoot -Wait -PassThru -NoNewWindow
        if ($procBuild.ExitCode -ne 0) {
            throw "Failed to build server binary: exit code $($procBuild.ExitCode)"
        }
    }

    $env:PORT = "$Port"
    $env:NO_COLOR = "1"
    $outLog = Join-Path $ProjectRoot "tmp/ephemeral_server_${Port}_out.log"
    $errLog = Join-Path $ProjectRoot "tmp/ephemeral_server_${Port}_err.log"

    $proc = Start-Process -FilePath $binPath `
        -WorkingDirectory $ProjectRoot `
        -PassThru `
        -RedirectStandardOutput $outLog `
        -RedirectStandardError $errLog

    # Wait up to 5 seconds for server to be responsive
    $baseUrl = "http://127.0.0.1:$Port"
    $ready = $false
    $timeout = [System.DateTime]::UtcNow.AddSeconds(5)

    while ([System.DateTime]::UtcNow -lt $timeout) {
        Start-Sleep -Milliseconds 150
        try {
            $resp = Invoke-RestMethod -Uri "$baseUrl/api/health" -TimeoutSec 1 -ErrorAction SilentlyContinue
            if ($resp -and ($resp.ok -or $resp.status -eq "ok")) {
                $ready = $true
                break
            }
        } catch {
            # Continue polling
        }
    }

    if (-not $ready) {
        if (-not $proc.HasExited) { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue }
        $logContent = if (Test-Path $outLog) { Get-Content $outLog -Raw } else { "" }
        throw "Ephemeral server on port $Port did not become ready within 5s. Log: $logContent"
    }

    return [PSCustomObject]@{
        Process = $proc
        Port    = $Port
        BaseUrl = $baseUrl
        LogFile = $outLog
        ErrLog  = $errLog
    }
}

function Stop-EphemeralServer {
    param(
        [Parameter(Mandatory=$true)]$ServerHandle
    )
    if ($ServerHandle -and $ServerHandle.Process -and (-not $ServerHandle.Process.HasExited)) {
        Stop-Process -Id $ServerHandle.Process.Id -Force -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 100
    }
    if ($ServerHandle -and $ServerHandle.LogFile -and (Test-Path $ServerHandle.LogFile)) {
        Remove-Item -Path $ServerHandle.LogFile -Force -ErrorAction SilentlyContinue
    }
    if ($ServerHandle -and $ServerHandle.ErrLog -and (Test-Path $ServerHandle.ErrLog)) {
        Remove-Item -Path $ServerHandle.ErrLog -Force -ErrorAction SilentlyContinue
    }
}

function Invoke-E2EHttp {
    param(
        [Parameter(Mandatory=$true)][string]$Uri,
        [string]$Method = "GET",
        $Body = $null,
        [hashtable]$Headers = @{},
        [int]$TimeoutSec = 5
    )
    $params = @{
        Uri                 = $Uri
        Method              = $Method
        TimeoutSec          = $TimeoutSec
        SkipHttpErrorCheck  = $true
    }
    if ($Headers.Count -gt 0) {
        $params.Headers = $Headers
    }
    if ($Body) {
        if ($Body -is [string]) {
            $params.Body = $Body
        } else {
            $params.Body = ($Body | ConvertTo-Json -Depth 10 -Compress)
            if (-not $params.Headers) { $params.Headers = @{} }
            $params.Headers["Content-Type"] = "application/json"
        }
    }

    try {
        $response = Invoke-WebRequest @params
        $jsonObj = $null
        try {
            $jsonObj = $response.Content | ConvertFrom-Json
        } catch {
            $jsonObj = $null
        }
        return [PSCustomObject]@{
            StatusCode  = [int]$response.StatusCode
            Content     = $response.Content
            Json        = $jsonObj
            Headers     = $response.Headers
            Error       = $null
        }
    } catch {
        return [PSCustomObject]@{
            StatusCode  = 0
            Content     = ""
            Json        = $null
            Headers     = @{}
            Error       = $_.Exception.Message
        }
    }
}

function Write-TestSummary {
    param(
        [Parameter(Mandatory=$true)]$Context,
        [bool]$Strict = $false
    )
    $elapsed = [System.DateTime]::UtcNow - $Context.StartTime
    $total   = $Context.Results.Count
    $passed  = ($Context.Results | Where-Object { $_.Status -eq "PASS" }).Count
    $failed  = ($Context.Results | Where-Object { $_.Status -eq "FAIL" }).Count
    $skipped = ($Context.Results | Where-Object { $_.Status -eq "SKIP" }).Count

    $failColor = if ($failed -gt 0) { "Red" } else { "Gray" }
    $skipColor = if ($skipped -gt 0) { "Yellow" } else { "Gray" }

    Write-Host ""
    Write-Host ("=" * 70)
    Write-Host "Test Suite Summary: $($Context.SuiteName)"
    Write-Host ("=" * 70)
    Write-Host "Total Assertions : $total"
    Write-Host "Passed           : $passed" -ForegroundColor Green
    Write-Host "Failed           : $failed" -ForegroundColor $failColor
    Write-Host "Skipped          : $skipped" -ForegroundColor $skipColor
    Write-Host "Duration         : $([Math]::Round($elapsed.TotalSeconds, 2))s"
    Write-Host ("=" * 70)

    if ($failed -gt 0) {
        Write-Host ""
        Write-Host "FAILURES:" -ForegroundColor Red
        foreach ($item in ($Context.Results | Where-Object { $_.Status -eq "FAIL" })) {
            Write-Host "  - [Tier $($item.Tier)] [$($item.FeatureId)] $($item.TestName)" -ForegroundColor Red
            Write-Host "    $($item.Details)" -ForegroundColor DarkGray
        }
        Write-Host ""
        return 1
    }

    Write-Host "ALL TESTS PASSED" -ForegroundColor Green
    return 0
}
