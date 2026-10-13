"""
Native (non-Docker) launcher for the AirMonitor frontend.

Same as run_server.py (starts the Flask app via waitress, no npm rebuild),
but also loads ../.env automatically and reads the port from FRONTEND_PORT
so it matches what start-airmonitor.bat used to print
("http://localhost:8080").
"""

import os
from pathlib import Path

HERE = Path(__file__).resolve().parent


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

from waitress import serve  # noqa: E402
from backend import app  # noqa: E402

if __name__ == "__main__":
    port = int(os.environ.get("FRONTEND_PORT", "8080"))
    print(f"AirMonitor frontend listening on 0.0.0.0:{port}")
    serve(app, host="0.0.0.0", port=port)
