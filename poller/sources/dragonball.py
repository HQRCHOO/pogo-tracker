"""Dragon Ball Super Card Game (English): Fusion World from the official site.
Masters has no reader yet, so its sets come from card_games.dragonball.manual.

Primary: follow product links on the products page (…/fw/en/products/01_422.html)
and read each product page (code, title, release date, MSRP). That survives
changes to the list layout. Fallback: the old list-page text pattern.
If nothing matches, the poller marks this source Down, saves a text snippet,
and uses the manual list.
"""
import re
from urllib.parse import urljoin

from ..util import get, html_text, parse_date, result

URL = "https://www.dbs-cardgame.com/fw/en/products/"
LINK = re.compile(r'href="([^"]*?/fw/en/products/\d+_\d+\.html)"', re.I)
CODE = re.compile(r"\[((?:FB|FS|SB|SD|FP|EB)\d{2})\]", re.I)
DATE = re.compile(r"RELEASE(?:\s*DATE)?\s*[:：]?\s*([A-Z][a-z]+\.?\s+\d{1,2},?\s+\d{4}|TBA)", re.I)
MSRP = re.compile(r"MSRP\s*[:：]?\s*(?:USD\s*)?\$?\s*([\d]+(?:\.\d{2})?)\s*(?:USD)?", re.I)
KIND = re.compile(r"(BOOSTER PACK|STARTER DECK|PREMIUM PACK|STORY BOOSTER|MANGA BOOSTER|THEME BOOSTER)", re.I)
MAX_PAGES = 12


def parse_product(text, url):
    code = CODE.search(text)
    if not code:
        return None
    i = code.start()
    kind = None
    for k in KIND.finditer(text[max(0, i - 160):i + 10]):
        kind = k.group(1).upper()
    start = max(0, i - 120)
    title = text[start:code.end()]
    if kind and kind in title.upper():
        title = title[title.upper().rfind(kind):]
    title = re.sub(r"\s+", " ", title).strip(" -·|")
    d = DATE.search(text, code.end())
    m = MSRP.search(text, code.end())
    return {"id": code.group(1).lower(), "format": "Fusion World", "name": title,
            "category": "STARTER DECK" if "STARTER" in (kind or title.upper()) else "BOOSTER PACK",
            "release_date": parse_date(d.group(1)) if d else None,
            "msrp": f"${m.group(1)}" if m else None, "url": url}


LIST_PAT = re.compile(
    r"((?:BOOSTER PACK|STARTER DECK|PREMIUM PACK|STORY BOOSTER)[^\[\]]{0,80}\[([A-Z]{2}\d{2})\])\s*"
    r"RELEASE\s*:\s*([A-Z][a-z]+\s+\d{1,2},\s+\d{4}|TBA)(?:\s*MSRP\s*:\s*([\d.]+)\s*USD)?", re.I)


def parse(text):
    """Old list-page pattern (fallback)."""
    items, seen = [], set()
    for name, code, date, msrp in LIST_PAT.findall(text):
        pid = code.lower()
        if pid in seen:
            continue
        seen.add(pid)
        items.append({"id": pid, "format": "Fusion World", "name": name.strip(),
                      "category": "STARTER DECK" if "STARTER" in name.upper() else "BOOSTER PACK",
                      "release_date": parse_date(date), "msrp": f"${msrp}" if msrp else None, "url": URL})
    return items


def fetch(cfg, prev):
    html = get(URL, browser=True).text
    links, seen_links = [], set()
    for href in LINK.findall(html):
        full = urljoin(URL, href)
        if full not in seen_links:
            seen_links.add(full)
            links.append(full)
    items, seen = [], set()
    for link in links[:MAX_PAGES]:
        try:
            row = parse_product(html_text(get(link, browser=True).text), link)
        except Exception:
            row = None
        if row and row["id"] not in seen:
            seen.add(row["id"])
            items.append(row)
    if not items:
        items = parse(html_text(html))
    return result(items, links=len(links), debug=None if items else html_text(html)[:1500])
