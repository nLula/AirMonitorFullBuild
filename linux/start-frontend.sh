#!/usr/bin/env bash
# Manual/foreground start - shows output in this terminal, Ctrl+C stops it.
# For the always-on, no-terminal-needed version, use install-autostart.sh.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"

if [ ! -x "venv/bin/python" ]; then
    echo "venv not found - run ./setup.sh first."
    exit 1
fi

export AIRMONITOR_CONFIG_DIR="$(pwd)/frontend/Library/config"

cd frontend
exec ../venv/bin/python run_server_native.py
