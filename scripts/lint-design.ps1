# Design Token Compliance Lint
# Detects arbitrary Tailwind CSS values in source files that violate
# the 8px spatial grid and modular typographic scale constraints.

$ErrorActionPreference = "Stop"

$searchPaths = @(
    "internal"
    "web-app/src"
)

$extensions = @("*.templ", "*.tsx", "*.jsx", "*.css")

# Arbitrary pixel/rem/em values in spacing, sizing, typography, and layout utilities.
# Matches patterns like p-[13px], text-[15px], gap-[7px], m-[1.5rem].
$arbitraryPattern = '(?<!\w)(p|px|py|pl|pr|pt|pb|ps|pe|m|mx|my|ml|mr|mt|mb|ms|me|gap|gap-x|gap-y|w|h|text|leading|tracking|rounded|border|shadow|inset|top|right|bottom|left|max-w|min-w|max-h|min-h|basis|space-x|space-y|indent|scroll-m|scroll-p|size)-\[\d+(\.\d+)?(px|rem|em)\]'

# Allowed exceptions: calc() expressions and CSS variables are legitimate.
$allowedPattern = '\[calc\(|var\('

$violations = @()
$scannedFiles = 0

foreach ($searchPath in $searchPaths) {
    $fullPath = Join-Path $PSScriptRoot ".." $searchPath

    if (-not (Test-Path $fullPath)) {
        continue
    }

    foreach ($ext in $extensions) {
        $files = Get-ChildItem -Path $fullPath -Filter $ext -Recurse -File -ErrorAction SilentlyContinue

        foreach ($file in $files) {
            # Skip generated files
            if ($file.Name -match '_templ\.go$') {
                continue
            }

            $scannedFiles++
            $lineNumber = 0
            $content = Get-Content -Path $file.FullName -ErrorAction SilentlyContinue

            foreach ($line in $content) {
                $lineNumber++
                $matches = [regex]::Matches($line, $arbitraryPattern)

                foreach ($match in $matches) {
                    # Check if this match is inside an allowed pattern (calc, var)
                    $context = $line.Substring([Math]::Max(0, $match.Index - 10), [Math]::Min($line.Length - [Math]::Max(0, $match.Index - 10), $match.Length + 20))
                    if ($context -match $allowedPattern) {
                        continue
                    }

                    $relativePath = $file.FullName.Replace((Resolve-Path (Join-Path $PSScriptRoot "..")).Path, "").TrimStart("\", "/")
                    $violations += [PSCustomObject]@{
                        File    = $relativePath
                        Line    = $lineNumber
                        Match   = $match.Value
                        Context = $line.Trim()
                    }
                }
            }
        }
    }
}

Write-Host "Design token lint: scanned $scannedFiles files"

if ($violations.Count -gt 0) {
    Write-Host ""
    Write-Host "FAIL: $($violations.Count) arbitrary value(s) detected" -ForegroundColor Red
    Write-Host ""

    foreach ($v in $violations) {
        Write-Host "  $($v.File):$($v.Line)" -ForegroundColor Yellow -NoNewline
        Write-Host " -> $($v.Match)" -ForegroundColor Red
        Write-Host "    $($v.Context)" -ForegroundColor DarkGray
    }

    Write-Host ""
    Write-Host "Use standard Tailwind scale values instead of arbitrary pixel values." -ForegroundColor Red
    Write-Host "See .agents/skills/design-engineering/SKILL.md for allowed values." -ForegroundColor Red
    exit 1
}
else {
    Write-Host "PASS: no arbitrary values detected" -ForegroundColor Green
    exit 0
}

