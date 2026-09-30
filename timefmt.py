"""Pacific-time helpers. Leek Duck times without a zone are local wall-clock times."""
import datetime as dt
from zoneinfo import ZoneInfo

PT = ZoneInfo("America/Los_Angeles")


def now_pt():
    return dt.datetime.now(PT).replace(tzinfo=None, microsecond=0)


def wall(s):
    """Event time -> naive PT wall-clock datetime (or None)."""
    if not s:
        return None
    s = str(s)
    try:
        if s.endswith("Z") or "+" in s[10:]:
            return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(PT).replace(tzinfo=None)
        return dt.datetime.fromisoformat(s[:19])
    except ValueError:
        return None


def day(d):
    """'2026-10-30' -> date, month-only or bad -> None."""
    try:
        return dt.date.fromisoformat(d) if d and len(d) == 10 else None
    except ValueError:
        return None


def short(d):
    """datetime -> 'Mon 9/28  8pm' (fixed-width-ish for code blocks)."""
    h = d.hour % 12 or 12
    t = f"{h}{':%02d' % d.minute if d.minute else ''}{'am' if d.hour < 12 else 'pm'}"
    return f"{d:%a} {d.month}/{d.day} {t:>7}"
