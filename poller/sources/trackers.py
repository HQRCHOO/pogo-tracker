"""Stock status from public tracker pages: HotStock and TrackaLacker.

Neither has a public API, so this reads their product pages (every 30 min by
default, with a descriptive bot User-Agent). Status here is secondhand: each row
says which tracker reported it. Configure in watchlist.yaml under `trackers:`.

  trackers:
    - item: Pokémon GO Plus +
      hotstock: https://www.hotstock.io/us/p/pokemon-go-plus
      trackalacker: https://www.trackalacker.com/products/showcase/pokemon-go-plus
      match:                  # keep only rows whose retailer link contains this text
        Best Buy: "6537404"
        Target: "88714054"

HotStock matches stores loosely (it listed a tablet and mac and cheese as GO Plus+
sources), so only retailers listed under `match`, with a matching link, are kept.
TrackaLacker listing pages also carry a "Recent Changes" table; status changes in
it are returned as `history` for the Log.
"""
import datetime as dt
import html as htmlmod
import json
import re
from urllib.parse import parse_qs, unquote, urlparse

from ..util import get, html_text, result

UA_NOTE = "TrackMaster personal dashboard poller (low frequency)"
SHOP = {"bestbuy": "Best Buy", "target": "Target", "walmart": "Walmart", "gamestop": "GameStop", "amazon": "Amazon",
        "ebay": "eBay", "samsclub": "Sam's Club", "costco": "Costco", "pokemoncenter": "Pokémon Center",
        "antonline": "Antonline", "lenovo": "Lenovo", "newegg": "Newegg"}
LIVE_ORDER = {"in_stock": 3, "preorder_live": 2, "low": 2, "unavailable": 0}


def norm_status(text):
    t = (text or "").lower().replace("-", " ")
    if "in stock" in t and "out of" not in t:
        return "in_stock"
    if "pre order" in t or "preorder" in t:
        return "preorder_live"
    if "limited" in t or "low stock" in t:
        return "low"
    return "unavailable"


def unwrap(url):
    """Affiliate redirect -> the retailer URL inside it."""
    url = htmlmod.unescape(url or "")
    try:
        q = parse_qs(urlparse(url).query)
        for k in ("u", "url", "murl"):
            if q.get(k):
                return unquote(q[k][0])
    except Exception:
        pass
    return url


def clean(url):
    """Drop affiliate tags (e.g. Amazon tag=) from a retailer link."""
    return re.sub(r"([?&])(tag|affid|affiliate|ref|clickid)=[^&]*&?", r"\1", url or "").rstrip("?&")


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")


# ---------------- HotStock ----------------
def parse_hotstock(page, item, match, src_url):
    rows = []
    parts = re.split(r"(?=shoplogo_[a-z0-9]+\.(?:png|svg))", page)
    for chunk in parts[1:]:
        key = re.match(r"shoplogo_([a-z0-9]+)", chunk).group(1)
        chunk = chunk[:4000]
        retailer = SHOP.get(key, key.title())
        mode = re.search(r"\((Delivery|Pickup|In[- ]store)\)", chunk[:600])
        label = retailer + (f" ({mode.group(1)})" if mode else "")
        want = match.get(retailer) or match.get(label)
        if not want:
            continue
        hrefs = [unwrap(h) for h in re.findall(r'href="([^"]+)"', chunk)]
        link = next((h for h in hrefs if want.lower() in h.lower()), None)
        if not link:
            continue
        st = re.search(r">\s*(IN STOCK|OUT OF STOCK|PRE-?ORDER|SOLD OUT|LIMITED)\s*<", chunk, re.I)
        if not st:
            continue
        price = re.search(r"\$\s*([\d,]+\.\d{2})", chunk)
        rows.append({"retailer": retailer, "label": label, "status": norm_status(st.group(1)),
                     "price": float(price.group(1).replace(",", "")) if price else None,
                     "url": link, "via": "HotStock", "tracker_url": src_url})
    # one row per retailer label
    out, seen = [], set()
    for r in rows:
        if r["label"] not in seen:
            seen.add(r["label"])
            out.append(r)
    return out


# ---------------- TrackaLacker ----------------
CHANGE = re.compile(r"(\d{1,2}/\d{1,2}/\d{4}),?\s+(\d{1,2}:\d{2}:\d{2}\s*[AP]M)\s+\$\s*([\d,]+\.\d{2})\s+"
                    r"(In Stock|Out of Stock|Pre-?Order|Sold Out|Unavailable|Limited Stock)", re.I)


