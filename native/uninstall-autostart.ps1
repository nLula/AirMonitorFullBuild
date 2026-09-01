# Removes the scheduled tasks created by install-autostart.ps1.
# Does not stop processes that are already running - use Task Manager,
# or just restart the PC, for that.

Unregister-ScheduledTask -TaskName "AirMonitor Collector" -Confirm:$false -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName "AirMonitor Frontend" -Confirm:$false -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName "AirMonitor Log Viewer" -Confirm:$false -ErrorAction SilentlyContinue

Write-Host "Removed the AirMonitor autostart tasks (if they existed)." -ForegroundColor Green
Write-Host "AirMonitor will no longer start automatically at logon."
