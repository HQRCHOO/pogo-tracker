"""Egg pools from ScrapedDuck (Leek Duck) eggs.json."""
from ..util import get, result
from ..icons import icon_file

URL = "https://raw.githubusercontent.com/bigfoott/ScrapedDuck/data/eggs.json"


def fetch(cfg, prev):
    items = [{"name": e.get("name"), "km": e.get("eggType"), "adventure_sync": bool(e.get("isAdventureSync")),
              "shiny": bool(e.get("canBeShiny")), "cp": e.get("combatPower") or {},
              "rarity": e.get("rarity"), "regional": bool(e.get("isRegional")), "gift": bool(e.get("isGiftExchange")),
              "icon": icon_file(e.get("image"))}
             for e in get(URL).json()]
    return result(items)
