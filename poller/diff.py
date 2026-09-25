"""Change detection: compare the new dashboard with the previous one and build alert lines."""
import datetime as dt

from .timefmt import day, now_pt, short, wall

LIVE = {"in_stock": "IN STOCK", "preorder_live": "PREORDER LIVE", "low": "LOW STOCK"}
GAMES = [("tcg_releases", "Pokémon TCG", "date"), ("onepiece_releases", "One Piece", "release_date"),
         ("dragonball_releases", "Dragon Ball", "release_date"), ("gundam_releases", "Gundam", "release_date")]


def compute(prev, new, cfg):
    alerted = list(prev.get("alerted") or [])
    seen = set(alerted)
    urgent, lines, keys = [], [], []

    def once(key, line):
        if key not in seen:
            seen.add(key)
            keys.append(key)
            lines.append(line)

    # 1. Stock flips to live: always alert, first in the message.
    before = {s.get("id"): s.get("status") for s in prev.get("stock", [])}
    for s in new.get("stock", []):
        if s.get("status") in LIVE and before.get(s.get("id")) not in LIVE:
            where = s.get("retailer", "")
            if s.get("store"):
                where += f" ({s['store']}, {s.get('area') or ''})".replace(", )", ")")
            price = f" ${s['price']:.2f}" if isinstance(s.get("price"), (int, float)) else ""
            urgent.append(f"🟢 {LIVE[s['status']]}: {s.get('item')} at {where}{price} {s.get('url') or ''}".strip())

    # 2. Pokémon GO events.
    now = now_pt()
    types = set((cfg.get("pogo") or {}).get("event_types") or [])
    soon_h = float((cfg.get("pogo") or {}).get("ending_soon_hours", 48))
    old = {e.get("id"): e for e in prev.get("pogo_events", [])}
    for e in new.get("pogo_events", []):
        if types and e.get("type") not in types:
            continue
        s, t = wall(e.get("start")), wall(e.get("end"))
        if t and t < now:
            continue
        when = f"{short(s)} – {short(t)}" if s and t else "dates TBD"
        if old and e["id"] not in old:
            once(f"ann:{e['id']}", f"📣 Announced: {e.get('name')} ({when})")
        elif e["id"] in old and (old[e["id"]].get("start"), old[e["id"]].get("end")) != (e.get("start"), e.get("end")):
            once(f"chg:{e['id']}:{e.get('start')}:{e.get('end')}", f"🔁 Changed: {e.get('name')} now {when}")
        if s and s.date() == now.date() and s >= now - dt.timedelta(hours=1):
            once(f"start:{e['id']}", f"▶️ Starting today: {e.get('name')} at {short(s).split()[-1]}")
        if s and t and s <= now < t and (t - now) <= dt.timedelta(hours=soon_h) and (t - s) >= dt.timedelta(days=3):
            once(f"end:{e['id']}", f"⏳ Ending soon: {e.get('name')} ends {short(t)}")

    # 3. Card releases coming up.
    ahead = int((cfg.get("card_games") or {}).get("alert_days_before", 7))
    today = now.date()
    groups = {}
    for key, label, field in GAMES:
        for r in new.get(key, []):
            d = day(r.get(field))
            k = f"rel:{key}:{r.get('id')}:{d}"
            if d and today <= d <= today + dt.timedelta(days=ahead) and k not in seen:
                seen.add(k)
                keys.append(k)
                tag = "" if r.get("confirmed", True) else " (date unconfirmed)"
                groups.setdefault((d, label), []).append(f"{r.get('name')}{tag}")
    for (d, label), names in sorted(groups.items()):
        more = f" (+{len(names) - 3} more)" if len(names) > 3 else ""
        lines.append(f"🃏 Release soon, {d:%a %b %-d}: {label}: " + ", ".join(names[:3]) + more)

    # 4. Sources failing 3 runs in a row (one alert per outage).
    for name, st in (new.get("sources") or {}).items():
        if st.get("ok") is False and st.get("fails", 0) >= 3:
            once(f"down:{name}:{st.get('last_success')}", f"⚠️ Source down: {name} ({st.get('error')})")

    return urgent + lines, (alerted + keys)[-800:]
