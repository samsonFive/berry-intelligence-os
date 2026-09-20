# Start Berry OS locally on Windows for Today / thumbs-up publishing.
# Requires Python 3.12. Python 3.14 cannot build pinned pydantic-core==2.33.2.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

function Find-Python312 {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $exe = & py -3.12 -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $exe) { return ([string]$exe).Trim() }
        foreach ($line in @(& py -0p 2>$null)) {
            if ($line -match '3\.12' -and $line -match '([A-Za-z]:\\[^\s]+python\.exe)') {
                return $Matches[1]
            }
        }
    }
    foreach ($name in @("python3.12", "python312")) {
        if (Get-Command $name -ErrorAction SilentlyContinue) {
            $exe = & $name -c "import sys; print(sys.executable)" 2>$null
            if ($exe) { return ([string]$exe).Trim() }
        }
    }
    return $null
}

$python = Find-Python312
if (-not $python) {
    Write-Host "Python 3.12 is required. This repo does not install on Python 3.14."
    Write-Host "Install 3.12, close this window, open a new PowerShell, then re-run:"
    Write-Host "  winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements"
    Write-Host "Or install https://www.python.org/downloads/release/python-31210/ (check 'py launcher')"
    exit 1
}

$ver = & $python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ($ver -notmatch '^3\.12') {
    Write-Host "Expected Python 3.12, got $ver at $python"
    exit 1
}

if (-not (Test-Path .venv\Scripts\python.exe)) {
    Write-Host "Creating .venv with $python ($ver)"
    & $python -m venv .venv
} else {
    $venvVer = & .\.venv\Scripts\python.exe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    if ($venvVer -notmatch '^3\.12') {
        Write-Host "Existing .venv is Python $venvVer. Recreating with 3.12."
        Remove-Item -Recurse -Force .venv
        & $python -m venv .venv
    }
}

Write-Host "Installing requirements with Python $ver ..."
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (Test-Path .env) {
    Get-Content .env | ForEach-Object {
        if ($_ -match '^\s*#' -or $_ -notmatch '=') { return }
        $name, $value = $_ -split '=', 2
        [Environment]::SetEnvironmentVariable($name.Trim(), $value.Trim().Trim('"'), "Process")
    }
}

$hostName = if ($env:BIOS_APP_BIND) { $env:BIOS_APP_BIND } else { "127.0.0.1" }
$port = if ($env:BIOS_APP_PORT) { $env:BIOS_APP_PORT } else { "8000" }
$browserHost = if ($hostName -eq "0.0.0.0") { "127.0.0.1" } else { $hostName }
$appUrl = "http://${browserHost}:${port}/today"
Write-Host "Berry OS → $appUrl"
Write-Host "Refresh live lanes on Today if the feed looks stale. Thumbs-up is the publish path."

# Open the user's normal external browser only after uvicorn answers. The
# server remains in this foreground window so Ctrl+C still stops it cleanly.
if ($env:BIOS_NO_BROWSER -notmatch '^(1|true|yes)$') {
    Write-Host "Your default browser will open when Berry OS is ready."
    Start-Job -ArgumentList $appUrl -ScriptBlock {
        param($url)
        for ($attempt = 0; $attempt -lt 90; $attempt++) {
            try {
                $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2
                if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                    Start-Process $url
                    return
                }
            } catch {
                Start-Sleep -Seconds 1
            }
        }
    } | Out-Null
}

& .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host $hostName --port $port
