AirMonitor - running without Docker
====================================

UPDATE (2026-08-24): three fixes/changes applied after the initial setup -
see "Update: timezone fix", "Update: Log tab showing stale data" and
"Update: mobile phone display" below. If you already ran setup.bat once,
just re-run it (it's safe to run again) so it installs the new 'tzdata'
package, then restart both start-*.bat windows to pick up the changed
files.

This "native" folder is a straight extraction of the two application images
that used to run in Docker (airmonitor-collector and airmonitor-frontend,
both loaded from airmonitor-images.tar). Both are plain Python 3 apps with
a handful of pip packages - nothing in them needs Docker or Linux, so they
run directly on Windows once Python is installed.

What maps to what
------------------
docker-compose "collector" service  -> collector\poll_sensors.py
  entrypoint.sh (cron + watch loop) -> collector\run_collector.py (new)
docker-compose "frontend" service   -> frontend\backend.py, frontend\paths.py
  run_server.py (fixed port 5000)   -> frontend\run_server_native.py (new,
                                        reads FRONTEND_PORT like .env used to)
./data   volume  -> still your existing data\ folder (untouched)
./config volume  -> still your existing config\ folder (untouched)
.env             -> read automatically by both native scripts, same as before

One difference: the frontend used to reach the shared data through a
container path called /app/Library. setup.bat recreates that as a Windows
directory junction, frontend\Library, pointing at your real data\ folder -
it's not a copy, both names refer to the same files.

One-time setup
---------------
1. Install Python 3.11 or newer from https://www.python.org/downloads/
   During install, check "Add python.exe to PATH".
2. Double-click setup.bat in this folder. It creates a virtual environment
   in .\venv, installs the required packages (flask, waitress, asyncssh,
   requests, croniter), and creates the frontend\Library junction.

Running it
-----------
Open two windows (double-click both, leave them running):
  start-collector.bat   - polls the sensors on the schedule from .env
  start-frontend.bat    - serves the web UI

Once both are running, open http://localhost:8080 (or whatever
FRONTEND_PORT is set to in .env). Colleagues on the same network can use
http://<this-pc-name-or-ip>:8080, same as before - Windows may prompt to
allow python.exe through the firewall the first time, allow it for private
networks.

Auto-loaded settings
----------------------
Both start-*.bat / run_*.py scripts read your existing .env file in the
AirMonitor folder automatically, so SENSOR_API_KEY, CRON_SCHEDULE,
POLL_TIMEOUT_S, SCAN_TIMEOUT_S, DISCOVERY_RESCAN_MIN,
HISTORY_RETENTION_DAYS and FRONTEND_PORT all keep working exactly as
before. Edit .env and restart the two windows to apply changes.

Starting automatically (recommended if this needs to always be up)
-----------------------------------------------------------------------
Double-click install-autostart.bat once. It registers three Task
Scheduler entries:
  - "AirMonitor Collector" and "AirMonitor Frontend" - the actual server,
    which:
      - starts automatically the next time you log in - covers PC
        restarts from Windows Update or anything else
      - gets relaunched automatically by Task Scheduler if the process
        ever exits unexpectedly (crash, killed, etc.) - up to 999 times,
        checked once a minute
      - runs headless (no console window), writing its output instead to
        native\logs\collector.log and native\logs\frontend.log
  - "AirMonitor Log Viewer" - opens two small windows a few seconds
    later, titled "...- log (safe to close)", that just tail those two
    log files live so you can see at a glance that both are still
    running. These windows are only watching the log files, not running
    the server itself, so closing one, both, or even ending them from
    Task Manager has no effect on the collector or frontend - they keep
    running headless regardless. You can also reopen them any time by
    double-clicking view-logs.bat.

install-autostart.bat will ask if you want to start everything right now
as well - say yes to skip a manual start-collector.bat/start-frontend.bat
this time.

This only starts things back up once you (or the account) actually log
back in after a restart. If this PC sits at the lock screen after a
Windows Update reboot until someone signs in, and you want it back up
with nobody touching the keyboard, enable automatic sign-in: press
Win+R, run "netplwiz", uncheck "Users must enter a password to use this
computer" for that account, and confirm. install-autostart.bat prints
this same tip at the end.

To stop it from autostarting later, run uninstall-autostart.bat (this
only removes the three scheduled tasks - it doesn't stop anything
already running, and doesn't touch any files).

If you'd still rather start things manually, start-collector.bat and
start-frontend.bat (the ones with a visible console window) still work
exactly as before - the two approaches don't conflict as long as you
don't run both at once for the same service.

Going back to Docker later
-----------------------------
Nothing here was removed - docker-compose.yml, airmonitor-images.tar and
start-airmonitor.bat are untouched, so once Docker Desktop works again you
can go back to it any time.

Update: timezone fix
-----------------------
Windows Python ignores the TZ environment variable entirely (that's a
POSIX/Docker thing), so under Docker the .env TZ setting kept the app's
clock correct regardless of the host's own timezone, but natively the app
was silently falling back to whatever Windows itself was set to - which
turned out not to match, so recorded timestamps were off by a fixed
amount.

Both collector\poll_sensors.py and frontend\backend.py now import a new
localtime.py (one copy in each folder) that reads the same TZ value from
.env and applies it directly via Python's zoneinfo, independent of the
Windows clock/timezone setting - .env's TZ stays set to Europe/Tallinn,
matching where you and the server actually are. This needs the 'tzdata'
package (Windows has no built-in IANA timezone database), added to
setup.bat - re-run setup.bat once to install it.

Update: Log tab showing stale data
--------------------------------------
Checking data\history.json and data\status.json directly confirmed the
collector was polling correctly the whole time and the sensors were
online - the Log tab in the browser had just stopped picking up new data,
most likely because a phone browser paused the page's auto-refresh timer
after the screen locked or the tab was backgrounded, and it never resumed
fetching. This is a browser-side behavior, not something in the Python
backend, and the original React source wasn't available to fix it at the
source (this deployment only ever had the pre-built files from the Docker
image, not the project the image was built from) - if you have access to
that source repository, this would be worth fixing there directly.

As a practical workaround, frontend\frontend\dist\index.html now has a
small script added that forces the page to reload when it becomes visible
again after being hidden for more than ~20 seconds (covers phone screen
lock / switching apps), plus reloads every 10 minutes as a fallback for a
desktop browser tab left open a long time. This guarantees the page can't
stay stuck showing old data, at the cost of an occasional full page
reload (state like which tab you're on resets, same as any refresh).

Update: mobile phone display
--------------------------------
The frontend previously looked cramped and, in places, overflowed the
screen on a phone (header text overlapping, the Graph tab's slider
running off-screen, the Settings dialog's sidebar squeezing the content
too narrow, log tables needing to scroll sideways awkwardly, etc.),
because it was only ever laid out with a desktop screen in mind and never
had any phone-specific styling.

Same situation as the Log tab fix above: no original React/CSS source is
available, only the pre-built files, so this was fixed by adding a block
of extra CSS rules directly into frontend\frontend\dist\index.html (right
after the existing stylesheet, so these rules take effect on top of it)
that only kick in below certain screen widths. On a normal desktop or
laptop browser window nothing changes at all; on a phone-sized screen the
header now wraps instead of overlapping, the tab bar and controls stay
readable, the Settings dialog's section list moves above the content
instead of squeezed beside it, and long tables scroll horizontally inside
themselves instead of pushing the whole page sideways. Tested at a
375-pixel-wide viewport (a typical phone) - no more sideways overflow on
any of the three tabs or the Settings dialog.
