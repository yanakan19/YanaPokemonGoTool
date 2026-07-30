"""Build data/species.json and the CPM table from the PokeMiners game master.

Run once, or whenever the game master updates. Never fetch or ship the
~100MB source file at request time -- this script consumes it and emits a
slim (~200KB) local JSON that the rest of the skill reads.

Usage: python3 build_data.py [path/to/latest.json]
       (downloads the game master if no path given)
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

GAME_MASTER_URL = "https://raw.githubusercontent.com/PokeMiners/game_masters/master/latest/latest.json"
OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "species.json"


def load_game_master(path=None):
    if path:
        with open(path) as f:
            return json.load(f)
    with urllib.request.urlopen(GAME_MASTER_URL, timeout=120) as resp:
        return json.load(resp)


def species_key(pokemon_id, form=None):
    name = pokemon_id.lower()
    if form and form.lower() != pokemon_id.lower():
        return f"{name}_{form.lower()}"
    return name


def extract_species(game_master):
    species = {}
    for item in game_master:
        data = item.get("data", {})
        settings = data.get("pokemonSettings")
        if not settings:
            continue
        stats = settings.get("stats")
        if not stats:
            continue
        pokemon_id = settings.get("pokemonId")
        if not pokemon_id:
            continue
        form = settings.get("form")
        key = species_key(pokemon_id, form)
        species[key] = {
            "atk": stats["baseAttack"],
            "def": stats["baseDefense"],
            "sta": stats["baseStamina"],
        }
        # Also index the bare species name to the first (default) form seen,
        # so lookups without a form still resolve.
        base_key = pokemon_id.lower()
        if base_key not in species:
            species[base_key] = species[key]
    return species


def extract_cpm(game_master):
    for item in game_master:
        data = item.get("data", {})
        if data.get("templateId") == "PLAYER_LEVEL_SETTINGS":
            cpm_list = data["playerLevel"]["cpMultiplier"]
            # cpm_list[0] is level 1, cpm_list[i] is level i+1
            return {str(i + 1): round(v, 8) for i, v in enumerate(cpm_list)}
    raise RuntimeError("PLAYER_LEVEL_SETTINGS not found in game master")


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else None
    gm = load_game_master(path)
    species = extract_species(gm)
    cpm = extract_cpm(gm)

    assert species["metagross"] == {"atk": 257, "def": 228, "sta": 190}, species.get("metagross")
    assert species["slaking"] == {"atk": 290, "def": 166, "sta": 284}, species.get("slaking")

    out = {"species": species, "cpm": cpm}
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(out, f, separators=(",", ":"))
    print(f"Wrote {len(species)} species and {len(cpm)} CPM levels to {OUT_PATH}")


if __name__ == "__main__":
    main()
