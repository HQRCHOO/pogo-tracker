"""Shared helpers: HTTP, time, date parsing, result shapes."""
import datetime as dt
import html as _html
import re

import requests

UA = "TrackMaster-poller/1.0 (personal dashboard)"
BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"], 1)}


def get(url, *, headers=None, params=None, browser=False, timeout=20):
    """GET with a timeout and a descriptive User-Agent. Raises on HTTP errors."""
    h = {"User-Agent": BROWSER_UA if browser else UA}
    h.update(headers or {})
    r = requests.get(url, headers=h, params=params, timeout=timeout)
    r.raise_for_status()
    return r


def now_utc():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def now_iso():
    return now_utc().isoformat().replace("+00:00", "Z")


def parse_iso(s):
    if not s:
        return None
    try:
        d = dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def parse_date(text):
    """'October 30, 2026' -> '2026-10-30'; 'October 2026' -> '2026-10'; else None."""
    if not text:
        return None
    t = str(text).strip()
    m = re.match(r"([A-Za-z]+)\.?\s+(\d{1,2}),?\s+(\d{4})", t)
    if m and m.group(1).lower() in MONTHS:
        return f"{int(m.group(3)):04d}-{MONTHS[m.group(1).lower()]:02d}-{int(m.group(2)):02d}"
    m = re.match(r"([A-Za-z]+)\.?\s+(\d{4})", t)
    if m and m.group(1).lower() in MONTHS:
        return f"{int(m.group(2)):04d}-{MONTHS[m.group(1).lower()]:02d}"
    if re.match(r"\d{4}-\d{2}(-\d{2})?$", t):
        return t
    return None


def html_text(html):
    """Flatten HTML to one line of text (scripts and styles removed)."""
    html = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html)
    html = re.sub(r"(?s)<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", _html.unescape(html)).strip()


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")[:60] or "item"


def result(items=None, ok=True, error=None, **extra):
    items = items or []
    out = {"ok": ok, "items": items, "error": error, "count": len(items)}
    out.update(extra)
    return out
