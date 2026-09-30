"""Best Buy: the button-state data behind the product page's Add to Cart / Sold Out button.

No key needed, but it isn't an official API: Best Buy can change or block it. Reads the
SKUs of the Best Buy stock entries in watchlist.yaml. A live reading is re-checked 20 s later.
"""
from ..confirm import confirm
from ..util import get, result

URL = ("https://www.bestbuy.com/button-state/api/v5/button-state?skus={sku}&conditions=NONE&storeId="
       "&destinationZipCode=&context=pdp&consolidated=false&source=buttonView&xboxAllAccess=false")
MAP = {"ADD_TO_CART": "in_stock", "PRE_ORDER": "preorder_live", "SOLD_OUT": "unavailable",
       "COMING_SOON": "unavailable", "CHECK_STORES": "unavailable", "UNAVAILABLE": "unavailable"}


def read(sku):
    js = get(URL.format(sku=sku), browser=True, headers={"Accept": "application/json",
             "Referer": f"https://www.bestbuy.com/site/{sku}.p?skuId={sku}"}).json()
    infos = js.get("buttonStateResponseInfos") or []
    info = next((i for i in infos if str(i.get("skuId")) == str(sku)), infos[0] if infos else {})
    state = str(info.get("buttonState") or "")
    return MAP.get(state, "unknown"), {"state": state, "text": info.get("displayText")}


def fetch(cfg, prev):
    watch = [s for s in cfg.get("stock", []) if s.get("retailer") == "bestbuy" and str(s.get("sku", "")).isdigit()]
    if not watch:
        return result(ok=None, error="not configured")
    items, notes = [], []
    for w in watch:
        status, extra, check = confirm(lambda: read(w["sku"]))
        note = f"button: {extra.get('text') or extra.get('state') or '?'}" + (f" · {check}" if check else "")
        notes.append(note)
        items.append({"id": f"bbb-{w['sku']}", "item": w.get("item"), "retailer": "Best Buy", "area": None,
                      "store": None, "status": status, "price": None, "note": note,
                      "url": f"https://www.bestbuy.com/site/{w['sku']}.p?skuId={w['sku']}"})
    return result(items, note="; ".join(notes))
