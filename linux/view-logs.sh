#!/usr/bin/env bash
# Live-tails both services' logs together (like "tail -f"). Ctrl+C just
# stops watching - it doesn't affect the running services at all, they
# keep going in the background regardless.
#
# If this errors with a permission message, prefix it with sudo:
#   sudo ./view-logs.sh
journalctl -u airmonitor-collector -u airmonitor-frontend -f
