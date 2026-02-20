"""
Timezone utility for getting the current date/time in the configured application timezone.
Reads the 'timezone' key from SystemSettings so it can be changed per deployment.
"""
from datetime import datetime


def get_local_now():
    """Return current datetime in the configured application timezone."""
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        try:
            from backports.zoneinfo import ZoneInfo
        except ImportError:
            return datetime.now()

    from app.models import SystemSettings
    tz_name = SystemSettings.get_value('timezone', 'America/Chicago')
    try:
        return datetime.now(ZoneInfo(tz_name))
    except Exception:
        return datetime.now()


def get_local_today():
    """Return current date in the configured application timezone."""
    return get_local_now().date()
