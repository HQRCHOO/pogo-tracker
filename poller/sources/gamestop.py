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


def purchase_buttons(buttons):
    """The product's own purchase button: visible, outside menus / headers / "you may also like"
    sections, short purchase wording, and the closest such button to the product title."""
    c = [b for b in buttons or [] if b.get("visible", True) and b.get("zone") != "aside"
         and 0 < len((b.get("t") or "").strip()) <= 30 and (BUY.search(b["t"]) or PRE.search(b["t"]) or OUT.search(b["t"]))]
    c.sort(key=lambda b: b.get("dist", 99999))
    return c[:1]


def status_from_buttons(buttons):
    """The purchase button decides: enabled Add to Cart / Pre-order means live;
    disabled, or reading Not Available / Sold Out, means out."""
    for b in purchase_buttons(buttons):
        t, dis = b.get("t") or "", b.get("d")
        if OUT.search(t) or dis:
            return "unavailable"
        if PRE.search(t):
            return "preorder_live"
        if BUY.search(t):
            return "in_stock"
    return "unknown"


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
    items, notes, debug = [], [], None
    for w in watch:
        status, price, note = "unknown", None, None
        try:
            html, text, buttons = render(w["url"], extra_wait=3.0)
            status = status_from_buttons(buttons)
            if status == "unknown":
                status = status_from_text(text)
            seen = [f"{'[disabled] ' if x.get('d') else ''}{x.get('t')} <{(x.get('a') or '').strip()[:50]}> {x.get('zone') or 'main'} {x.get('dist')}px"
                    for x in buttons if x.get("t") and (BUY.search(x["t"]) or PRE.search(x["t"]) or OUT.search(x["t"]))][:15]
            i = max(text.find("Pokémon GO Plus"), 0)
            debug = ("status: " + status + "\npurchase-like buttons: " + ("; ".join(seen) or "none")
                     + "\npage text near the product:\n" + text[i:i + 700])
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
    return result(items, note="; ".join(notes) or "read after the page finished loading (+3 s)", debug=debug)
