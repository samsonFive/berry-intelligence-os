# One-click launcher: starts the server minimized (so it's easy to find and
# close later) and opens the browser automatically once it actually responds,
# instead of guessing a fixed delay.

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

Start-Process -FilePath "$root\.venv\Scripts\python.exe" `
    -ArgumentList "-m", "uvicorn", "app.main:app" `
    -WorkingDirectory $root `
    -WindowStyle Minimized

$url = "http://127.0.0.1:8000/"
$maxWaitSeconds = 30
$ready = $false

for ($i = 0; $i -lt $maxWaitSeconds; $i++) {
    try {
        Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2 | Out-Null
        $ready = $true
        break
    } catch {
        Start-Sleep -Seconds 1
    }
}

Start-Process $url

if (-not $ready) {
    # Give the minimized server window a moment in case it's just slow to
    # start; if something's actually wrong, restoring that window from the
    # taskbar shows the real error.
    Start-Sleep -Seconds 5
}
