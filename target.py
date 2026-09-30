"""Target stock via RedSky (unofficial; Target changes it without notice).

Set target.redsky_url in watchlist.yaml to the current fulfillment URL template
from retail-drop-monitor, using {tcin}, {store_id}, {zip} and {key} placeholders,
and save the key as the TARGET_REDSKY_KEY secret. Until then this reports
"not configured".
"""
import os

from ..util import get, result

LIVE = {"IN_STOCK": "in_stock", "LIMITED_STOCK": "low", "PRE_ORDER_SELLABLE": "preorder_live",
        "OUT_OF_STOCK": "unavailable", "UNAVAILABLE": "unavailable"}


def _statuses(node, found, ship=False):
    """Collect (is_shipping, status) pairs; statuses under shipping_options are online, the rest in-store."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k.endswith("availability_status") and isinstance(v, str):
                found.append((ship, v))
            else:
                _statuses(v, found, ship or k == "shipping_options")
    elif isinstance(node, list):
        for v in node:
            _statuses(v, found, ship)


def _best(values):
    for s in ("PRE_ORDER_SELLABLE", "IN_STOCK", "LIMITED_STOCK"):
        if s in values:
            return LIVE[s]
    return "unavailable" if values else None


def fetch(cfg, prev):
    tpl = (cfg.get("target") or {}).get("redsky_url")
    key = os.environ.get("TARGET_REDSKY_KEY", "")
    watch = [s for s in cfg.get("stock", []) if s.get("retailer") == "target" and str(s.get("tcin", "")).isdigit()]
    if not tpl or not watch:
        return result(ok=None, error="not configured")
    stores = (cfg.get("target") or {}).get("stores", [])  # [{area, store_id}]
    items, cache = [], {}
    for w in watch:
        online = None
        for st in stores or [{"area": None, "store_id": ""}]:
            zip_ = next((a["zip"] for a in cfg.get("location", {}).get("areas", []) if a["name"] == st.get("area")), "")
            ck = (w["tcin"], st.get("store_id", ""))
            if ck not in cache:  # one request per store, even if it serves two areas
                found = []
                _statuses(get(tpl.format(tcin=w["tcin"], store_id=st.get("store_id", ""), zip=zip_, key=key), browser=True).json(), found)
                cache[ck] = found
            found = cache[ck]
            online = online or _best([v for ship, v in found if ship])
            if st.get("store_id"):
                items.append({"id": f"tg-{w['tcin']}-{st['store_id']}-{(st.get('area') or '').lower().replace(' ', '')}",
                              "item": w.get("item"), "retailer": "Target", "area": st.get("area"),
                              "store": st.get("name") or st.get("store_id"),
                              "status": _best([v for ship, v in found if not ship]) or "unavailable", "price": None,
                              "url": f"https://www.target.com/p/-/A-{w['tcin']}"})
        items.insert(0, {"id": f"tg-{w['tcin']}-online", "item": w.get("item"), "retailer": "Target", "area": None,
                         "store": None, "status": online or "unavailable", "price": None,
                         "url": f"https://www.target.com/p/-/A-{w['tcin']}"})
    return result(items)
