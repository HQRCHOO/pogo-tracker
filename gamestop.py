"""GameStop product pages: read the schema.org availability in the page's embedded JSON.
GameStop often blocks automated requests (HTTP 403); that shows as Down, not a crash."""
import re

from ..util import get, result

MAP = {"instock": "in_stock", "preorder": "preorder_live", "outofstock": "unavailable",
       "soldout": "unavailable", "limitedavailability": "low"}


def fetch(cfg, prev):
    watch = [s for s in cfg.get("stock", []) if s.get("retailer") == "gamestop" and s.get("url")]
    if not watch:
        return result(ok=None, error="not configured")
    items = []
    for w in watch:
        html = get(w["url"], browser=True).text
        m = re.search(r'schema\.org/(InStock|PreOrder|OutOfStock|SoldOut|LimitedAvailability)', html)
        price = re.search(r'"price"\s*:\s*"?([\d.]+)', html)
        items.append({"id": "gs-" + re.sub(r"\D", "", w["url"])[-8:], "item": w.get("item") or w.get("name"),
                      "retailer": "GameStop", "area": None, "store": None,
                      "status": MAP.get(m.group(1).lower(), "unavailable") if m else "unavailable",
                      "price": float(price.group(1)) if price else None, "url": w["url"]})
    return result(items)
