"""Gundam Card Game products and release dates from gcg-api (weekly refresh)."""
import datetime as dt

from ..util import get, result

URL = "https://raw.githubusercontent.com/yzRobo/gcg-api/main/data/products.json"


def fetch(cfg, prev):
    cutoff = (dt.date.today() - dt.timedelta(days=90)).isoformat()
    items = []
    for p in get(URL).json():
        rd = p.get("release_date")
        if rd and rd < cutoff:
            continue
        items.append({"id": p.get("product_id"), "name": p.get("name"),
                      "category": p.get("category_label"), "set_code": p.get("set_code"),
                      "release_date": rd, "msrp": p.get("msrp")})
    return result(items)
