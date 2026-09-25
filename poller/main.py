"""TrackMaster poller: fetch due sources, merge into dashboard.json, alert on changes.

Usage:
  python -m poller.main               # normal scheduled run
  python -m poller.main --force       # run every source now
  python -m poller.main --dry-run     # fetch and print, write nothing, send nothing
  python -m poller.main --test-alert  # send one Discord test message and exit
"""
import argparse
import copy
import importlib
import os
import sys

import yaml

from . import alerts, calendar, diff, drive
from .util import now_iso, now_utc, parse_iso, result

HEARTBEAT_HOURS = 2  # rewrite dashboard.json at least this often even if nothing changed
VOLATILE = ("generated_at", "last_run", "last_success", "checked_at", "fails")  # timestamps ignored when deciding "changed"


def signature(d):
    """The dashboard with per-run timestamps removed, for change detection."""
    def strip(node):
        if isinstance(node, dict):
            return {k: strip(v) for k, v in node.items() if k not in VOLATILE}
        if isinstance(node, list):
            return [strip(v) for v in node]
        return node
    import json as _json
    return _json.dumps(strip(d), sort_keys=True, ensure_ascii=False)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# source name -> (cadence group, dashboard key)
SOURCES = {
    "scrapedduck": ("pogo_events", "pogo_events"),
    "sdraids": ("raids", "raids"),
    "sdresearch": ("raids", "research"),
    "sdeggs": ("raids", "eggs"),
    "pokemonsets": ("card_games", "tcg_releases"),
    "gcg": ("card_games", "gundam_releases"),
    "onepiece": ("card_games", "onepiece_releases"),
    "dragonball": ("card_games", "dragonball_releases"),
    "bestbuy": ("stock", "stock"),
    "target": ("stock", "stock"),
    "gamestop": ("stock", "stock"),
    "discord": ("discord", "discord_posts"),
}
STOCK_SOURCES = ("bestbuy", "target", "gamestop")
LINK_RULES = {"pogo_events": "https://leekduck.com/events/{id}/",
              "gundam_releases": "https://www.gundam-gcg.com/en/products/{id}.html"}


