"""GameStop product pages, read the way a person sees them.

GameStop's page first loads with a placeholder buy button (and "InStock" in its
embedded data), then its scripts fetch the real availability a second or two later.
So the page is opened in headless Chromium, allowed to finish loading, given 3 more
seconds, and only then is the final button / availability text read.
If the browser can't run, the status is "unknown" — never a guessed "in stock".
"""
import re

from ..render import render, RenderUnavailable
from ..util import result

OUT = re.compile(r"\b(not available|out of stock|sold out|currently unavailable|unavailable online|no longer available)\b", re.I)
PRE = re.compile(r"\bpre-?order( now)?\b", re.I)
BUY = re.compile(r"\badd to cart\b", re.I)


def status_from_buttons(buttons):
    """The buy button decides: an enabled Add to Cart / Pre-order means live;
    a disabled one, or a button reading Not Available / Sold Out, means out."""
    live, out = None, False
    for b in buttons or []:
        t, dis = b.get("t") or "", b.get("d")
        if BUY.search(t) or PRE.search(t):
            if dis:
                out = True
            else:
                live = "preorder_live" if PRE.search(t) else "in_stock"
        elif OUT.search(t):
            out = True
    if live:
        return live
    return "unavailable" if out else "unknown"


def status_from_text(text):
    """Fallback on visible text: out-of-stock wording wins over a buy phrase."""
    if OUT.search(text or ""):
        return "unavailable"
    if PRE.search(text or ""):
        return "preorder_live"
    if BUY.search(text or ""):
        return "in_stock"
    return "unknown"


def fetch(cfg, prev):
    watch = [s for s in cfg.get("stock", []) if s.get("retailer") == "gamestop" and s.get("url")]
    if not watch:
        return result(ok=None, error="not configured")
    items, notes = [], []
    for w in watch:
        status, price, note = "unknown", None, None
        try:
            html, text, buttons = render(w["url"], extra_wait=3.0)
            status = status_from_buttons(buttons)
            if status == "unknown":
                status = status_from_text(text)
            pm = re.search(r"\$\s*(\d{2,3}\.\d{2})", text)
            price = float(pm.group(1)) if pm else None
            if status == "unknown":
                note = "page loaded but showed no availability wording"
        except RenderUnavailable:
            note = "browser not available; status not checked"
        except Exception as e:  # blocked or timed out: say so, and never keep an old "in stock"
            note = f"page didn't load ({type(e).__name__}: {str(e)[:80]})"
        items.append({"id": "gs-" + re.sub(r"\D", "", w["url"])[-8:], "item": w.get("item") or w.get("name"),
                      "retailer": "GameStop", "area": None, "store": None, "status": status,
                      "price": price, "url": w["url"], "note": note})
        if note:
            notes.append(note)
    return result(items, note="; ".join(notes) or "read after the page finished loading (+3 s)")
