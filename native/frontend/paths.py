import os
from pathlib import Path

APP_NAME = "AirMonitor"

def get_config_file():
    # Server/Docker deployments set AIRMONITOR_CONFIG_DIR so the config lives
    # with the app's data (shared volume) instead of the user profile.
    override = os.getenv("AIRMONITOR_CONFIG_DIR")
    if override:
        base = Path(override)
    else:
        appdata = os.getenv("APPDATA")
        base = (Path(appdata) if appdata else Path.home() / ".config") / APP_NAME
    base.mkdir(parents=True, exist_ok=True)
    return base / "config.json"

def resource_path(relative_path):
    # When running in PyInstaller bundled mode,
    # data files are inside '_internal' directory
    base_path = os.path.abspath(".")
    internal_path = os.path.join(base_path, "_internal")
    if os.path.exists(internal_path):
        # Adjust to _internal folder for bundled files
        base_path = internal_path
    return os.path.join(base_path, relative_path)

CONFIG_FILE = get_config_file()
LIBRARY_DIR = Path(resource_path(os.path.join("Library")))
ALLSENSORS_FILE = os.path.join(LIBRARY_DIR, 'allSensors.json')
