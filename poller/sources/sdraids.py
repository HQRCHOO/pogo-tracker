"""Current raid bosses from ScrapedDuck (Leek Duck) raids.json."""
import re

from ..util import get, result

URL = "https://raw.githubusercontent.com/bigfoott/ScrapedDuck/data/raids.json"


def tier_of(label):
    t = str(label or "")
    if re.search(r"mega", t, re.I):
        return "Mega"
    m = re.match(r"\s*(\d+)", t)
    return m.group(1) if m else t


def fetch(cfg, prev):
    items = []
    for r in get(URL).json():
        cp = r.get("combatPower") or {}
        items.append({"name": r.get("name"), "tier": tier_of(r.get("tier")), "tier_label": r.get("tier"),
                      "kind": "raid", "shiny": bool(r.get("canBeShiny")),
                      "types": [t.get("name") for t in (r.get("types") or []) if isinstance(t, dict)],
                      "cp": (cp.get("normal") or {}), "cp_boosted": (cp.get("boosted") or {})})
    return result(items)
