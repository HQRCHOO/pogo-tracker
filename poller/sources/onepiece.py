"""One Piece Card Game (English) products from the official products page.

There's no API, so this reads the page text. The pattern matches how the page
lists items ("BOOSTERS <name> Release Date October 30, 2026 MSRP USD $4.99").
If Bandai changes the layout and nothing matches, the poller marks this source
Down and uses card_games.onepiece.manual from watchlist.yaml instead.
"""
import re

from ..util import get, html_text, parse_date, result, slug

URL = "https://en.onepiece-cardgame.com/products/"
PAT = re.compile(
    r"(BOOSTERS|DECKS|OTHERS)\s+(?:PREMIUM BANDAI\s+)?(.{4,120}?)\s+"
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
        items.append({"id": pid, "name": name, "category": CAT.get(cat, cat),
                      "release_date": parse_date(date), "msrp": f"${msrp}" if msrp else None, "url": URL})
    return items


def fetch(cfg, prev):
    return result(parse(html_text(get(URL, browser=True).text)))