def parse_listing(page, item, match, src_url):
    title = re.search(r"<title>([^<]+)</title>", page, re.I)
    retailer = None
    if title:
        m = re.search(r"\bat\s+(.+?)\s+-\s+(?:Track|TrackaLacker)", htmlmod.unescape(title.group(1)))
        retailer = m.group(1).strip() if m else None
    status, price = None, None
    for block in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', page, re.S | re.I):
        try:
            js = json.loads(block)
        except Exception:
            continue
        offers = (js.get("offers") if isinstance(js, dict) else None) or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        if offers:
            status = norm_status(re.sub(r".*/", "", str(offers.get("availability", ""))).replace("OutOfStock", "out of stock")
                                 .replace("InStock", "in stock").replace("PreOrder", "pre order"))
            try:
                price = float(offers.get("price")) if offers.get("price") is not None else None
            except (TypeError, ValueError):
                price = None
    text = html_text(page)
    if status is None:
        st = re.search(r"\b(In Stock|Out of Stock|Pre-?Order|Sold Out)\b", text)
        status = norm_status(st.group(1)) if st else None
    link = None
    for h in re.findall(r'href="([^"]+)"', page):
        u = unwrap(h)
        if retailer and u.startswith("http") and "trackalacker" not in u and slug(retailer).split("-")[0] in u.lower().replace(" ", ""):
            link = u
            break
    hist = []
    for d, t, p, s in CHANGE.findall(text):
        try:
            at = dt.datetime.strptime(f"{d} {t.replace(' ', '')}", "%m/%d/%Y %I:%M:%S%p").replace(tzinfo=dt.timezone.utc)
        except ValueError:
            continue
        hist.append({"at": at.isoformat().replace("+00:00", "Z"), "price": float(p.replace(",", "")), "status": norm_status(s)})
    if not retailer or status is None:
        return None, []
    want = match.get(retailer)
    if match and not want:
        return None, []
    row = {"retailer": retailer, "label": retailer, "status": status, "price": price, "url": link or src_url,
           "via": "TrackaLacker", "tracker_url": src_url}
    # status changes only (oldest first); the oldest counts only if it was live
    hist.sort(key=lambda h: h["at"])
    events, last = [], None
    for h in hist:
        if h["status"] != last and (last is not None or h["status"] in ("in_stock", "preorder_live")):
            events.append(dict(h, retailer=retailer, item=item, source="TrackaLacker", tracker_url=src_url, url=link))
        last = h["status"]
    return row, events


def parse_showcase_links(page, base):
    links, seen = [], set()
    for h in re.findall(r'href="(/products/showcase/[^"/]+/listings/\d+/[^"#?]+)"', page):
        full = "https://www.trackalacker.com" + h
        if full not in seen:
            seen.add(full)
            links.append(full)
    return links


def fetch(cfg, prev):
    watch = cfg.get("trackers") or []
    if not watch:
        return result(ok=None, error="not configured")
    rows, history, errors, reads = [], [], [], 0
    for w in watch:
        item, match = w.get("item") or "Pokémon GO Plus +", w.get("match") or {}
        if w.get("hotstock"):
            try:
                rows += [dict(r, item=item) for r in parse_hotstock(get(w["hotstock"], browser=True).text, item, match, w["hotstock"])]
                reads += 1
            except Exception as e:
                errors.append(f"HotStock: {type(e).__name__}")
        if w.get("trackalacker"):
            try:
                page = get(w["trackalacker"], browser=True).text
                reads += 1
                listing_urls = [w["trackalacker"]] if "/listings/" in w["trackalacker"] else parse_showcase_links(page, w["trackalacker"])[:8]
                for u in listing_urls:
                    lp = page if u == w["trackalacker"] else get(u, browser=True).text
                    row, ev = parse_listing(lp, item, match, u)
                    if row:
                        rows.append(dict(row, item=item))
                        history += ev
            except Exception as e:
                errors.append(f"TrackaLacker: {type(e).__name__}")
    # merge per item + retailer label: the livelier status wins; note both trackers
    merged = {}
    for r in rows:
        k = (r["item"], r["label"])
        cur = merged.get(k)
        if not cur:
            merged[k] = r
            continue
        via = " + ".join(sorted({cur["via"], r["via"]}))
        best = r if LIVE_ORDER.get(r["status"], 0) > LIVE_ORDER.get(cur["status"], 0) else cur
        merged[k] = dict(best, via=via, price=best.get("price") or cur.get("price") or r.get("price"))
    items = [{"id": "trk-" + slug(r["label"]) + "-" + slug(r["item"])[:24], "item": r["item"], "retailer": r["label"],
              "area": None, "store": None, "status": r["status"], "price": r.get("price"), "url": clean(r["url"]),
              "via": r["via"], "tracker_url": r["tracker_url"]} for r in merged.values()]
    if not items and not reads:
        return result(ok=False, error="; ".join(errors) or "no tracker pages read")
    return result(items, history=history, note="; ".join(errors) or None,
                  debug=None if items else "trackers read but 0 rows matched the watchlist")
