"""One Piece Card Game (English) products from the official products page.

There's no API, so this reads the page text. The pattern matches how the page
lists items ("BOOSTERS <name> Release Date October 30, 2026 MSRP USD $4.99").
A name may not run across another item's price or category word, so an item
without a date (e.g. sleeves) can't swallow the next product.
If Bandai changes the layout and nothing matches, the poller marks this source
Down, saves a text snippet for debugging, and uses card_games.onepiece.manual.
"""
import re

from ..util import get, html_text, parse_date, result, slug

URL = "https://en.onepiece-cardgame.com/products/"
PUNK = "https://raw.githubusercontent.com/buhbbl/punk-records/main/english/"   # official pack list + cards as JSON
STOP = r"(?!MSRP|BOOSTERS |DECKS |OTHERS |PREMIUM BANDAI |Release Date|Delivery Month)"
PAT = re.compile(
    r"(BOOSTERS|DECKS|OTHERS)\s+(?:PREMIUM BANDAI\s+)?((?:" + STOP + r".){4,120}?)\s+"
    r"(?:Release Date|Delivery Month)\s+([A-Z][a-z]+(?:\s+\d{1,2},)?\s+\d{4}|TBA)"
    r"(?:\s+MSRP\s+USD\s+\$([\d.]+))?")
CAT = {"BOOSTERS": "BOOSTER PACK", "DECKS": "DECKS", "OTHERS": "OTHERS"}


def parse(text):
    items, seen = [], set()
    for cat, name, date, msrp in PAT.findall(text):
        name = name.strip(" -")
        code = re.search(r"\[([A-Z]{2,3}-?\d{2})\]", name)
        pid = slug(code.group(1)).replace("-", "") if code else slug(name)
        if pid in seen:
            continue
        seen.add(pid)
        category = CAT.get(cat, cat)
        if re.match(r"(EXTRA |PREMIUM )?BOOSTER PACK", name, re.I):
            category = "BOOSTER PACK"
        items.append({"id": pid, "name": name, "category": category,
                      "release_date": parse_date(date), "msrp": f"${msrp}" if msrp else None, "url": URL})
    return items


def cross_check(items):
    """punk-records (built from the official card list): confirm names of released packs and add card counts.
    It only covers packs already released and has no dates, so upcoming sets are left as they are."""
    try:
        packs = get(PUNK + "packs.json").json()
    except Exception:
        return 0
    by_label = {}
    for pid, p in packs.items():
        lab = (p.get("title_parts") or {}).get("label")
        if lab:
            by_label[lab.replace("-", "").upper()] = (pid, p)
    counts = {}
    try:  # one index file lists every card with its pack; parallel prints (_p1, _p2…) aren't counted twice
        for cid, c in get(PUNK + "index/cards_by_id.json", timeout=60).json().items():
            if "_p" not in cid:
                counts[str(c.get("pack_id"))] = counts.get(str(c.get("pack_id")), 0) + 1
    except Exception:
        pass
    hits = 0
    for it in items:
        key = str(it.get("id", "")).upper()
        if key not in by_label:
            continue
        pid, p = by_label[key]
        tp = p.get("title_parts") or {}
        it["official_name"] = p.get("raw_title")
        if counts.get(str(pid)):
            it["card_count"] = counts[str(pid)]
        if not re.search(r"\[[A-Z]{2,3}-?\d{2}\]", it.get("name") or "") and p.get("raw_title"):
            it["name"] = p["raw_title"]   # the page reader garbled it; use the official title
        hits += 1
    return hits


def fetch(cfg, prev):
    text = html_text(get(URL, browser=True).text)
    items = parse(text)
    hits = cross_check(items) if items else 0
    return result(items, debug=None if items else text[:1500], note=f"punk-records confirmed {hits}" if hits else None)
