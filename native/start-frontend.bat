@echo off
title AirMonitor Frontend (native)
cd /d "%~dp0"

if not exist "venv\Scripts\activate.bat" (
    echo Run setup.bat first.
    pause
    exit /b 1
)
call venv\Scripts\activate.bat

rem AIRMONITOR_CONFIG_DIR mirrors what docker-compose set (/app/Library/config),
rem where Library is the junction created by setup.bat pointing at ..\data.
set AIRMONITOR_CONFIG_DIR=%~dp0frontend\Library\config

cd frontend
python run_server_native.py
pause
