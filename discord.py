"""Read posts from Discord channels in YOUR server with your bot token.

Other servers' announcement channels reach your server through Discord's
Follow feature (guide §11). Never use a personal login token here.
"""
import os
import re

from ..util import get, result

API = "https://discord.com/api/v10"
LINK = re.compile(r"https?://\S+")


def fetch(cfg, prev):
    token = os.environ.get("DISCORD_BOT_TOKEN")
    feeds = [f for f in cfg.get("discord_feeds", []) if str(f.get("channel_id", "")).isdigit()]
    if not token or not feeds:
        return result(ok=None, error="not configured")
    old = {p["id"]: p for p in (prev.get("discord_posts") or [])}
    items = list(old.values())
    for f in feeds:
        msgs = get(f"{API}/channels/{f['channel_id']}/messages", params={"limit": 50},
                   headers={"Authorization": f"Bot {token}"}).json()
        kws = [k.lower() for k in f.get("keywords", [])]
        for m in msgs:
            if m["id"] in old or any(i["id"] == m["id"] for i in items):
                continue
            text = (m.get("content") or "")
            for e in m.get("embeds", []):  # followed announcements often arrive as embeds
                text += " " + " ".join(filter(None, [e.get("title"), e.get("description")]))
            items.append({"id": m["id"], "channel": f.get("name"), "tab": f.get("tab"),
                          "at": m.get("timestamp"), "text": text.strip()[:600],
                          "links": LINK.findall(text)[:5],
                          "hits": [k for k in kws if k in text.lower()]})
    items.sort(key=lambda p: p.get("at") or "", reverse=True)
    keep, per = [], {}
    for p in items:  # newest 50 per channel
        per[p["channel"]] = per.get(p["channel"], 0) + 1
        if per[p["channel"]] <= 50:
            keep.append(p)
    return result(keep)
