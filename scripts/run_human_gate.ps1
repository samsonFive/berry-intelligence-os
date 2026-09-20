# Open Berry OS directly in the Gate 3 statement-review workspace.
$ErrorActionPreference = "Stop"
$env:BIOS_START_PATH = "/statements?review=unreviewed"
& (Join-Path $PSScriptRoot "run_local.ps1")
