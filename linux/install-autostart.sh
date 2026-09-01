#!/usr/bin/env bash
# Installs and enables:
#   1. Two systemd services, "airmonitor-collector" and "airmonitor-frontend",
#      that start automatically at boot (no login needed at all - this is a
#      real system service, not a desktop autostart) and get restarted
#      automatically by systemd if either ever exits unexpectedly.
#   2. A desktop autostart entry, "AirMonitor Logs", that opens a terminal
#      window tailing both services' logs whenever you log into a Linux
#      desktop session (GNOME/KDE/XFCE/etc.). That window only watches the
#      logs - it is not the server, so closing it does not stop anything.
#      This part only has any effect on a machine with a graphical desktop;
#      on a headless server it simply never triggers, which is fine.
#
# Run this as your normal user (NOT with sudo) - it asks for your sudo
# password itself, only for the specific commands that need root (the
# systemd part). Safe to re-run.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"
HERE="$(pwd)"
RUN_USER="${SUDO_USER:-$USER}"
RUN_GROUP="$(id -gn "$RUN_USER")"
RUN_HOME="$(getent passwd "$RUN_USER" | cut -d: -f6)"

if [ ! -x "venv/bin/python" ]; then
    echo "venv not found - run ./setup.sh first (as $RUN_USER, not sudo), then re-run this."
    exit 1
fi

if [ "$RUN_USER" = "root" ]; then
    echo "This will run the AirMonitor services as 'root', which works but isn't"
    echo "necessary - consider re-running this as a normal user instead."
fi

echo "[1/2] Installing systemd services for user '$RUN_USER'..."

for svc in airmonitor-collector airmonitor-frontend; do
    sed \
        -e "s#__AIRMONITOR_DIR__#${HERE}#g" \
        -e "s#__RUN_USER__#${RUN_USER}#g" \
        -e "s#__RUN_GROUP__#${RUN_GROUP}#g" \
        "${svc}.service.template" > "/tmp/${svc}.service.generated"
    sudo mv "/tmp/${svc}.service.generated" "/etc/systemd/system/${svc}.service"
done

sudo systemctl daemon-reload
sudo systemctl enable airmonitor-collector.service airmonitor-frontend.service

echo "[2/2] Installing the desktop log-viewer autostart entry for '$RUN_USER'..."

chmod +x "$HERE/view-logs-gui.sh"
AUTOSTART_DIR="$RUN_HOME/.config/autostart"
mkdir -p "$AUTOSTART_DIR"
sed -e "s#__AIRMONITOR_DIR__#${HERE}#g" \
    airmonitor-logs.desktop.template > "$AUTOSTART_DIR/airmonitor-logs.desktop"
if [ "$(id -u)" = "0" ] && [ "$RUN_USER" != "root" ]; then
    chown -R "$RUN_USER:$RUN_GROUP" "$RUN_HOME/.config/autostart"
fi

echo
echo "Done."
echo " - 'airmonitor-collector' and 'airmonitor-frontend' will now start automatically"
echo "   on every boot, and restart on their own if they crash."
echo " - A terminal tailing their logs will open automatically next time '$RUN_USER'"
echo "   logs into a graphical desktop session (if this machine has one)."
echo

read -r -p "Start the collector and frontend right now as well? (y/n) " start
if [[ "$start" == "y" || "$start" == "Y" ]]; then
    sudo systemctl start airmonitor-collector.service airmonitor-frontend.service
    echo "Started."
    echo "Status:     systemctl status airmonitor-collector airmonitor-frontend"
    echo "Live logs:  ./view-logs.sh   (or: journalctl -u airmonitor-collector -u airmonitor-frontend -f)"
fi

if [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]; then
    read -r -p "Open the log-viewer window right now too? (y/n) " openlogs
    if [[ "$openlogs" == "y" || "$openlogs" == "Y" ]]; then
        nohup "$HERE/view-logs-gui.sh" >/dev/null 2>&1 &
        disown
    fi
fi
