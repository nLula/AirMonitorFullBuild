import os
import re
import json
import subprocess
import sys
import threading
import time
import logging
from pathlib import Path
from flask import Flask, send_from_directory, jsonify, request

import localtime

# Resolve all paths relative to this file so the app works from any working directory
BASE_DIR = Path(__file__).resolve().parent

# Root directory of the compiled React frontend output
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"

# Flask serves static assets from the React build folder.
app = Flask(
    __name__,
    static_folder=str(FRONTEND_DIST),
    static_url_path="",
)

# Module-level logger so poll thread messages appear in the console
log = logging.getLogger("airmonitor")
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")

# Shared poll status written by the background thread and read by /api/poll/status
_poll_status = {
    "last_check":    None,   # ISO timestamp of the most recent poll attempt
    "last_download": None,   # ISO timestamp of the most recent successful download
    "last_error":    None,   # Error message from the most recent failed poll, or None
    "remote_file":   None,   # Filename of the newest remote file seen
    "local_file":    None,   # Filename of the current local sensor file
}
_poll_status_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Frontend build
# ---------------------------------------------------------------------------

def build_frontend():
    """
    Run 'npm run build' inside the frontend directory.
    Exits the process if the build fails so the user sees a clear error.
    """
    frontend_dir = BASE_DIR / "frontend"
    if not frontend_dir.exists():
        print(f"ERROR: frontend directory not found at {frontend_dir}")
        sys.exit(1)

    print("Building React frontend...")
    result = subprocess.run(
        "npm run build",
        cwd=str(frontend_dir),
        shell=True,
        check=True,
    )

    if result.returncode != 0:
        print("ERROR: Frontend build failed.")
        sys.exit(1)

    print("Frontend build complete.")


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def load_config():
    """
    Read and return the parsed contents of config.json.
    Returns an empty dict if the file does not exist or is malformed.
    """
    from paths import CONFIG_FILE
    p = Path(CONFIG_FILE)
    if not p.exists():
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_config(data):
    """
    Write the given dict to config.json, creating parent directories as needed.
    """
    from paths import CONFIG_FILE
    p = Path(CONFIG_FILE)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_settings():
    """
    Return the merged settings dict with all defaults applied.
    Always reflects the current state of config.json so the poll thread
    picks up changes without restarting the server.
    """
    defaults = {
        "sftp_address":     "",
        "sftp_username":    "",
        "sftp_password":    "",
        "sftp_port":        22,
        "sftp_remote_path": "/",
        "poll_interval":    60,
        "aliases":          {},
        "sensor_radius":    50,
    }
    saved = load_config().get("settings", {})
    return {**defaults, **saved}


# ---------------------------------------------------------------------------
# Local sensor file helpers
# ---------------------------------------------------------------------------

# Regex that matches allSensors<YYYYMMDDHHMMSS>.json
SENSOR_FILE_RE = re.compile(r"^allSensors(\d{14})\.json$")


def find_latest_local_sensors_file():
    """
    Scan the Library directory for files matching allSensors<timestamp>.json
    and return (timestamp_str, Path) of the newest one, or (None, None) if none
    exist. Falls back to allSensors.json as a (None, path) tuple so callers
    can still serve data when no timestamped file is present.
    """
    from paths import LIBRARY_DIR
    lib = Path(LIBRARY_DIR)
    if not lib.exists():
        return None, None

    candidates = []
    for f in lib.iterdir():
        m = SENSOR_FILE_RE.match(f.name)
        if m:
            candidates.append((m.group(1), f))

    if candidates:
        candidates.sort(key=lambda t: t[0], reverse=True)
        return candidates[0]

    fallback = lib / "allSensors.json"
    return (None, fallback) if fallback.exists() else (None, None)


# ---------------------------------------------------------------------------
# SFTP polling thread
# ---------------------------------------------------------------------------

