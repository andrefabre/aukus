# One-command local demo (Windows PowerShell). Free: no cloud, no API keys.
#   .\scripts\start-demo.ps1            # set up on first run, then serve
#   .\scripts\start-demo.ps1 -Reset     # wipe demo data and re-seed May..last month
param([switch]$Reset, [int]$Port = 8000)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
    & .\.venv\Scripts\python.exe -m pip install --quiet --upgrade pip
    & .\.venv\Scripts\python.exe -m pip install --quiet -e ".[dev]"
}
$py = ".\.venv\Scripts\python.exe"
if ($Reset -or -not (Test-Path "var\vault")) {
    & $py -m disp_evidence demo-setup
}
Start-Process "http://127.0.0.1:$Port"
& $py -m disp_evidence serve --port $Port
