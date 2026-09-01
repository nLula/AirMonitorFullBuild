@echo off
rem Windowless launcher used by the "AirMonitor Collector" scheduled task
rem (see install-autostart.ps1). Not meant to be double-clicked directly -
rem use start-collector.bat for that, which shows a console window.
cd /d "%~dp0"

if not exist "venv\Scripts\pythonw.exe" (
    exit /b 1
)
if not exist "logs" mkdir "logs"

set SENSORS_CONFIG=%~dp0..\config\sensors.json
set DATA_DIR=%~dp0..\data

cd collector
"%~dp0venv\Scripts\pythonw.exe" run_collector.py >> "%~dp0logs\collector.log" 2>&1
