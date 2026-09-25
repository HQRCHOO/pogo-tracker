"""Field research from ScrapedDuck (Leek Duck) research.json."""
from ..util import get, html_text, result

URL = "https://raw.githubusercontent.com/bigfoott/ScrapedDuck/data/research.json"


def fetch(cfg, prev):
    items = []
    for r in get(URL).json():
        rewards = []
        for x in r.get("rewards") or []:
            cp = x.get("combatPower") or {}
            rewards.append({"name": x.get("name"), "shiny": bool(x.get("canBeShiny")), "cp": cp})
        items.append({"task": html_text(r.get("text") or ""), "category": r.get("type") or "",
                      "rewards": [w["name"] for w in rewards if w.get("name")], "reward_detail": rewards})
    return result(items)
