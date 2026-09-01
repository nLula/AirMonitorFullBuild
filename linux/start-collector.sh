#!/usr/bin/env bash
# Manual/foreground start - shows output in this terminal, Ctrl+C stops it.
# For the always-on, no-terminal-needed version, use install-autostart.sh.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"

if [ ! -x "venv/bin/python" ]; then
    echo "venv not found - run ./setup.sh first."
    exit 1
fi

export SENSORS_CONFIG="$(pwd)/../config/sensors.json"
export DATA_DIR="$(pwd)/../data"

cd collector
exec ../venv/bin/python run_collector.py
