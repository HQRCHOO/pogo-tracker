"""Featured Power Spot (Max Battle) bosses from ScrapedDuck's events feed.

Max Mondays ("Dynamax Sizzlipede during Max Monday") and Max Battle Days ("Gigantamax Cinderace Max Battle Day")
name their featured boss. The full weekly pool isn't published as data; the PoGo agent writes it to the
dashboard database (max_battles/current) and the page merges the two.
"""
import datetime as dt
import re

from ..util import get, result

URL = "https://raw.githubusercontent.com/bigfoott/ScrapedDuck/data/events.json"
PAT = re.compile(r"^(Dynamax|Gigantamax)\s+(.+?)\s+(?:during Max Monday|Max Battle Day)$", re.I)


def _names(s):
    parts = re.split(r",\s*(?:and\s+)?|\s+and\s+", s.strip())
    return [p.strip() for p in parts if p.strip()]


def _when(s):
    try:
        return dt.datetime.fromisoformat(str(s).replace("Z", ""))
    except Exception:
        return None


def fetch(cfg, prev):
    now = dt.datetime.utcnow()
    items, seen = [], set()
    for e in get(URL).json():
        if e.get("eventType") not in ("max-mondays", "max-battles"):
            continue
        m = PAT.match(str(e.get("name") or ""))
        start, end = _when(e.get("start")), _when(e.get("end"))
        if not m or not start or not end:
            continue
        if end < now - dt.timedelta(hours=12) or start > now + dt.timedelta(days=21):
            continue
        kind = m.group(1).lower()
        for name in _names(m.group(2)):
            key = (kind, name.lower())
            if key in seen:
                continue
            seen.add(key)
            items.append({"name": name, "kind": kind, "tier": 6 if kind == "gigantamax" else None,
                          "featured_start": e.get("start"), "featured_end": e.get("end"),
                          "event": e.get("name"), "url": e.get("link") or f"https://leekduck.com/events/{e.get('eventID')}/",
                          "icon_key": f"max:{kind}:{name}"})
    items.sort(key=lambda x: x["featured_start"] or "")
    return result(items)
