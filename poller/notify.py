"""Slack pings when stock changes.

Compares this run's stock rows with the last known status of each row:
  - change to in stock / preorder / low  → a ping (first-hand readings are already double-checked
    by the sources; tracker readings are labeled "reported by HotStock — verify")
  - change back to sold out              → a quiet message (optional)
Readings of "unknown" (blocked page) never count as a change.
"""
from . import alerts

LIVE = {"in_stock", "preorder_live", "low"}
WORD = {"in_stock": "IN STOCK", "preorder_live": "PREORDER OPEN", "low": "LOW STOCK"}


def carry_last_known(prev_rows, new_rows):
    prev = {r.get("id"): r for r in prev_rows or []}
    for r in new_rows:
        p = prev.get(r.get("id")) or {}
        known = p.get("last_known") or (p.get("status") if p.get("status") not in (None, "unknown", "not_configured") else None)
        r["_prev_known"] = known
        if r.get("status") not in ("unknown", "not_configured", None):
            r["last_known"] = r["status"]
        elif known:
            r["last_known"] = known
    return new_rows


def changes(new_rows):
    live, gone = [], []
    for r in new_rows:
        st, was = r.get("status"), r.pop("_prev_known", None)
        if st in LIVE and was not in LIVE:
            live.append(r)
        elif st == "unavailable" and was in LIVE:
            gone.append(r)
    return live, gone


def where(r):
    return r.get("retailer", "?") + (f" {r['store']}" if r.get("store") else "") + (f" ({r['area']})" if r.get("area") else "")


def message(live, gone, cfg):
    n = (cfg.get("notify") or {})
    lines = []
    first = [r for r in live if r.get("src") != "trackers"]
    if first and n.get("mention_on_first_hand"):
        lines.append(n["mention_on_first_hand"])
    for r in live:
        price = f" ${r['price']:.2f}" if isinstance(r.get("price"), (int, float)) else ""
        how = "reported by " + r["via"] + " — verify on the retailer page" if r.get("via") else "confirmed on a second check"
        lines.append(f"🟢 *{WORD.get(r['status'], r['status'])}*: {r.get('item')} at {where(r)}{price} ({how})\n{r.get('url') or ''}")
    if gone and n.get("sold_out_messages", True):
        lines.append("⚪ Back to sold out: " + ", ".join(f"{r.get('item')} at {where(r)}" for r in gone))
    return "\n".join(lines).strip()


def run(prev_rows, new_rows, cfg, dry=False):
    carry_last_known(prev_rows, new_rows)
    live, gone = changes(new_rows)
    text = message(live, gone, cfg) if (live or gone) else ""
    sent = 0
    if text and not dry and (cfg.get("notify") or {}).get("slack", True):
        try:
            sent = alerts.slack(text)
        except Exception:
            sent = 0
    return {"live": len(live), "gone": len(gone), "text": text, "sent": sent}