def load_cfg():
    with open(os.path.join(ROOT, "config", "watchlist.yaml"), encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def due(state, group, cfg, force):
    if force:
        return True
    last = parse_iso((state or {}).get("last_run"))
    mins = float((cfg.get("cadence_minutes") or {}).get(group, 15))
    return last is None or (now_utc() - last).total_seconds() >= (mins - 1) * 60


def merge_manual(scraped, manual):
    """Scraped rows win on dates/prices; manual rows fill gaps and add unlisted sets."""
    by_id = {r["id"]: dict(r) for r in scraped if r.get("id")}
    for m in manual or []:
        m = dict(m)
        m.setdefault("id", m.get("name", "item").lower().replace(" ", "-"))
        if m.get("date") and not m.get("release_date"):
            m["release_date"] = str(m.pop("date"))
        if m.get("release_date") is not None:
            m["release_date"] = str(m["release_date"])
        if m["id"] in by_id:
            got, want = str(by_id[m["id"]].get("release_date") or ""), str(m.get("release_date") or "")
            if len(got) == 7 and len(want) == 10 and want.startswith(got):
                by_id[m["id"]]["release_date"] = want  # page shows the month; manual has the day
            for k, v in m.items():
                if by_id[m["id"]].get(k) in (None, "") and v not in (None, ""):
                    by_id[m["id"]][k] = v
        else:
            m.setdefault("source", "manual")
            by_id[m["id"]] = m
    return list(by_id.values())


RETAILER = {"bestbuy": "Best Buy", "target": "Target", "gamestop": "GameStop"}


def placeholders(cfg, results):
    """A 'not configured' row for each watched item whose retailer isn't set up yet."""
    rows = []
    for w in cfg.get("stock", []):
        r = w.get("retailer")
        res = results.get(r)
        if res and res.get("ok") is None:
            item = w.get("item") or "Pokémon GO Plus +"
            rows.append({"id": f"{r}-setup-{item}".lower().replace(" ", "-"), "item": item,
                         "retailer": RETAILER.get(r, r), "area": None, "store": None,
                         "status": "not_configured", "price": None, "url": None,
                         "note": f"{res.get('error')}: add IDs/keys (guide §12)", "src": r})
    return rows


def run(only=None, force=False, dry=False, out=print):
    cfg = load_cfg()
    prev = drive.read_dashboard() or {}
    new = copy.deepcopy(prev)
    old_states = new.get("sources") or {}
    states = new["sources"] = {k: old_states[k] for k in SOURCES if k in old_states}  # drop retired names
    results = {}
    out(f"[{now_iso()}] run start · force={force} dry={dry}")

    for name, (group, key) in SOURCES.items():
        if only and name not in only:
            continue
        st = states.setdefault(name, {"ok": None, "fails": 0})
        if not due(st, group, cfg, force):
            continue
        try:
            res = importlib.import_module(f"poller.sources.{name}").fetch(cfg, prev)
        except Exception as e:  # one broken source never stops the others
            res = result(ok=False, error=f"{type(e).__name__}: {str(e)[:160]}")
        if res["ok"] and name in ("onepiece", "dragonball") and not res["items"]:
            res = result(ok=False, error="page layout changed: 0 products matched")
        results[name] = res
        st["last_run"] = now_iso()
        if res["ok"]:
            st.update(ok=True, last_success=now_iso(), fails=0, error=None, count=res["count"])
        elif res["ok"] is None:
            st.update(ok=None, fails=0, error=res["error"], count=0)
        else:
            st.update(ok=False, fails=int(st.get("fails", 0)) + 1, error=res["error"])
        flag = {True: "ok  ", None: "skip", False: "FAIL"}[res["ok"]]
        out(f"{name:<14} {flag} {res.get('count', 0):>3} items   {res.get('error') or ''}".rstrip())

        if res["ok"] and name not in STOCK_SOURCES and name not in ("onepiece", "dragonball", "pokemonsets"):
            new[key] = res["items"]
        if name == "pokemonsets" and res.get("tcgdex_cache"):
            new["tcgdex_cache"] = res["tcgdex_cache"]

    # Card games: scraped (if it worked) + manual lists from the watchlist.
    games = cfg.get("card_games") or {}
    for name, key, gkey in (("onepiece", "onepiece_releases", "onepiece"), ("dragonball", "dragonball_releases", "dragonball")):
        res = results.get(name)
        base = res["items"] if res and res["ok"] else prev.get(key, [])
        new[key] = merge_manual(base, (games.get(gkey) or {}).get("manual"))
    manual_pk = [dict(r, id=r.get("id") or r["name"].lower().replace(" ", "-").replace(":", ""),
                      date=str(r.get("date")) if r.get("date") else None, source="manual")
                 for r in (games.get("pokemon") or [])]
    pk_res = results.get("pokemonsets")
    api_pk = pk_res["items"] if pk_res and pk_res["ok"] else [r for r in prev.get("tcg_releases", []) if r.get("source") != "manual"]
    # manual rows win by date match (same set), otherwise both are kept
    api_dates = {}
    for r in api_pk:
        api_dates.setdefault(r.get("date"), []).append(r)
    merged, used = [], set()
    for mrow in manual_pk:
        hit = next((h for h in api_dates.get(mrow.get("date")) or [] if h["id"] not in used), None)
        mrow.setdefault("category", "boosters")
        if hit:
            used.add(hit["id"])
            keep_id = mrow["id"]
            over = {k: v for k, v in mrow.items() if v not in (None, "")}
            mrow = dict(hit); mrow.update(over); mrow["id"] = keep_id; mrow["api_id"] = hit["id"]
        merged.append(mrow)
    new["tcg_releases"] = merged + [r for r in api_pk if r["id"] not in used]

    # Stock: replace rows from sources that ran; keep the rest from last time.
    if any(s in results for s in STOCK_SOURCES):
        ran = [s for s in STOCK_SOURCES if s in results]
        keep = [r for r in prev.get("stock", []) if r.get("src") not in ran and r.get("src")]
        fresh = []
        for s in ran:
            res = results[s]
            if res["ok"]:
                fresh += [dict(r, src=s, checked_at=now_iso()) for r in res["items"]]
            elif res["ok"] is False:  # keep last known rows for a failing retailer
                fresh += [r for r in prev.get("stock", []) if r.get("src") == s
                          or (not r.get("src") and r.get("retailer") == RETAILER.get(s))]
        new["stock"] = keep + fresh + placeholders(cfg, results)

    new.update(schema=2, generated_at=now_iso(), generated_by="poller",
               location=cfg.get("location") or new.get("location"), link_rules=LINK_RULES)
    gh = str(cfg.get("github_user") or "")
    new["calendar_url"] = (f"https://raw.githubusercontent.com/{gh}/pogo-tracker/main/calendar.ics"
                           if gh and not gh.startswith("<") else None)
    # stock_log: every status flip, for the Log tab and restock predictions (last 500)
    before = {r.get("id"): r for r in prev.get("stock", [])}
    flips = []
    for r in new.get("stock", []):
        was = (before.get(r.get("id")) or {}).get("status")
        if was is not None and was != r.get("status") and r.get("status") != "not_configured":
            flips.append({"at": now_iso(), "item": r.get("item"), "retailer": r.get("retailer"), "store": r.get("store"),
                          "area": r.get("area"), "from": was, "to": r.get("status"), "price": r.get("price"), "url": r.get("url")})
    new["stock_log"] = (flips + list(prev.get("stock_log") or []))[:500]
    lines, new["alerted"] = diff.compute(prev, new, cfg)
    new["alerts_log"] = ([{"at": now_iso(), "line": ln} for ln in lines] + list(prev.get("alerts_log") or []))[:30]
    out(f"diff: {len(lines)} alert line(s)")
    for line in lines:
        out("  " + line)
    if dry:
        out("dry run: nothing written, nothing sent")
        return new, lines
    prev_gen = parse_iso(prev.get("generated_at"))
    stale = prev_gen is None or (now_utc() - prev_gen).total_seconds() >= HEARTBEAT_HOURS * 3600
    if signature(prev) == signature(new) and not stale and not lines:
        out("drive: unchanged, not written (heartbeat in "
            f"{HEARTBEAT_HOURS * 3600 - (now_utc() - prev_gen).total_seconds():.0f}s)")
        return new, lines
    size = drive.write_dashboard(new)
    out(f"drive: wrote {size / 1024:.1f} KB" + (" (heartbeat)" if stale and signature(prev) == signature(new) else ""))
    changed, n_ev = calendar.write(new, cfg, ROOT)
    out(f"calendar: {n_ev} entries, {'updated' if changed else 'unchanged'}")
    sent = alerts.discord(lines)
    out(f"discord: {sent} message(s) sent")
    return new, lines


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--test-alert", action="store_true")
    ap.add_argument("--only", nargs="*")
    a = ap.parse_args(argv)
    if a.test_alert:
        n = alerts.discord(["✅ TrackMaster test alert: the Discord webhook works."])
        print(f"discord: {n} test message(s) sent" if n else "discord: DISCORD_WEBHOOK not set")
        return 0 if n else 1
    run(only=a.only, force=a.force or os.environ.get("FORCE") == "true", dry=a.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
