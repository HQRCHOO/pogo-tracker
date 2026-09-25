"""Dragon Ball Super Card Game (English): Fusion World from the official products page.
Masters has no page parser yet, so its sets come from card_games.dragonball.manual.

The Fusion World page lists items as "<NAME> [FB11] RELEASE: October 16, 2026 MSRP: 4.99 USD".
If nothing matches, the poller marks this source Down and uses the manual list.
"""
import re

from ..util import get, html_text, parse_date, result

URL = "https://www.dbs-cardgame.com/fw/en/products/"
PAT = re.compile(
    r"((?:BOOSTER PACK|STARTER DECK|PREMIUM PACK|STORY BOOSTER)[^\[\]]{0,80}\[([A-Z]{2}\d{2})\])\s*"
    r"RELEASE\s*:\s*([A-Z][a-z]+\s+\d{1,2},\s+\d{4}|TBA)(?:\s*MSRP\s*:\s*([\d.]+)\s*USD)?", re.I)


def parse(text):
    items, seen = [], set()
    for name, code, date, msrp in PAT.findall(text):
        pid = code.lower()
        if pid in seen:
            continue
        seen.add(pid)
        items.append({"id": pid, "format": "Fusion World", "name": name.strip(),
                      "category": "STARTER DECK" if "STARTER" in name.upper() else "BOOSTER PACK",
                      "release_date": parse_date(date), "msrp": f"${msrp}" if msrp else None, "url": URL})
    return items


def fetch(cfg, prev):
    return result(parse(html_text(get(URL, browser=True).text)))
