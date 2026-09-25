"""Pokémon TCG sets with release dates.

Primary: pokemontcg.io /v2/sets (one call; POKEMONTCG_KEY optional, raises the rate limit).
Fallback: TCGdex /v2/en/sets, which lists sets without dates; dates are fetched per set
once and cached in dashboard.json (tcgdex_cache) so later runs only fetch new sets.
"""
import datetime as dt
import os
import re

from ..util import get, result

PTCG = "https://api.pokemontcg.io/v2/sets"
TCGDEX = "https://api.tcgdex.net/v2/en/sets"
OTHER = re.compile(r"trainer kit|mcdonald|promo|celebrations: classic|black star", re.I)


def _window(days_back=730, days_ahead=120):
    today = dt.date.today()
    return (today - dt.timedelta(days=days_back)).isoformat(), (today + dt.timedelta(days=days_ahead)).isoformat()


def _row(sid, name, date, series, url, source):
    return {"id": "set-" + str(sid).lower(), "name": name, "date": date, "series": series,
            "category": "other" if OTHER.search(name or "") else "boosters", "source": source, "url": url, "confirmed": True}


def _ptcg():
    headers = {"X-Api-Key": os.environ["POKEMONTCG_KEY"]} if os.environ.get("POKEMONTCG_KEY") else {}
    lo, hi = _window()
    items, page = [], 1
    while True:
        js = get(PTCG, params={"orderBy": "-releaseDate", "pageSize": 250, "page": page}, headers=headers).json()
        data = js.get("data") or []
        for s in data:
            d = str(s.get("releaseDate") or "").replace("/", "-")
            if d and lo <= d <= hi:
                items.append(_row(s.get("id"), s.get("name"), d, s.get("series"), "https://pokemontcg.io/sets/" + str(s.get("id")), "pokemontcg.io"))
        if len(data) < 250 or page >= 4:
            break
        page += 1
    return items


def _tcgdex(prev):
    cache = dict((prev or {}).get("tcgdex_cache") or {})
    lo, hi = _window()
    items = []
    for s in get(TCGDEX).json():
        sid = s.get("id")
        if sid not in cache:
            full = get(f"{TCGDEX}/{sid}").json()
            cache[sid] = {"name": full.get("name"), "date": full.get("releaseDate"),
                          "series": (full.get("serie") or {}).get("name")}
        c = cache[sid]
        if c.get("date") and lo <= c["date"] <= hi:
            items.append(_row(sid, c["name"], c["date"], c.get("series"), "https://tcgdex.dev/", "tcgdex"))
    return items, cache


def fetch(cfg, prev):
    try:
        return result(_ptcg(), api="pokemontcg.io")
    except Exception as e:  # fall back to TCGdex
        items, cache = _tcgdex(prev)
        return result(items, api="tcgdex", tcgdex_cache=cache, primary_error=f"{type(e).__name__}: {str(e)[:120]}")
