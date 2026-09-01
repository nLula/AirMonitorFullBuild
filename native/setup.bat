@echo off
rem One-time setup for running AirMonitor without Docker.
rem Requires Python 3.11+ installed from python.org with "Add python.exe to PATH" checked.
cd /d "%~dp0"

echo ============================================
echo   AirMonitor native setup
echo ============================================

where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: python was not found on PATH.
    echo Install Python 3.11+ from https://www.python.org/downloads/ first,
    echo making sure to check "Add python.exe to PATH" during install.
    pause
    exit /b 1
)

echo [1/3] Creating virtual environment in .\venv ...
python -m venv venv

echo [2/3] Installing dependencies (flask, waitress, asyncssh, requests, croniter, tzdata)...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install flask waitress asyncssh requests croniter tzdata
if errorlevel 1 (
    echo ERROR: pip install failed, see above.
    pause
    exit /b 1
)

echo [3/3] Linking frontend\Library to the existing .\data folder ...
if not exist "frontend\Library" (
    mklink /J "frontend\Library" "..\data"
)

echo.
echo ============================================
echo   Setup complete.
echo   Start the collector and frontend with
echo   start-collector.bat and start-frontend.bat
echo   (run each in its own window - leave both open).
echo ============================================
pause
