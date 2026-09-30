"""Pokémon icons, packed into dashboard.json as tiny WebP data URIs.

Style (v3.41): Pokémon Shuffle icons from nileplumb/PkmnShuffleMap (UICONS format, made for Pokémon GO maps
and Discord bots). ScrapedDuck's file names (pm83.fGALARIAN.icon.png) are translated to UICONS names
(83_f2338.png) using the form, Mega and costume tables in WatWowMap's masterfile. Anything the Shuffle pack
lacks falls back to the official GO art below, so no card goes blank.

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
STYLE = "uicons-shuffle-1"   # bump to re-fetch every icon after a style change
UICONS = "https://raw.githubusercontent.com/nileplumb/PkmnShuffleMap/master/UICONS/"
MASTER = "https://raw.githubusercontent.com/WatWowMap/Masterfile-Generator/master/master-latest-everything.json"
MEGA = {"MEGA": 1, "MEGA_X": 2, "MEGA_Y": 3, "PRIMAL": 4}
MAX_NEW_PER_RUN = 450
TIME_BUDGET = 150  # seconds


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


def _norm(x):
    return re.sub(r"[^A-Z0-9]+", "_", str(x).upper()).strip("_")


class Shuffle:
    """Translates ScrapedDuck icon names to UICONS names that exist in the Shuffle pack."""
    def __init__(self, session):
        self.index = set((session.get(UICONS + "index.json", timeout=30).json() or {}).get("pokemon") or [])
        mf = session.get(MASTER, timeout=60).json()
        self.mons = mf.get("pokemon") or {}
        self.fproto = {int(k): v.get("proto", "") for k, v in (mf.get("forms") or {}).items()}
        self.cost = {v.get("proto"): int(k) for k, v in (mf.get("costumes") or {}).items()}

    def _form_id(self, dex, tok):
        for fid, f in ((self.mons.get(str(dex)) or {}).get("forms") or {}).items():
            fid = int(fid)
            if fid and (self.fproto.get(fid, "").endswith("_" + tok) or _norm(f.get("name")) == tok):
                return fid
        return None

    def name_for(self, name):
        m = re.match(r"pm(\d+)(?:\.f([A-Z0-9_]+))?(?:\.c([A-Z0-9_]+))?(\.s)?\.icon\.png$", name or "")
        if not m:
            return None
        dex, f, c, sh = int(m.group(1)), m.group(2), m.group(3), "_s" if m.group(4) else ""
        dflt = (self.mons.get(str(dex)) or {}).get("defaultFormId")
        cp = f"_c{self.cost[c]}" if c and c in self.cost else ""
        if f in MEGA:
            fp = f"_e{MEGA[f]}"
        elif f:
            fid = self._form_id(dex, f)
            if not fid:
                return None                      # unknown form: never show a different Pokémon
            fp = f"_f{fid}"
        else:
            fp = ""
        cands = [f"{dex}{fp}{cp}{sh}", f"{dex}{fp}{sh}"]
        if not f or (dflt and fp == f"_f{dflt}"):  # the default form is the plain species icon
            cands += [f"{dex}{sh}"] + ([f"{dex}_f{dflt}{sh}"] if dflt else [])
        return next((x + ".png" for x in dict.fromkeys(cands) if x + ".png" in self.index), None)


def _encode(content):
    from PIL import Image
    im = Image.open(io.BytesIO(content)).convert("RGBA")
    box = im.getbbox()
    if box:
        im = im.crop(box)
    im.thumbnail((SIZE, SIZE))
    buf = io.BytesIO()
    im.save(buf, "WEBP", quality=60, method=6)   # Shuffle art is busier than GO icons; 60 keeps the total near 450 KB
    return "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode()


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
    same_style = prev.get("icons_style") == STYLE
    old = dict(prev.get("icons") or {})                  # previous style: only a stand-in until re-fetched
    cache = old if same_style else {}
    src = dict(prev.get("icons_src") or {}) if same_style else {}
    need = used(new)
    missing = sorted(n for n in need if n not in cache)
    got, failed, t0, shuffle = 0, [], time.time(), None
    if missing:
        s = requests.Session()
        s.headers["User-Agent"] = "TrackMaster poller (personal dashboard)"
        try:
            shuffle = Shuffle(s)
        except Exception as e:
            out(f"icons: Shuffle pack index unavailable ({type(e).__name__}); using GO art")
        for n in missing[:MAX_NEW_PER_RUN]:
            if time.time() - t0 > TIME_BUDGET:
                break
            uri = None
            try:
                u = shuffle.name_for(n) if shuffle else None
                if u:
                    r = s.get(UICONS + "pokemon/" + u, timeout=15)
                    if r.status_code == 200 and r.content:
                        uri, src[n] = _encode(r.content), "shuffle"
                if not uri:
                    uri = _fetch(n, s)
                    if uri:
                        src[n] = "go"
            except Exception:
                uri = None
            if uri:
                cache[n] = uri
                got += 1
            else:
                failed.append(n)
    icons = {}
    for n in sorted(need):
        if n in cache:
            icons[n] = cache[n]
        elif n in old:                                   # not re-fetched yet this run: keep the old icon
            icons[n] = old[n]
    new["icons"], new["icons_style"] = icons, STYLE
    new["icons_src"] = {n: src[n] for n in icons if n in src}
    size = sum(len(v) for v in icons.values())
    n_shuffle = sum(1 for n in icons if src.get(n) == "shuffle")
    out(f"icons: {len(icons)}/{len(need)} ready · {n_shuffle} Shuffle · {got} new · {len(failed)} not found · {size / 1024:.0f} KB")
    return {"ready": len(icons), "need": len(need), "shuffle": n_shuffle, "new": got, "failed": failed[:20], "kb": round(size / 1024)}
