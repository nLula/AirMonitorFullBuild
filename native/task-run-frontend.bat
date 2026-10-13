@echo off
rem Windowless launcher used by the "AirMonitor Frontend" scheduled task
rem (see install-autostart.ps1). Not meant to be double-clicked directly -
rem use start-frontend.bat for that, which shows a console window.
cd /d "%~dp0"

if not exist "venv\Scripts\pythonw.exe" (
    exit /b 1
)
if not exist "logs" mkdir "logs"

set AIRMONITOR_CONFIG_DIR=%~dp0frontend\Library\config

cd frontend
"%~dp0venv\Scripts\pythonw.exe" run_server_native.py >> "%~dp0logs\frontend.log" 2>&1
