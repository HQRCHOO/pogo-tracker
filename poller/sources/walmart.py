"""Walmart product page, read in the headless browser after it loads (+3 s).

Counts as in stock only when the item is sold by Walmart itself (marketplace sellers at
2x MSRP don't count). Walmart often answers bots with a "Robot or human?" check; that
reports "unknown", never a guess. A live reading is re-checked 20 s later.
"""
import json
import re

from ..confirm import confirm
from ..render import render, RenderUnavailable
from ..util import result


def _walk(obj, keys, found):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in keys and isinstance(v, (str, int, float, bool)) and k not in found:
                found[k] = v
            _walk(v, keys, found)
    elif isinstance(obj, list):
        for v in obj:
            _walk(v, keys, found)


def read(url):
    html, text, buttons = render(url, extra_wait=3.0)
    if re.search(r"robot or human|press & hold|verify you are a human", text, re.I):
        return "unknown", {"why": "Walmart bot check"}
    m = re.search(r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    found = {}
    if m:
        try:
            _walk(json.loads(m.group(1)), {"availabilityStatus", "sellerName", "sellerDisplayName", "price"}, found)
        except Exception:
            pass
    seller = str(found.get("sellerDisplayName") or found.get("sellerName") or "")
    avail = str(found.get("availabilityStatus") or "")
    if avail:
        if avail.upper() == "IN_STOCK":
            return ("in_stock" if "walmart" in seller.lower() else "unavailable"), {"seller": seller, "avail": avail}
        return "unavailable", {"seller": seller, "avail": avail}
    if re.search(r"\b(out of stock|not available)\b", text, re.I):
        return "unavailable", {"why": "page says out of stock"}
    return "unknown", {"why": "no availability found"}


def fetch(cfg, prev):
    watch = [s for s in cfg.get("stock", []) if s.get("retailer") == "walmart" and s.get("url")]
    if not watch:
        return result(ok=None, error="not configured")
    items, notes = [], []
    for w in watch:
        try:
            status, extra, check = confirm(lambda: read(w["url"]))
            note = ", ".join(f"{k} {v}" for k, v in extra.items() if v) + (f" · {check}" if check else "")
        except RenderUnavailable:
            status, note = "unknown", "browser not available"
        except Exception as e:
            status, note = "unknown", f"page didn't load ({type(e).__name__}: {str(e)[:60]})"
        notes.append(note)
        items.append({"id": "wm-" + re.sub(r"\D", "", w["url"])[-10:], "item": w.get("item"), "retailer": "Walmart",
                      "area": None, "store": None, "status": status, "price": None, "note": note, "url": w["url"]})
    return result(items, note="; ".join(notes))
