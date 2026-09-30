"""Pokémon icons, packed into dashboard.json as tiny WebP data URIs.

A published page can't load pictures from other sites, so the poller fetches each icon once,
shrinks it to 40 px and embeds it. ScrapedDuck names the file (e.g. pm83.fGALARIAN.icon.png);
Leek Duck's image server refuses automated downloads, so the same file is read from the
PokeMiners Pokémon GO asset collection on GitHub. Icons are cached run to run in
dashboard.json["icons"]; ones no longer used are dropped.
"""
import base64
import io
import re
import time
from urllib.parse import quote

import requests

BASE = "https://raw.githubusercontent.com/PokeMiners/pogo_assets/master/Images/Pokemon/Addressable%20Assets/"
BASE2 = "https://raw.githubusercontent.com/pokemon-go-api/assets/main/Pokemon/"   # second source, also has shiny icons
SIZE = 40
MAX_NEW_PER_RUN = 450
TIME_BUDGET = 90  # seconds


def icon_file(url):
    """'https://cdn.leekduck.com/.../pm83.fGALARIAN.icon.png' -> 'pm83.fGALARIAN.icon.png'"""
    if not url:
        return None
    name = str(url).rsplit("/", 1)[-1]
    return name if name.endswith(".png") else None


def _fallbacks(name):
    yield name
    base = re.match(r"(pm\d+)", name)
    if base:
        forms = re.sub(r"\.c[A-Z0-9_]+", "", name)            # costume
        if forms != name:
            yield forms
        yield base.group(1) + ".icon.png"                     # plain species


def _fetch(name, session):
    from PIL import Image
    for cand, base in [(c, b) for c in _fallbacks(name) for b in (BASE, BASE2)]:
        r = session.get(base + quote(cand), timeout=15)
        if r.status_code != 200 or not r.content:
            continue
        im = Image.open(io.BytesIO(r.content)).convert("RGBA")
        box = im.getbbox()
        if box:
            im = im.crop(box)
        im.thumbnail((SIZE, SIZE))
        buf = io.BytesIO()
        im.save(buf, "WEBP", quality=72, method=6)
        return "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode()
    return None


def used(d):
    names = set()
    for r in d.get("raids") or []:
        names.add(r.get("icon"))
    for t in d.get("research") or []:
        for w in t.get("reward_detail") or []:
            names.add(w.get("icon"))
    for e in d.get("eggs") or []:
        names.add(e.get("icon"))
    for b in d.get("raid_difficulty") or []:
        names.add(b.get("shiny_icon"))
    for g in d.get("rocket") or []:
        for slot in g.get("slots") or []:
            for p in slot:
                names.add(p.get("icon"))
    names.discard(None)
    return names


def build(new, prev, out=print):
    cache = dict(prev.get("icons") or {})
    need = used(new)
    missing = sorted(n for n in need if n not in cache)
    got, failed, t0 = 0, [], time.time()
    if missing:
        s = requests.Session()
        s.headers["User-Agent"] = "TrackMaster poller (personal dashboard)"
        for n in missing[:MAX_NEW_PER_RUN]:
            if time.time() - t0 > TIME_BUDGET:
                break
            try:
                uri = _fetch(n, s)
            except Exception:
                uri = None
            if uri:
                cache[n] = uri
                got += 1
            else:
                failed.append(n)
    new["icons"] = {n: cache[n] for n in sorted(need) if n in cache}
    size = sum(len(v) for v in new["icons"].values())
    out(f"icons: {len(new['icons'])}/{len(need)} ready · {got} new · {len(failed)} not found · {size / 1024:.0f} KB")
    return {"ready": len(new["icons"]), "need": len(need), "new": got, "failed": failed[:20], "kb": round(size / 1024)}
