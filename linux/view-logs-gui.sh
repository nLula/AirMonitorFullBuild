#!/usr/bin/env bash
# Opens a new terminal window tailing both service logs live - meant to be
# launched from a graphical desktop session (that's what install-autostart.sh
# wires up via ~/.config/autostart). Tries common terminal emulators in turn
# so it works across desktop environments without needing one specific DE.
#
# This window is only watching the logs, not running the server - closing
# it, or even killing it, has zero effect on the collector/frontend, which
# keep running as systemd services regardless.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"

CMD="journalctl -u airmonitor-collector -u airmonitor-frontend -f"

HOST="$(hostname)"
IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
if [ -z "$IP" ]; then
    IP="$(ip -4 addr show scope global 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | head -n1)"
fi
IP="${IP:-unknown IP}"
TITLE="AirMonitor - Address: ${HOST} (${IP})"

# Shown both as the window title and as the first line inside it, since not
# every window manager/taskbar surfaces the title text.
INNER="echo '$TITLE'; echo; $CMD; echo; echo '[log stopped - press enter to close]'; read"

if command -v x-terminal-emulator >/dev/null 2>&1; then
    exec x-terminal-emulator -T "$TITLE" -e bash -c "$INNER"
elif command -v gnome-terminal >/dev/null 2>&1; then
    exec gnome-terminal --title="$TITLE" -- bash -c "$INNER"
elif command -v konsole >/dev/null 2>&1; then
    exec konsole --title "$TITLE" -e bash -c "$INNER"
elif command -v xfce4-terminal >/dev/null 2>&1; then
    exec xfce4-terminal --title="$TITLE" -e "bash -c \"$INNER\""
elif command -v mate-terminal >/dev/null 2>&1; then
    exec mate-terminal --title="$TITLE" -e "bash -c \"$INNER\""
elif command -v lxterminal >/dev/null 2>&1; then
    exec lxterminal -T "$TITLE" -e bash -c "$INNER"
elif command -v tilix >/dev/null 2>&1; then
    exec tilix -t "$TITLE" -e bash -c "$INNER"
elif command -v alacritty >/dev/null 2>&1; then
    exec alacritty -T "$TITLE" -e bash -c "$INNER"
elif command -v kitty >/dev/null 2>&1; then
    exec kitty -T "$TITLE" bash -c "$INNER"
elif command -v xterm >/dev/null 2>&1; then
    exec xterm -T "$TITLE" -e bash -c "$INNER"
else
    notify-send "AirMonitor" "No terminal emulator found - open one manually and run: $CMD" 2>/dev/null || true
    exit 1
fi
