"""Featured Power Spot (Max Battle) bosses from ScrapedDuck's events feed, plus a roster of every current
Power Spot boss so the poller can pack their icons (v3.51).

Max Mondays ("Dynamax Sizzlipede during Max Monday") and Max Battle Days ("Gigantamax Cinderace Max Battle Day")
name their featured boss. The full weekly pool isn't published as data; the PoGo agent writes it to the
dashboard database (max_battles/current) and the page merges the two.
"""
import datetime as dt
import re

from ..util import get, result

URL = "https://raw.githubusercontent.com/bigfoott/ScrapedDuck/data/events.json"
SNACKNAP = "https://www.snacknap.com/max-battles"   # the live list the PoGo agent reads
KEEP_DAYS = 30
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
    roster, note = _roster(cfg, prev, items, now)
    return result(items, roster=roster, note=note)


def _plain(name):
    m = re.match(r"^(.+?) \((Galarian|Alolan|Hisuian|Paldean)\)$", name)
    return f"{m.group(2)} {m.group(1)}" if m else name


def _snacknap(prev):
    """Best effort: find known Pokémon names on Snack Nap's Max Battles page (layout-independent)."""
    from ..util import html_text
    known = {_plain(x[0]) for x in ((prev.get("gamedata") or {}).get("dex") or []) if x and x[0]}
    known = {n for n in known if len(n) >= 4 and "(" not in n}
    if not known:
        return None, "no Pokémon list yet"
    text = html_text(get(SNACKNAP, browser=True, timeout=25).text)
    found = sorted(n for n in known if re.search(r"(?<![A-Za-z])" + re.escape(n) + r"(?![A-Za-z])", text))
    if not 8 <= len(found) <= 150:
        return None, f"page read, but {len(found)} names found (ignored)"
    return found, f"{len(found)} names"


def _roster(cfg, prev, featured, now):
    today = now.date().isoformat()
    old = dict(prev.get("max_roster") or {})
    seed = cfg.get("max_roster") or {}
    roster = {}
    def add(name, kind, seen):
        k = f"{kind}:{name}"
        roster[k] = max(seen, roster.get(k, ""), old.get(k, ""))
    for kind in ("dynamax", "gigantamax"):
        for n in seed.get(kind) or []:
            add(n, kind, today)
    for f in featured:
        add(f["name"], f["kind"], today)
    try:
        found, sn_note = _snacknap(prev)
    except Exception as e:
        found, sn_note = None, f"unreadable ({type(e).__name__})"
    for n in found or []:
        add(n, "dynamax", today)
    cutoff = (now - dt.timedelta(days=KEEP_DAYS)).date().isoformat()
    for k, seen in old.items():            # keep recently seen names so a rotation doesn't make icons flicker
        if k not in roster and seen >= cutoff:
            roster[k] = seen
    return dict(sorted(roster.items())), f"roster {len(roster)} · Snack Nap: {sn_note}"
