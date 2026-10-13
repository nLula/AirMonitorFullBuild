#!/usr/bin/env bash
# One-time setup for running AirMonitor on Linux, no Docker involved.
# Run this as your normal user (not root/sudo).
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"

echo "============================================"
echo "  AirMonitor Linux setup"
echo "============================================"

if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 not found. Install it first, e.g.:"
    echo "  sudo apt install python3 python3-venv python3-pip   # Debian/Ubuntu"
    echo "  sudo dnf install python3 python3-pip                # Fedora/RHEL"
    exit 1
fi

echo "[1/4] Creating virtual environment in ./venv ..."
python3 -m venv venv

echo "[2/4] Installing dependencies (flask, waitress, asyncssh, requests, croniter, tzdata)..."
./venv/bin/pip install --upgrade pip >/dev/null
./venv/bin/pip install flask waitress asyncssh requests croniter tzdata

echo "[3/4] Linking frontend/Library to the ../data folder ..."
mkdir -p ../data
if [ ! -e "frontend/Library" ]; then
    ln -s ../../data frontend/Library
fi

echo "[4/4] Checking for ../config/sensors.json and ../.env ..."
missing=0
if [ ! -f "../config/sensors.json" ]; then
    echo "  MISSING: ../config/sensors.json - copy your real one here before starting."
    missing=1
fi
if [ ! -f "../.env" ]; then
    echo "  MISSING: ../.env - copy your real one here before starting (has SENSOR_API_KEY etc.)."
    missing=1
fi

echo
echo "============================================"
if [ "$missing" -eq 0 ]; then
    echo "  Setup complete."
else
    echo "  Setup complete, but see the MISSING items above first."
fi
echo "  Test it manually with ./start-collector.sh and ./start-frontend.sh"
echo "  (each in its own terminal), or set up autostart with"
echo "  ./install-autostart.sh"
echo "============================================"
