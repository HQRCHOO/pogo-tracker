"""Nintendo Store (US) product pages: first-hand online stock for GO Plus+.

Reads the product page's structured data: JSON-LD offers first, then the
Next.js page data (__NEXT_DATA__), then visible button text. Price comes only from
the JSON-LD offer (other prices on the page belong to other products). Configure in
watchlist.yaml as a stock entry with retailer: nintendo and the product URL.
If the page can't be read (blocked, or built entirely by JavaScript), the source
reports an error and saves what it saw for the Sources tab.
"""
import json
import re

from ..confirm import confirm
from ..render import render, RenderUnavailable
from ..util import get, html_text, result
from .gamestop import status_from_buttons, status_from_text


def _walk(obj, keys, found):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in keys and not isinstance(v, (dict, list)):
                found.setdefault(k, v)
            _walk(v, keys, found)
    elif isinstance(obj, list):
        for v in obj:
            _walk(v, keys, found)


def parse(page):
    status, price = None, None
    for block in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', page, re.S | re.I):
        try:
            js = json.loads(block)
        except Exception:
            continue
        for node in (js if isinstance(js, list) else [js]):
            offers = node.get("offers") if isinstance(node, dict) else None
            if isinstance(offers, list):
                offers = offers[0] if offers else None
            if isinstance(offers, dict):
                av = str(offers.get("availability", ""))
                if av:
                    status = ("in_stock" if av.endswith("InStock") else "preorder_live" if av.endswith("PreOrder")
                              else "unavailable")
                try:
                    price = float(offers.get("price")) if offers.get("price") not in (None, "") else price
                except (TypeError, ValueError):
                    pass
    if status is None:
        m = re.search(r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>', page, re.S)
        if m:
            try:
                found = {}
                _walk(json.loads(m.group(1)), {"isSoldOut", "soldOut", "inStock", "isInStock", "purchaseStatus",
                                               "availability", "salePrice", "regularPrice", "finalPrice"}, found)
                if found.get("isSoldOut") is True or found.get("soldOut") is True:
                    status = "unavailable"
                elif found.get("inStock") is True or found.get("isInStock") is True:
                    status = "in_stock"
                elif isinstance(found.get("purchaseStatus"), str):
                    ps = found["purchaseStatus"].lower()
                    status = "in_stock" if "available" in ps and "un" not in ps else ("preorder_live" if "pre" in ps else "unavailable")
                elif isinstance(found.get("availability"), str):
                    av = found["availability"].lower()
                    status = "in_stock" if "in stock" in av or av == "instock" else "unavailable"
            except Exception:
                pass
    if status is None:
        text = html_text(page)
        if re.search(r"\b(sold out|out of stock|currently unavailable)\b", text, re.I):
            status = "unavailable"
        elif re.search(r"\badd to cart\b", text, re.I):
            status = "in_stock"
        elif re.search(r"\bpre-?order\b", text, re.I):
            status = "preorder_live"
    return status, price


def fetch(cfg, prev):
    watch = [s for s in cfg.get("stock", []) if s.get("retailer") == "nintendo" and s.get("url")]
    if not watch:
        return result(ok=None, error="not configured")
    items, debug = [], None
    for w in watch:
        def read():
            page, shown, buttons = render(w["url"], extra_wait=3.0)
            st, pr = parse(page)
            seen = status_from_buttons(buttons)
            if seen == "unknown":
                seen = status_from_text(shown)
            return (seen if seen != "unknown" else (st or "unknown")), {"page": page, "price": pr}

        try:  # read the page after its scripts finish (+3 s); a live reading is re-checked 20 s later
            status, extra, check = confirm(read)
            page, price = extra["page"], extra["price"]
        except RenderUnavailable:
            page = get(w["url"], browser=True).text
            status, price = parse(page)
        except Exception as e:  # blocked or timed out: report unknown, never keep an old status
            items.append({"id": "nin-" + (re.search(r"-(\d+)/?$", w["url"].rstrip("/")) or re.search(r"(\d+)", "0")).group(1),
                          "item": w.get("item") or "Pokémon GO Plus +", "retailer": "Nintendo Store", "area": None,
                          "store": None, "status": "unknown", "price": None, "url": w["url"],
                          "note": f"page didn't load ({type(e).__name__}: {str(e)[:60]})"})
            continue
        if status is None:
            text = html_text(page)
            debug = (text[:1500] if len(text.strip()) > 200 else "Page text was nearly empty (likely built by JavaScript). Raw page start:\n" + page[:1500])
            continue
        pid = re.search(r"-(\d+)/?$", w["url"].rstrip("/"))
        items.append({"id": "nin-" + (pid.group(1) if pid else "item"), "item": w.get("item") or "Pokémon GO Plus +",
                      "retailer": "Nintendo Store", "area": None, "store": None, "status": status, "price": price,
                      "url": w["url"]})
    if not items:
        return result(ok=False, error="page read but no stock status found", debug=debug)
    return result(items)
