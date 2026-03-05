#!/usr/bin/env python3
"""Daily Pokémon updater — runs inside HA container via shell_command.

Uses only stdlib (urllib). Calls HA API via supervisor or localhost.
"""

import json
import os
import sys
import traceback
import urllib.request
from datetime import date

LOG_FILE = "/config/scripts/pokemon_debug.log"

# In HA OS, shell_command runs inside the core container.
# SUPERVISOR_TOKEN is available; API via http://supervisor/core
# Fallback: long-lived token + localhost
HA_TOKEN = os.environ.get("HA_TOKEN", "")
HA_URL = os.environ.get("HA_URL", "http://localhost:8123")

TYPE_CN = {
    "Normal": "一般", "Fire": "火", "Water": "水", "Electric": "电",
    "Grass": "草", "Ice": "冰", "Fighting": "格斗", "Poison": "毒",
    "Ground": "地面", "Flying": "飞行", "Psychic": "超能力", "Bug": "虫",
    "Rock": "岩石", "Ghost": "幽灵", "Dragon": "龙", "Dark": "恶",
    "Steel": "钢", "Fairy": "妖精",
}


def log(msg):
    try:
        with open(LOG_FILE, "a") as f:
            f.write(msg + "\n")
    except Exception:
        pass
    print(msg, file=sys.stderr)


def fetch_json(url, token=None):
    headers = {"User-Agent": "HA-Pokemon/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def ha_set_input_text(entity_id, value):
    data = json.dumps({"entity_id": entity_id, "value": str(value)[:255]}).encode()
    req = urllib.request.Request(
        f"{HA_URL}/api/services/input_text/set_value",
        data=data,
        headers={
            "Authorization": f"Bearer {HA_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    urllib.request.urlopen(req, timeout=10)


def get_today_pokemon_id():
    today = date.today()
    seed = today.year * 366 + today.timetuple().tm_yday
    return (seed * 997) % 1025 + 1


def main():
    log(f"--- start: HA_URL={HA_URL}")

    poke_id = get_today_pokemon_id()
    log(f"pokemon id: {poke_id}")

    pokemon = fetch_json(f"https://pokeapi.co/api/v2/pokemon/{poke_id}")
    log("fetched pokemon data")

    name_en = pokemon["name"].replace("-", " ").title()
    types_str = " / ".join(TYPE_CN.get(t["type"]["name"].title(), t["type"]["name"].title()) for t in pokemon["types"])
    height = pokemon["height"] / 10
    weight = pokemon["weight"] / 10
    sprite = pokemon["sprites"]["other"]["official-artwork"]["front_default"] or pokemon["sprites"]["front_default"] or ""

    stats = {}
    total = 0
    for s in pokemon["stats"]:
        stats[s["stat"]["name"]] = s["base_stat"]
        total += s["base_stat"]

    name_cn = name_en
    genera_cn = ""
    flavor_cn = ""
    try:
        species = fetch_json(f"https://pokeapi.co/api/v2/pokemon-species/{poke_id}")
        names = {n["language"]["name"]: n["name"] for n in species.get("names", [])}
        for lang in ("zh-Hans", "zh-Hant", "ja-Hrkt", "ja"):
            if lang in names:
                name_cn = names[lang]
                break
        genera = {g["language"]["name"]: g["genus"] for g in species.get("genera", [])}
        for lang in ("zh-Hans", "zh-Hant", "ja-Hrkt", "ja"):
            if lang in genera:
                genera_cn = genera[lang]
                break
        flavors = {f["language"]["name"]: f["flavor_text"] for f in species.get("flavor_text_entries", [])}
        for lang in ("zh-Hans", "zh-Hant", "ja-Hrkt", "ja", "en"):
            if lang in flavors:
                flavor_cn = flavors[lang].replace("\n", " ").replace("\f", " ")
                break
    except Exception as e:
        log(f"species fetch failed: {e}")

    pokemon_data = json.dumps({
        "id": poke_id, "cn": name_cn, "en": name_en, "g": genera_cn,
        "t": types_str, "h": f"{height}m", "w": f"{weight}kg",
        "hp": stats.get("hp", 0), "atk": stats.get("attack", 0),
        "def": stats.get("defense", 0), "spa": stats.get("special-attack", 0),
        "spd": stats.get("special-defense", 0), "spe": stats.get("speed", 0),
        "tot": total,
    }, ensure_ascii=False)

    log(f"writing to HA: {HA_URL}/api/services/input_text/set_value")
    ha_set_input_text("input_text.pokemon_data", pokemon_data)
    ha_set_input_text("input_text.pokemon_sprite", sprite)
    ha_set_input_text("input_text.pokemon_flavor", flavor_cn)
    log(f"done: #{poke_id} {name_cn}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log(traceback.format_exc())
        sys.exit(1)
