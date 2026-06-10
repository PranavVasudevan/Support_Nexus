# Start the TicketAI frontend (React dev server) on http://localhost:3000
#   Right-click → Run with PowerShell, or:  .\run_frontend.ps1
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
Set-Location "$root\frontend"

if (-not (Test-Path "$root\frontend\node_modules")) {
    Write-Host "Installing frontend dependencies (first run only)..." -ForegroundColor Cyan
    npm install
}

Write-Host "Starting frontend on http://localhost:3000" -ForegroundColor Green
Write-Host "Login:  client / user123   (chat)    |    admin / admin123   (review + dashboard)" -ForegroundColor Yellow
npm start