def _poll_once(s):
    """
    Perform a single SFTP poll cycle using the settings dict s.
    Uses asyncssh which supports the full range of legacy SSH algorithms
    including diffie-hellman-group1-sha1, group14-sha1, ssh-rsa, and all
    CBC ciphers that modern paramiko has removed from its registry.

    Connects to the SFTP server, lists allSensors<timestamp>.json files in the
    remote path, compares the newest remote timestamp against the newest local
    timestamp, and downloads + replaces the local file if the remote is newer.

    Updates _poll_status in place. Never raises - all errors are caught and
    recorded in _poll_status["last_error"].
    """
    import asyncio
    import asyncssh
    from paths import LIBRARY_DIR

    lib     = Path(LIBRARY_DIR)
    now_iso = localtime.now().strftime("%Y-%m-%dT%H:%M:%S")

    async def _run():
        # Connect with the broadest possible algorithm set so that any server
        # version can negotiate successfully. asyncssh supports every algorithm
        # including legacy ones removed from paramiko 2.9+.
        conn = await asyncssh.connect(
            host=s["sftp_address"],
            port=int(s["sftp_port"]),
            username=s["sftp_username"],
            password=s["sftp_password"],
            known_hosts=None,           # skip host-key verification
            kex_algs=[                  # include SHA-1 group kex for old servers
                "curve25519-sha256",
                "curve25519-sha256@libssh.org",
                "ecdh-sha2-nistp256",
                "ecdh-sha2-nistp384",
                "ecdh-sha2-nistp521",
                "diffie-hellman-group16-sha512",
                "diffie-hellman-group-exchange-sha256",
                "diffie-hellman-group14-sha256",
                "diffie-hellman-group14-sha1",
                "diffie-hellman-group1-sha1",
                "diffie-hellman-group-exchange-sha1",
            ],
            encryption_algs=[           # all cipher modes including legacy CBC
                "aes128-ctr", "aes192-ctr", "aes256-ctr",
                "aes128-gcm@openssh.com", "aes256-gcm@openssh.com",
                "aes128-cbc", "aes192-cbc", "aes256-cbc",
                "blowfish-cbc", "cast128-cbc", "3des-cbc",
            ],
            mac_algs=[
                "hmac-sha2-256", "hmac-sha2-512",
                "hmac-sha2-256-etm@openssh.com", "hmac-sha2-512-etm@openssh.com",
                "hmac-sha1", "hmac-md5", "hmac-sha1-96", "hmac-md5-96",
            ],
            server_host_key_algs=[      # include legacy ssh-rsa for old servers
                "ssh-ed25519",
                "ecdsa-sha2-nistp256", "ecdsa-sha2-nistp384", "ecdsa-sha2-nistp521",
                "rsa-sha2-512", "rsa-sha2-256",
                "ssh-rsa",
            ],
        )
        async with conn:
            async with conn.start_sftp_client() as sftp:
                remote_path = s["sftp_remote_path"].rstrip("/") or "/"

                try:
                    entries = await sftp.listdir(remote_path)
                except asyncssh.SFTPError as e:
                    raise IOError(f"Cannot list remote path '{remote_path}': {e}")

                remote_candidates = []
                for name in entries:
                    m = SENSOR_FILE_RE.match(name)
                    if m:
                        remote_candidates.append((m.group(1), name))

                if not remote_candidates:
                    raise FileNotFoundError(
                        f"No allSensors<timestamp>.json files found at {remote_path}"
                    )

                remote_candidates.sort(key=lambda t: t[0], reverse=True)
                newest_remote_ts, newest_remote_name = remote_candidates[0]

                local_ts, local_path = find_latest_local_sensors_file()

                with _poll_status_lock:
                    _poll_status["remote_file"] = newest_remote_name
                    _poll_status["local_file"]  = local_path.name if local_path else None

                if local_ts is not None and newest_remote_ts <= local_ts:
                    log.info("Poll: local file is current (%s), skipping download.", local_ts)
                    with _poll_status_lock:
                        _poll_status["last_check"] = now_iso
                        _poll_status["last_error"] = None
                    return

                lib.mkdir(parents=True, exist_ok=True)
                local_dest  = lib / newest_remote_name
                remote_full = f"{remote_path}/{newest_remote_name}"
                log.info("Poll: downloading %s -> %s", remote_full, local_dest)
                await sftp.get(remote_full, str(local_dest))

                if local_path and local_ts is not None and local_path.exists():
                    log.info("Poll: removing outdated local file %s", local_path.name)
                    local_path.unlink(missing_ok=True)

                with _poll_status_lock:
                    _poll_status["last_check"]    = now_iso
                    _poll_status["last_download"] = now_iso
                    _poll_status["last_error"]    = None
                    _poll_status["local_file"]    = newest_remote_name

                log.info("Poll: download complete.")

    try:
        if not s["sftp_address"] or not s["sftp_username"]:
            raise ValueError("SFTP address or username is not configured.")
        asyncio.run(_run())
    except Exception as exc:
        err_msg = str(exc)
        log.warning("Poll error: %s", err_msg)
        with _poll_status_lock:
            _poll_status["last_check"] = now_iso
            _poll_status["last_error"] = err_msg


