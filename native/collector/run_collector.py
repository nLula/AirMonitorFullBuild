"""
Native (non-Docker) replacement for the collector container's entrypoint.sh.

The original container used cron to run poll_sensors.py on a schedule, plus
a small loop watching for a poll_request file dropped by the frontend's
"refresh" button. This script does the same two jobs without cron, so it
can run directly on Windows.

Reads the same environment variables as docker-compose.yml did
(SENSOR_API_KEY, CRON_SCHEDULE, POLL_TIMEOUT_S, SCAN_TIMEOUT_S,
DISCOVERY_RESCAN_MIN, HISTORY_RETENTION_DAYS, SENSORS_CONFIG, DATA_DIR),
loading them from ../.env if they are not already set in the environment.
"""

import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
POLL_SCRIPT = HERE / "poll_sensors.py"


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


load_dotenv(HERE.parent.parent / ".env")

import localtime  # noqa: E402 - after load_dotenv so it sees TZ from .env

try:
    from croniter import croniter
except ImportError:
    print("Missing dependency 'croniter'. Run setup.bat first (or: pip install croniter).")
    sys.exit(1)

DATA_DIR = Path(os.environ.get("DATA_DIR", str(HERE.parent / "data")))
SCHEDULE = os.environ.get("CRON_SCHEDULE", "*/5 * * * *")
POLL_REQUEST_FILE = DATA_DIR / "poll_request"

_lock = threading.Lock()


def log(msg: str) -> None:
    print(f"[collector] {msg}", flush=True)


def run_poll(force_scan: bool = False) -> None:
    env = os.environ.copy()
    if force_scan:
        env["FORCE_SCAN"] = "1"
    with _lock:
        subprocess.run([sys.executable, str(POLL_SCRIPT)], env=env, check=False)


def watch_poll_requests() -> None:
    while True:
        try:
            if POLL_REQUEST_FILE.exists():
                POLL_REQUEST_FILE.unlink(missing_ok=True)
                log("Immediate poll requested by frontend")
                run_poll()
        except OSError:
            pass
        time.sleep(2)


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        POLL_REQUEST_FILE.unlink(missing_ok=True)
    except OSError:
        pass

    log("Initial poll (full discovery scan)...")
    run_poll(force_scan=True)

    threading.Thread(target=watch_poll_requests, daemon=True).start()

    log(f"Cron schedule: {SCHEDULE}")
    itr = croniter(SCHEDULE, localtime.now())
    while True:
        next_run = itr.get_next(datetime)
        sleep_s = (next_run - localtime.now()).total_seconds()
        if sleep_s > 0:
            time.sleep(sleep_s)
        run_poll()


if __name__ == "__main__":
    main()
