"""Morning Slack digest (guide §10). Reads dashboard.json only; fetches nothing new."""
import datetime as dt
import os
import sys

import yaml

from . import alerts, drive
from .main import ROOT
from .timefmt import day, now_pt, short, wall
from .util import now_utc, parse_iso

FENCE = "`" * 3
W = 38  # max code-block line width for phones


def cut(s, n):
    s = str(s or "")
    return s if len(s) <= n else s[: n - 1] + "…"


STATUS = {"in_stock": "IN STOCK", "preorder_live": "PREORDER", "low": "LOW", "unavailable": "out",
          "not_configured": "not set up"}


def short_item(s):
    return str(s or "").replace("Pokémon GO Plus +", "GO Plus+")


def block(title, rows):
    return f"*{title}*\n{FENCE}\n" + "\n".join(rows) + f"\n{FENCE}" if rows else ""


def build(d, cfg):
    now = now_pt()
    types = set((cfg.get("pogo") or {}).get("event_types") or [])
    skip = {"go-battle-league", "pokemon-spotlight-hour"}
    ev = [(e, wall(e.get("start")), wall(e.get("end"))) for e in d.get("pogo_events", [])]
    ending = sorted([x for x in ev if x[1] and x[2] and x[1] <= now < x[2] and x[2] - now <= dt.timedelta(days=7)
                     and x[0].get("type") not in skip], key=lambda x: x[2])
    starting = sorted([x for x in ev if x[1] and now < x[1] <= now + dt.timedelta(days=7)
                       and x[0].get("type") not in skip], key=lambda x: x[1])
    stock = d.get("stock", [])
    live = [s for s in stock if s.get("status") in ("in_stock", "preorder_live", "low")]

    rel = []
    for key, label, field in (("tcg_releases", "Pkmn", "date"), ("onepiece_releases", "OP", "release_date"),
                              ("dragonball_releases", "DB", "release_date"), ("gundam_releases", "Gdm", "release_date")):
        for r in d.get(key, []):
            dd = day(r.get(field))
            if dd and now.date() <= dd <= now.date() + dt.timedelta(days=45):
                rel.append((dd, label, r))
    rel.sort(key=lambda x: x[0])

    # Headline: restock > ending within 48h > count ending this week
    ending48 = [x for x in ending if x[2] - now <= dt.timedelta(hours=48)]
    if live:
        pairs = []
        for s in live:
            p = f"{(s.get('status') or '').replace('_', ' ')} at {s.get('retailer')}"
            if p not in pairs:
                pairs.append(p)
        head = "🟢 GO Plus+: " + ", ".join(pairs[:3]) if all("GO Plus" in (s.get("item") or "") for s in live) \
            else "🟢 " + ", ".join(f"{s.get('item')} {p}" for s, p in zip(live, pairs))
    elif ending48:
        head = f"⏳ {ending48[0][0].get('name')} ends {short(ending48[0][2]).strip()}"
    else:
        head = f"{len(ending)} event{'s' if len(ending) != 1 else ''} end this week · {len(rel)} card drops in 45 days"

    def erow(x, when):
        prefix = short(when) + "  "
        return prefix + cut(x[0].get("name"), W - len(prefix))

    parts = [f"*⚡ TrackMaster · {now:%a %b %-d}*\n{head}",
             block("Ending this week", [erow(x, x[2]) for x in ending[:8]]),
             block("Starting this week", [erow(x, x[1]) for x in starting[:8]]),
             block("Restock watch", [cut(f"{cut(short_item(s.get('item')), 8):<8} {cut(s.get('retailer'), 9):<9} "
                                         f"{STATUS.get(s.get('status'), s.get('status') or ''):<10}"
                                         f"{'$%.2f' % s['price'] if isinstance(s.get('price'), (int, float)) else ''}", W).rstrip()
                                     for s in stock if not s.get("area")][:6]),
             block("Card releases", [cut(f"{('TODAY' if dd == now.date() else f'{dd:%b} {dd.day}'):<7} {lab} {r.get('name')}", W)
                                     for dd, lab, r in rel[:8]])]
    links = [f"<{cfg.get('dashboard_url')}|Open TrackMaster>"] if cfg.get("dashboard_url") else []
    for s in live:
        tag = f"<{s['url']}|{s.get('retailer')}>" if s.get("url") else None
        if tag and tag not in links and len(links) < 4:
            links.append(tag)
    if links:
        parts.append(" · ".join(links))
    src = d.get("sources") or {}
    ok = sum(1 for s in src.values() if s.get("ok") is True)
    gen = parse_iso(d.get("generated_at"))
    asof = wall(d.get("generated_at"))
    parts.append(f"_Sources {ok}/{len(src)} OK · data as of {short(asof).split()[-1] if asof else '—'} PT_")
    return "\n\n".join(p for p in parts if p), gen


def main():
    with open(os.path.join(ROOT, "config", "watchlist.yaml"), encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    hour = int((cfg.get("digest") or {}).get("hour_pt", 7))
    if now_pt().hour != hour and os.environ.get("FORCE") != "true":
        print(f"not {hour} AM PT; the other scheduled run will post")
        return 0
    d = drive.read_dashboard()
    text, gen = build(d, cfg)
    stale_h = float((cfg.get("digest") or {}).get("stale_hours", 6))
    if gen and (now_utc() - gen).total_seconds() > stale_h * 3600:
        text = f"⚠️ TrackMaster: the poller hasn't updated since {short(wall(d.get('generated_at'))).strip()} PT. Check the pogo-tracker Actions tab."
    print(text)
    n = alerts.slack(text)
    print(f"slack: {n} message(s) sent" if n else "slack: SLACK_WEBHOOK not set (printed only)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
