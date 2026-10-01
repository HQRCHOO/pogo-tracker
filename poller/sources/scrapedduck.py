import re
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
        row = {"id": e["eventID"], "name": e.get("name"), "type": e.get("eventType"),
               "start": e.get("start"), "end": e.get("end")}
        x = e.get("extraData") or {}
        extra = {}
        if isinstance(x.get("spotlight"), dict):          # v3.54: small extras for the PoGo news bar
            extra["bonus"] = x["spotlight"].get("bonus")
            extra["mon"] = x["spotlight"].get("name")
        if isinstance(x.get("communityday"), dict):
            bl = [b.get("text", "") for b in (x["communityday"].get("bonuses") or []) if b.get("text")]
            bl.sort(key=lambda t: 0 if re.search(r"\d\s*[×x]", t) else 1)   # multipliers ("3× Catch Stardust") first
            extra["bonus"] = " · ".join(bl[:2]) or None
            extra["mon"] = ", ".join(m.get("name", "") for m in (x["communityday"].get("spawns") or [])[:2] if m.get("name")) or None
        if isinstance(x.get("raidbattles"), dict):
            extra["bosses"] = [b.get("name") for b in (x["raidbattles"].get("bosses") or []) if b.get("name")][:4]
        extra = {k: v for k, v in extra.items() if v}
        if extra:
            row["extra"] = extra
        items.append(row)
    return result(items, dropped=dropped)
