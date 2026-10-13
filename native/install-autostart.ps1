# Registers the AirMonitor collector and frontend as Windows scheduled
# tasks that:
#   - start automatically the next time you log in (covers PC restarts,
#     Windows Update reboots, power loss, etc.)
#   - get restarted automatically by Task Scheduler if the process ever
#     exits unexpectedly (up to 999 times, one attempt per minute)
#   - run with no visible console window (output goes to native\logs\)
#
# A third task, "AirMonitor Log Viewer", also starts at logon and opens two
# small windows that just tail collector.log/frontend.log for a visual
# "it's alive" check - those windows are not the server itself (which stays
# headless per above), so closing them does not stop anything.
#
# Safe to run more than once - it just replaces the existing tasks.

$here = $PSScriptRoot

if (-not (Test-Path (Join-Path $here "venv\Scripts\pythonw.exe"))) {
    Write-Host "venv not found - run setup.bat first, then re-run this." -ForegroundColor Red
    exit 1
}

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -MultipleInstances IgnoreNew

$trigger = New-ScheduledTaskTrigger -AtLogOn

# Gives the collector/frontend a few seconds' head start so the log windows
# below have something to show right away instead of an empty wait.
$viewerTrigger = New-ScheduledTaskTrigger -AtLogOn
$viewerTrigger.Delay = "PT10S"

$collectorAction = New-ScheduledTaskAction -Execute (Join-Path $here "task-run-collector.bat") -WorkingDirectory $here
$frontendAction  = New-ScheduledTaskAction -Execute (Join-Path $here "task-run-frontend.bat")  -WorkingDirectory $here
$viewerAction    = New-ScheduledTaskAction -Execute (Join-Path $here "view-logs.bat")          -WorkingDirectory $here

Register-ScheduledTask -TaskName "AirMonitor Collector" -Action $collectorAction -Trigger $trigger -Settings $settings `
    -Description "Starts the AirMonitor sensor collector at logon (native, non-Docker). See AirMonitor\native\README.txt." -Force | Out-Null

Register-ScheduledTask -TaskName "AirMonitor Frontend" -Action $frontendAction -Trigger $trigger -Settings $settings `
    -Description "Starts the AirMonitor web frontend at logon (native, non-Docker). See AirMonitor\native\README.txt." -Force | Out-Null

Register-ScheduledTask -TaskName "AirMonitor Log Viewer" -Action $viewerAction -Trigger $viewerTrigger -Settings $settings `
    -Description "Opens two windows tailing the collector/frontend logs at logon. Not the server itself - closing them is harmless. See AirMonitor\native\README.txt." -Force | Out-Null

Write-Host ""
Write-Host "Done. 'AirMonitor Collector', 'AirMonitor Frontend' and 'AirMonitor Log Viewer' are now registered" -ForegroundColor Green
Write-Host "in Task Scheduler, and will start automatically the next time you log in - including after a" -ForegroundColor Green
Write-Host "Windows Update restart, as long as you log back in to this Windows account afterwards." -ForegroundColor Green
Write-Host ""
Write-Host "Tip: if you'd like this PC to log back in on its own after a reboot (no lock-screen wait)," -ForegroundColor DarkGray
Write-Host "run 'netplwiz', uncheck 'Users must enter a password to use this computer', and confirm." -ForegroundColor DarkGray
Write-Host ""

$start = Read-Host "Start everything right now as well - collector, frontend, and the log windows? (y/n)"
if ($start -eq "y" -or $start -eq "Y") {
    Start-ScheduledTask -TaskName "AirMonitor Collector"
    Start-ScheduledTask -TaskName "AirMonitor Frontend"
    Start-ScheduledTask -TaskName "AirMonitor Log Viewer"
    Write-Host "Started. Two log windows should appear shortly; closing them does not stop the server."
}
