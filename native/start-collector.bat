@echo off
title AirMonitor Collector (native)
cd /d "%~dp0"

if not exist "venv\Scripts\activate.bat" (
    echo Run setup.bat first.
    pause
    exit /b 1
)
call venv\Scripts\activate.bat

rem Same paths docker-compose.yml mounted as volumes:
set SENSORS_CONFIG=%~dp0..\config\sensors.json
set DATA_DIR=%~dp0..\data

cd collector
python run_collector.py
pause
