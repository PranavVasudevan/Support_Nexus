# Start the TicketAI backend (no Docker). Run from anywhere.
#   Right-click → Run with PowerShell, or:  .\run_backend.ps1
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
Set-Location $root

if (-not (Test-Path "$root\.venv\Scripts\python.exe")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Cyan
    python -m venv "$root\.venv"
    & "$root\.venv\Scripts\python.exe" -m pip install --upgrade pip
    & "$root\.venv\Scripts\python.exe" -m pip install -r "$root\backend\requirements.txt"
    Write-Host "(Optional) for the on-prem DistilBERT model, also run:" -ForegroundColor Yellow
    Write-Host "  .\.venv\Scripts\pip install torch --index-url https://download.pytorch.org/whl/cu124"
    Write-Host "  .\.venv\Scripts\pip install -r backend\requirements-ml.txt"
}

$env:PYTHONPATH = "$root\backend"
$env:TRANSFORMERS_OFFLINE = "1"   # use the already-downloaded model; remove to allow HF downloads
$env:HF_HUB_OFFLINE = "1"
Write-Host "Starting backend on http://localhost:8000  (docs: /docs)" -ForegroundColor Green
& "$root\.venv\Scripts\python.exe" -m uvicorn api.main:app --app-dir "$root\backend" --host 0.0.0.0 --port 8000
