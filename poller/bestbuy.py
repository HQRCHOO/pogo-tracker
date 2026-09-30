"""Best Buy Products + Stores API: chain status and nearby in-store stock per area ZIP."""
import os

from ..util import get, result

API = "https://api.bestbuy.com/v1"
STATUS = {"available": "in_stock", "preorder": "preorder_live", "soldout": "unavailable",
          "comingsoon": "not_open", "backorder": "unavailable"}


def fetch(cfg, prev):
    key = os.environ.get("BESTBUY_KEY")
    watch = [s for s in cfg.get("stock", []) if s.get("retailer") == "bestbuy"]
    if not key or not any(str(s.get("sku", "")).isdigit() for s in watch):
        return result(ok=None, error="not configured")
    loc = cfg.get("location", {})
    radius = float(loc.get("radius_miles", 10))
    items = []
    for w in watch:
        sku = str(w.get("sku", ""))
        if not sku.isdigit():
            continue
        p = get(f"{API}/products/{sku}.json", params={
            "apiKey": key, "show": "sku,name,salePrice,orderable,onlineAvailability,url,upc"}).json()
        status = STATUS.get(str(p.get("orderable", "")).lower().replace(" ", ""), "unavailable")
        if p.get("onlineAvailability") and status == "unavailable":
            status = "in_stock"
        items.append({"id": f"bb-{sku}", "item": w.get("item") or p.get("name"), "retailer": "Best Buy",
                      "area": None, "store": None, "status": status, "price": p.get("salePrice"),
                      "upc": p.get("upc"), "url": p.get("url"), "note": p.get("orderable")})
        seen = {}
        zips = (cfg.get("bestbuy") or {}).get("zips") or [dict(a, radius_miles=radius) for a in loc.get("areas", [])]
        for area in zips:
            stores = get(f"{API}/products/{sku}/stores.json",
                         params={"postalCode": area["zip"], "apiKey": key}).json().get("stores", [])
            for st in stores:
                dist = st.get("distance")
                if dist is not None and float(dist) > float(area.get("radius_miles", radius)):
                    continue
                sid = st.get("storeID")
                if sid in seen and (dist is None or float(dist) >= seen[sid]["_d"]):
                    continue
                row = {"id": f"bb-{sku}-{sid}", "item": w.get("item") or p.get("name"),
                       "retailer": "Best Buy", "area": area.get("area") or area.get("name"),
                       "store": st.get("name") or st.get("city"), "status": "in_stock",
                       "price": p.get("salePrice"), "url": p.get("url"), "_d": float(dist or 0)}
                seen[sid] = row
        for row in seen.values():
            row.pop("_d", None)
            items.append(row)
    return result(items)
