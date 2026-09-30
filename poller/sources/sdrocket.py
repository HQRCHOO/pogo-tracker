"""Team GO Rocket lineups from ScrapedDuck (Leek Duck) rocketLineups.json:
leaders (Giovanni, Cliff, Arlo, Sierra) and grunts, with the possible Pokémon in each of the three slots."""
from ..icons import icon_file
from ..util import get, result

URL = "https://raw.githubusercontent.com/bigfoott/ScrapedDuck/data/rocketLineups.json"


def fetch(cfg, prev):
    items = []
    for r in get(URL).json():
        slots = []
        for key in ("firstPokemon", "secondPokemon", "thirdPokemon"):
            slots.append([{"name": p.get("name"), "types": p.get("types") or [], "encounter": bool(p.get("isEncounter")),
                           "shiny": bool(p.get("canBeShiny")), "icon": icon_file(p.get("image"))}
                          for p in (r.get(key) or []) if isinstance(p, dict)])
        title = r.get("title") or ""
        kind = "boss" if "Boss" in title else ("leader" if "Leader" in title else "grunt")
        items.append({"name": r.get("name"), "title": title, "type": r.get("type") or "", "kind": kind, "slots": slots})
    return result(items)
