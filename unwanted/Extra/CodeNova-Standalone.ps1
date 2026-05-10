# CodeNova AI - Standalone Desktop Application Launcher
# Double-click or Right-click "Run with PowerShell"

param(
    [switch]$AutoRun = $false
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "================================" -ForegroundColor Cyan
Write-Host "CodeNova AI - Standalone IDE" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# Check prerequisites
Write-Host "Checking prerequisites..." -ForegroundColor Yellow

$pythonCheck = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Python 3.8+ is required" -ForegroundColor Red
    Write-Host "Download from: https://python.org" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

$nodeCheck = node --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Node.js 14+ is required" -ForegroundColor Red
    Write-Host "Download from: https://nodejs.org" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "✓ Python: $pythonCheck" -ForegroundColor Green
Write-Host "✓ Node.js: $nodeCheck" -ForegroundColor Green
Write-Host ""

# Check and install desktop app dependencies
$desktopAppPath = Join-Path $scriptDir "desktop-app"
if (-not (Test-Path "$desktopAppPath\node_modules")) {
    Write-Host "Installing desktop app dependencies..." -ForegroundColor Yellow
    Push-Location $desktopAppPath
    npm install 2>&1 | Out-Null
    Pop-Location
    Write-Host "✓ Dependencies installed" -ForegroundColor Green
}

# Kill existing process on port 8000
Write-Host "Cleaning up existing services..." -ForegroundColor Yellow
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | ForEach-Object {
    Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
}

# Start backend
Write-Host "Starting Backend API Server..." -ForegroundColor Cyan
$backendPath = Join-Path $scriptDir "java_refactoring_engine"
$null = Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$backendPath'; python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000" -WindowStyle Normal

Start-Sleep -Seconds 3

# Start Desktop App
Write-Host "Launching CodeNova AI Desktop Application..." -ForegroundColor Cyan
$null = Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$desktopAppPath'; npm start" -WindowStyle Normal

Write-Host ""
Write-Host "================================" -ForegroundColor Green
Write-Host "CodeNova AI is now running!" -ForegroundColor Green
Write-Host "================================" -ForegroundColor Green
Write-Host ""
Write-Host "Backend API:" -ForegroundColor Cyan
Write-Host "  → http://127.0.0.1:8000" -ForegroundColor Yellow
Write-Host "  → Docs: http://127.0.0.1:8000/docs" -ForegroundColor Yellow
Write-Host ""
Write-Host "Desktop App Features:"
Write-Host "  • Ctrl+Shift+R - Refactor Code" -ForegroundColor Yellow
Write-Host "  • Ctrl+Shift+A - Analyze Code" -ForegroundColor Yellow
Write-Host "  • Ctrl+Shift+E - Check Errors" -ForegroundColor Yellow
Write-Host ""
Write-Host "Two windows will open:" -ForegroundColor Yellow
Write-Host "  1. Backend API console" -ForegroundColor Yellow
Write-Host "  2. CodeNova IDE (Electron app)" -ForegroundColor Yellow
Write-Host ""

Write-Host "Close both windows when done." -ForegroundColor Yellow
