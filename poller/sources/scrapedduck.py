"""Pokémon GO events from Leek Duck, via the ScrapedDuck mirror.

Keeps events that ended within the last PAST_DAYS or start within AHEAD_DAYS
(plus undated ones), which keeps dashboard.json small.
"""
import datetime as dt

from ..timefmt import now_pt, wall
from ..util import get, result

URL = "https://raw.githubusercontent.com/bigfoott/ScrapedDuck/data/events.json"
PAST_DAYS, AHEAD_DAYS = 7, 60


def fetch(cfg, prev):
    now = now_pt()
    lo, hi = now - dt.timedelta(days=PAST_DAYS), now + dt.timedelta(days=AHEAD_DAYS)
    items, dropped = [], 0
    for e in get(URL).json():
        if not e.get("eventID"):
            continue
        s, t = wall(e.get("start")), wall(e.get("end"))
        if (t and t < lo) or (s and s > hi):
            dropped += 1
            continue
        items.append({"id": e["eventID"], "name": e.get("name"), "type": e.get("eventType"),
                      "start": e.get("start"), "end": e.get("end")})
    return result(items, dropped=dropped)
