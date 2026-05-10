@echo off
REM ============================================================================
REM CodeNova AI - Standalone Desktop Application
REM Double-click this file to run the complete application
REM ============================================================================

setlocal enabledelayedexpansion

REM Get the directory where this script is located
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ from python.org
    pause
    exit /b 1
)

REM Check if Node.js is installed
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Node.js is not installed or not in PATH
    echo Please install Node.js from nodejs.org
    pause
    exit /b 1
)

cls
echo ============================================================================
echo CodeNova AI - Java Refactoring IDE
echo ============================================================================
echo.
echo Starting services...
echo.

REM Kill any existing processes on port 8000
for /f "tokens=5" %%a in ('netstat -aon ^| find ":8000 "') do taskkill /pid %%a /f 2>nul

REM Start the FastAPI backend
echo [1/2] Starting Backend API Server on port 8000...
start "CodeNova Backend API" cmd /k "cd /d "%SCRIPT_DIR%java_refactoring_engine" && python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000"

REM Wait for backend to start
timeout /t 3 /nobreak

REM Install desktop app dependencies if needed
if not exist "%SCRIPT_DIR%desktop-app\node_modules" (
    echo [2a/2] Installing desktop app dependencies...
    cd /d "%SCRIPT_DIR%desktop-app"
    call npm install >nul 2>&1
)

REM Start Electron desktop app
echo [2/2] Launching CodeNova AI Desktop Application...
cd /d "%SCRIPT_DIR%desktop-app"
call npm start

echo.
echo CodeNova AI has finished running
echo.