def _poll_loop():
    """
    Background thread that runs forever, sleeping for poll_interval seconds
    between each SFTP check. Reads settings fresh from config.json each cycle
    so changes made via the Settings dialog take effect without a restart.
    Skips the poll if sftp_address is empty (not yet configured).
    """
    log.info("Poll thread started.")
    while True:
        s = get_settings()
        interval = max(5, int(s.get("poll_interval", 60)))

        if s.get("sftp_address", "").strip():
            _poll_once(s)
        else:
            log.debug("Poll: SFTP not configured, skipping.")

        time.sleep(interval)


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@app.route("/api/sensors")
def api_sensors():
    """
    Return the most recent allSensors<timestamp>.json from the Library.
    Falls back to allSensors.json. Returns 404 if neither exists.
    """
    _, path = find_latest_local_sensors_file()
    if path is None:
        return jsonify({"error": "No sensor file found in Library"}), 404

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return jsonify(data)


@app.route("/api/poll/status")
def api_poll_status():
    """
    Report data freshness from the collector server, which polls the sensors
    on a cron schedule and writes status.json plus allSensors<timestamp>.json
    into the Library folder (shared Docker volume).

    Fields (kept compatible with the old SFTP poll status):
      last_check    - when the collector last polled the sensors
      last_download - timestamp of the newest allSensors file
      last_error    - set only when no sensor is reachable at all
      local_file    - name of the newest allSensors file
      sensors       - per-sensor detail: online, last_connect, response_ms
    """
    from paths import LIBRARY_DIR

    ts, path = find_latest_local_sensors_file()

    collector = {}
    status_path = Path(LIBRARY_DIR) / "status.json"
    if status_path.exists():
        try:
            collector = json.loads(status_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    sensors = collector.get("sensors", {})

    # Mark sensors the user has already configured (floor assigned via the
    # Settings dialog); everything else is "freshly discovered" in the UI.
    assign_path = Path(LIBRARY_DIR) / "config" / "sensor_assignments.json"
    try:
        assignments = json.loads(assign_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        assignments = {}
    for v in sensors.values():
        v["assigned"] = str(v.get("sensor_id")) in assignments

    last_error = None
    if sensors and not any(v.get("online") for v in sensors.values()):
        last_error = "No sensor reachable: " + "; ".join(
            f"{v.get('name', k)}: {v.get('error', 'offline')}" for k, v in sensors.items()
        )

    return jsonify({
        "last_check":    collector.get("last_poll"),
        "last_download": ts,
        "last_error":    last_error,
        "remote_file":   None,
        "local_file":    path.name if path else None,
        "sensors":       sensors,
    })


@app.route("/api/poll/trigger", methods=["POST"])
def api_poll_trigger():
    """
    Request an immediate sensor poll from the collector by dropping a
    trigger file into the shared Library volume - the collector watches
    for it and polls within a couple of seconds. The frontend then follows
    /api/poll/status until last_check advances.
    """
    from paths import LIBRARY_DIR
    trigger = Path(LIBRARY_DIR) / "poll_request"
    trigger.parent.mkdir(parents=True, exist_ok=True)
    trigger.write_text(localtime.now().strftime("%Y-%m-%dT%H:%M:%S"), encoding="utf-8")
    return jsonify({"ok": True, "message": "Immediate poll requested."})


@app.route("/api/history")
def api_history():
    """
    Return the sensor check history recorded by the collector
    (history.json in the shared Library volume): one record per sensor per
    poll with online state, response time, HTTP status and error text.
    Optional ?hours=N limits the window. Used by the Log tab.
    """
    from datetime import timedelta
    from paths import LIBRARY_DIR

    p = Path(LIBRARY_DIR) / "history.json"
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return jsonify({"checks": []})

    checks = data.get("checks", [])
    date = request.args.get("date")  # YYYY-MM-DD: return that day only
    hours = request.args.get("hours", type=float)
    if date:
        key = date.replace("-", "")
        checks = [c for c in checks if c.get("timestamp", "").replace("-", "")[:8] == key]
    elif hours:
        cutoff = (localtime.now() - timedelta(hours=hours)).isoformat()
        checks = [c for c in checks if c.get("timestamp", "") >= cutoff]
    return jsonify({"checks": checks})


@app.route("/api/sensors/assign", methods=["POST"])
def api_assign_sensor():
    """
    Assign a sensor (by its firmware sensor_id) to a floor. Written into
    sensor_assignments.json in the shared Library volume; the collector
    reads it each poll and files the sensor's data under that floor.
    Body: { "sensor_id": 0, "floor": "Floor_10" }
    Returns the slot name the sensor occupies (sensor_<id+1>).
    """
    from paths import LIBRARY_DIR

    body = request.get_json(force=True, silent=True) or {}
    floor = str(body.get("floor", ""))
    try:
        sensor_id = int(body.get("sensor_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "sensor_id must be a number"}), 400
    if not re.match(r"^Floor_\d+$", floor):
        return jsonify({"error": "floor must look like Floor_7"}), 400

    assign_path = Path(LIBRARY_DIR) / "config" / "sensor_assignments.json"
    assign_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        assignments = json.loads(assign_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        assignments = {}
    assignments[str(sensor_id)] = {"floor": floor}
    assign_path.write_text(json.dumps(assignments, indent=2), encoding="utf-8")

    # A sensor lives on exactly one floor: drop its placement markers from
    # every other floor so it can be placed fresh on the new one.
    slot = None
    status_path = Path(LIBRARY_DIR) / "status.json"
    try:
        st = json.loads(status_path.read_text(encoding="utf-8"))
        for key, v in (st.get("sensors") or {}).items():
            if v.get("sensor_id") == sensor_id:
                slot = key.split("/", 1)[1]
                break
    except (OSError, json.JSONDecodeError):
        pass

    if slot:
        config = load_config()
        placements = config.get("sensor_placements", {})
        new_floor_label = floor.replace("_", " ")
        changed = False
        for fl, entries in list(placements.items()):
            if fl == new_floor_label:
                continue
            kept = [p for p in entries if p.get("sensorId") != slot]
            if len(kept) != len(entries):
                placements[fl] = kept
                changed = True
        if changed:
            config["sensor_placements"] = placements
            save_config(config)

    return jsonify({"ok": True, "floor": floor})


@app.route("/api/placements", methods=["GET"])
def api_get_placements():
    """
    Return saved sensor placement positions from config.json.
    Shape: { "Floor 7": [{ sensorId, x, y }, ...], ... }
    """
    return jsonify(load_config().get("sensor_placements", {}))


@app.route("/api/placements", methods=["POST"])
def api_save_placements():
    """
    Persist the full sensor placements object into config.json.
    Expects JSON body: { "Floor 7": [{ sensorId, x, y }, ...], ... }
    """
    data = request.get_json(force=True, silent=True)
    if data is None:
        return jsonify({"error": "Invalid JSON body"}), 400
    config = load_config()
    config["sensor_placements"] = data
    save_config(config)
    return jsonify({"ok": True})


@app.route("/api/settings", methods=["GET"])
def api_get_settings():
    """
    Return all non-security settings from config.json with defaults applied.
    Includes sftp_remote_path added to support folder-level polling.
    """
    return jsonify(get_settings())


@app.route("/api/settings", methods=["POST"])
def api_save_settings():
    """
    Persist non-security settings into config.json under the 'settings' key.
    Merges with existing settings so partial updates are safe.
    The poll thread picks up the new values on its next wake cycle.
    """
    data = request.get_json(force=True, silent=True)
    if data is None:
        return jsonify({"error": "Invalid JSON body"}), 400
    config = load_config()
    config.setdefault("settings", {}).update(data)
    save_config(config)
    return jsonify({"ok": True})


@app.route("/api/security/pin", methods=["POST"])
def api_change_pin():
    """
    Change the developer mode PIN stored in config.json.
    Requires the correct old PIN. Body: { old_pin, new_pin }.
    """
    body    = request.get_json(force=True, silent=True) or {}
    old_pin = str(body.get("old_pin", ""))
    new_pin = str(body.get("new_pin", ""))

    if not new_pin.isdigit() or len(new_pin) > 4:
        return jsonify({"error": "New PIN must be up to 4 digits"}), 400

    config  = load_config()
    current = config.get("dev_pin", "1111")

    if old_pin != current:
        return jsonify({"error": "Old PIN is incorrect"}), 403

    config["dev_pin"] = new_pin
    save_config(config)
    return jsonify({"ok": True})


@app.route("/api/security/email", methods=["GET"])
def api_get_email():
    """
    Return the current recovery email address from emails.list.
    """
    from paths import LIBRARY_DIR
    emails_path = Path(LIBRARY_DIR) / "emails.list"
    if not emails_path.exists():
        return jsonify({"email": ""})
    for line in emails_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            return jsonify({"email": line})
    return jsonify({"email": ""})


@app.route("/api/security/email", methods=["POST"])
def api_set_email():
    """
    Write a new recovery email address to emails.list.
    Body: { "email": "user@example.com" }
    """
    from paths import LIBRARY_DIR
    body  = request.get_json(force=True, silent=True) or {}
    email = str(body.get("email", "")).strip()

    emails_path = Path(LIBRARY_DIR) / "emails.list"
    emails_path.parent.mkdir(parents=True, exist_ok=True)
    emails_path.write_text(email + "\n", encoding="utf-8")
    return jsonify({"ok": True})


@app.route("/api/pin/current", methods=["GET"])
def api_get_pin():
    """
    Return the current developer PIN for local frontend validation.
    """
    config = load_config()
    return jsonify({"pin": config.get("dev_pin", "1111")})


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_react(path):
    """
    Catch-all route that serves the React SPA.
    Static files are served directly; all other paths fall back to index.html.
    """
    target = FRONTEND_DIST / path
    if path and target.exists():
        return send_from_directory(str(FRONTEND_DIST), path)
    # index.html must never be cached, otherwise browsers keep referencing
    # old hashed bundle names after a rebuild and the app breaks silently
    resp = send_from_directory(str(FRONTEND_DIST), "index.html")
    resp.headers["Cache-Control"] = "no-cache"
    return resp


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    build_frontend()

    # Start the background SFTP poll thread as a daemon so it exits when the
    # main process exits. The thread reads settings fresh each cycle so no
    # restart is needed after changing connection settings via the UI.
    poll_thread = threading.Thread(target=_poll_loop, daemon=True, name="sftp-poller")
    poll_thread.start()

    print("Starting AirMonitor backend on http://localhost:5000")
    app.run(debug=True, port=5000, use_reloader=False)