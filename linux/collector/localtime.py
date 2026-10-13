"""
Timezone-independent "local now".

Native Windows Python ignores the TZ environment variable entirely (that's
a POSIX/Docker mechanism), so datetime.now() just returns whatever timezone
Windows itself is configured with - which drifted from the AirMonitor
deployment's intended timezone once Docker (which did honor TZ inside the
container) was taken out of the picture.

This reads the same TZ value .env always used and applies it directly in
Python via the IANA database (the 'tzdata' package, since Windows has no
built-in copy), so recorded timestamps no longer depend on how the host
machine's clock/timezone happens to be configured.
"""
import os
from datetime import datetime

try:
    from zoneinfo import ZoneInfo
    _ZONE = ZoneInfo(os.environ.get("TZ", "Europe/Kyiv"))
except Exception as e:  # missing tzdata package, unknown zone name, etc.
    _ZONE = None
    _ZONE_ERROR = e


def now() -> datetime:
    """Current local time as a naive datetime - same shape datetime.now()
    always returned, so nothing downstream (isoformat strings, comparisons,
    filenames) needs to change, but the value itself is now correct
    regardless of the OS timezone setting."""
    if _ZONE is not None:
        return datetime.now(_ZONE).replace(tzinfo=None)
    return datetime.now()
