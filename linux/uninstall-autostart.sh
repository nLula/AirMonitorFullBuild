#!/usr/bin/env bash
# Removes everything install-autostart.sh set up: the two systemd services
# and the desktop log-viewer autostart entry. Does not touch any files
# under this folder, and does not stop a log-viewer window already open.
set -euo pipefail
RUN_USER="${SUDO_USER:-$USER}"
RUN_HOME="$(getent passwd "$RUN_USER" | cut -d: -f6)"

sudo systemctl disable --now airmonitor-collector.service airmonitor-frontend.service 2>/dev/null || true
sudo rm -f /etc/systemd/system/airmonitor-collector.service /etc/systemd/system/airmonitor-frontend.service
sudo systemctl daemon-reload

rm -f "$RUN_HOME/.config/autostart/airmonitor-logs.desktop"

echo "Removed the AirMonitor autostart services and the desktop log-viewer entry"
echo "(whichever of those existed). AirMonitor will no longer start automatically."
