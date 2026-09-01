AirMonitor - running on Linux (no Docker)
============================================

This is the Linux counterpart of the "native" Windows setup - same idea,
same Python code (it's identical, unchanged - none of it was ever
Windows-specific), just Linux shell scripts and a systemd-based autostart
instead of batch files and Task Scheduler.

Expected folder layout
--------------------------
This "linux" folder expects to sit next to a "config" folder, a "data"
folder, and a ".env" file, exactly like the Windows "native" folder does:

  AirMonitor/
    .env
    config/
      sensors.json
    data/                  (created automatically if missing)
    linux/                 <- this folder
      collector/
      frontend/
      setup.sh
      ...

If you're moving this from the Windows machine, copy your real
config/sensors.json and .env alongside this linux folder (same folder
they already live in on Windows) - don't reuse the ones on Windows over
a network share, copy them, since data/history.json in particular can
grow large and having two collectors polling the same sensors from two
machines at once would just create confusing double-entries. Run this
instead of the Windows one, not alongside it, unless you deliberately
want a second independent instance somewhere else.

One-time setup
------------------
1. Make sure Python 3.9+ is installed:
     sudo apt install python3 python3-venv python3-pip     # Debian/Ubuntu
     sudo dnf install python3 python3-pip                  # Fedora/RHEL
2. If these files arrived via a zip/download rather than a native Linux
   copy, the executable bit is often lost in transit - restore it once:
     chmod +x *.sh
3. Run:
     ./setup.sh
   It creates a virtual environment in ./venv, installs the handful of
   pip packages needed (flask, waitress, asyncssh, requests, croniter,
   tzdata), and links frontend/Library to your ../data folder. It will
   warn if ../config/sensors.json or ../.env are missing - copy your
   real ones there before starting.

Running it manually (for testing)
--------------------------------------
Two terminals, each left open:
  ./start-collector.sh
  ./start-frontend.sh
Ctrl+C in either stops that one. Open http://localhost:8080 (or whatever
FRONTEND_PORT is set to in .env) once both are running.

Starting automatically at boot (recommended for an always-on server)
--------------------------------------------------------------------------
Run once (as your normal user, not sudo - it'll ask for your password
itself only when it actually needs root):
     ./install-autostart.sh

This installs two things:

1. Two systemd services, "airmonitor-collector" and "airmonitor-frontend",
   that:
     - start automatically on every boot - this is a real system service,
       so unlike a desktop autostart it doesn't need anyone to log in at
       all, it comes up as part of the normal boot sequence
     - get restarted automatically by systemd if either process ever
       exits unexpectedly
     - log to the systemd journal, viewable with journalctl or view-logs.sh

2. A desktop autostart entry, "AirMonitor Logs", installed to
   ~/.config/autostart/ for the user that ran the script. If (and only
   if) that user logs into a graphical desktop session (GNOME, KDE,
   XFCE, Cinnamon, MATE, etc.), a terminal window titled
   "AirMonitor - Address: <hostname> (<ip>)" pops up automatically,
   tailing both services' logs live - the title itself tells you what to
   type into a browser on another device to reach the frontend. That
   window is only watching the logs, not running the server, so closing
   it - or even killing it - does not stop anything; the collector and
   frontend keep running as systemd services either way. It tries
   several common terminal emulators to find one that's installed, and
   on a headless machine with no desktop at all, this part simply never
   triggers - which is fine, it's a visual convenience only, nothing
   depends on it.

Useful commands afterward:
  systemctl status airmonitor-collector airmonitor-frontend   - check state
  ./view-logs.sh                                               - live log tail (current terminal)
  ./view-logs-gui.sh                                           - open the log window on demand
  sudo systemctl restart airmonitor-frontend                   - restart one
  ./uninstall-autostart.sh                                     - remove all of the above

Notes
-------
- If you set FRONTEND_PORT to a number below 1024 (e.g. 80) in .env, the
  service will fail to bind unless you either run it as root (change
  User=root/Group=root in the generated
  /etc/systemd/system/airmonitor-frontend.service and
  `sudo systemctl daemon-reload`), or grant the venv's python binary the
  capability instead: `sudo setcap 'cap_net_bind_service=+ep'
  venv/bin/python3.X` (find the exact filename with `ls venv/bin/`).
  Simplest is just to keep the default 8080 and, if needed, put a reverse
  proxy (nginx/Caddy) in front of it on port 80 instead.
- The TZ handling from the Windows setup (localtime.py, reading the TZ
  value straight out of .env via Python's zoneinfo) is included here too
  and works the same way, even though Linux normally does respect a TZ
  environment variable directly - keeping both platforms on the exact
  same code path means one less thing that can behave differently
  between them.
- The frontend now includes phone-friendly styling (added directly into
  frontend/frontend/dist/index.html, since no original React/CSS source
  is available - only the pre-built files). Below a certain screen width
  the header wraps instead of overlapping, the Graph tab's controls and
  the Settings dialog reflow to fit, and long tables scroll horizontally
  inside themselves instead of dragging the whole page sideways. Nothing
  changes on a normal desktop/laptop browser window.
