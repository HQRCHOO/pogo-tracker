"""Raid difficulty from pokemon-go-api (github.com/pokemon-go-api/pokemon-go-api, published on GitHub Pages).

For each current boss: estimated trainers needed with level-20, level-30 and level-40 counters
(the api's easy / normal / hard battle results), plus the boss's normal and shiny icon file names,
which match ScrapedDuck's names so bosses line up exactly.
"""
from ..icons import icon_file
from ..util import get, result

URL = "https://raw.githubusercontent.com/pokemon-go-api/pokemon-go-api/gh-pages/api/raidboss.json"


def fetch(cfg, prev):
    js = get(URL).json()
    items = []
    for level, bosses in (js.get("currentList") or {}).items():
        for b in bosses or []:
            br = b.get("battleResult") or {}
            est = {k: {"trainers": round(float(v.get("totalEstimator")), 2), "level": v.get("pokemonLevel"),
                       "friendship": v.get("friendshipLevel")}
                   for k, v in br.items() if isinstance(v, dict) and v.get("totalEstimator") is not None}
            assets = b.get("assets") or {}
            items.append({"level": level, "shadow": level.startswith("shadow"), "name": (b.get("names") or {}).get("English"),
                          "icon": icon_file(assets.get("image")), "shiny_icon": icon_file(assets.get("shinyImage")),
                          "estimates": est})
    return result(items)
