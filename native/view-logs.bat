@echo off
rem Opens two small windows that just watch the collector and frontend log
rem files live (like "tail -f"), purely so you can see at a glance that
rem everything is still polling/serving.
rem
rem These windows are NOT the server - the actual collector and frontend
rem run headless in the background (started by Task Scheduler / pythonw),
rem so closing either of these log windows, or both, does nothing to them.
rem You can close and re-run this any time.
cd /d "%~dp0"
if not exist "logs" mkdir "logs"
if not exist "logs\collector.log" type nul > "logs\collector.log"
if not exist "logs\frontend.log" type nul > "logs\frontend.log"

start "AirMonitor Collector - log (safe to close)" cmd /k powershell -NoProfile -NoLogo -Command "Get-Content -Path '%~dp0logs\collector.log' -Wait -Tail 20"
start "AirMonitor Frontend - log (safe to close)" cmd /k powershell -NoProfile -NoLogo -Command "Get-Content -Path '%~dp0logs\frontend.log' -Wait -Tail 20"
