#!/usr/bin/env python3
"""CLI entry point: scan.py <image> [--source wild|raid|research|egg|rocket] [--boosted]

Classifies the screenshot, then dispatches to the profile or encounter reader,
and prints a compact result line plus detail. Honesty over coverage: wild
encounters never get a single IV%; fixed-level encounters get a range or a
"100% guaranteed" call when the CP matches the unique hundo CP.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "species.json"

# §1 / §5.3 encounter source rules.
SOURCE_RULES = {
    "wild": {"levels": (1, 30), "floor": (0, 0, 0), "fixed_level": False},
    "raid": {"levels": (20, 20), "floor": (10, 10, 10), "fixed_level": True},
    "egg": {"levels": (20, 20), "floor": (10, 10, 10), "fixed_level": True},
    "research": {"levels": (15, 15), "floor": (10, 10, 10), "fixed_level": True},
    "rocket": {"levels": (8, 8), "floor": (0, 0, 0), "fixed_level": True},
}


def _levels_in_range(lo, hi):
    import solver as S
    return [lvl for lvl in S.ALL_LEVELS if lo <= lvl <= hi and lvl == int(lvl)]


def _load_species():
    with open(DATA_PATH) as f:
        return json.load(f)["species"]


def _species_stats(species_db, name):
    key = name.lower().replace(" ", "_")
    if key not in species_db:
        raise KeyError(f"unknown species '{name}' -- not found in data/species.json")
    return species_db[key]


BAR_MISMATCH_MAX_DISTANCE = 6  # sum of |delta| across the 3 stats we'll still trust


def scan_profile(image_path):
    import read_profile
    import solver as S

    result = read_profile.read_profile_screenshot(image_path)
    species_db = _load_species()
    stats = _species_stats(species_db, result["species"])

    combos_cp = S.reverse_solve(
        stats["atk"], stats["def"], stats["sta"], result["cp"],
        iv_floor=(0, 0, 0),
    )
    if not combos_cp:
        raise read_profile.ReadError(
            f"no IV combo at any level reproduces CP {result['cp']} for "
            f"{result['species']} -- check the species (forms share the caption "
            "name but not base stats) or re-check the CP digits"
        )

    # HP OCR is a second independent digit-only read (like CP) -- when it
    # parsed at all, prefer the CP+HP-consistent subset over CP alone, since
    # that pins down the stamina IV exactly rather than leaving it to guesswork.
    combos_hp = None
    if result["hp"] is not None:
        combos_hp = S.reverse_solve(
            stats["atk"], stats["def"], stats["sta"], result["cp"],
            iv_floor=(0, 0, 0), hp=result["hp"],
        )
    combos = combos_hp if combos_hp else combos_cp

    bar_ivs = (result["iv_a"], result["iv_d"], result["iv_s"])
    exact = [c for c in combos if c[1:] == bar_ivs]

    note = None
    if len(exact) == 1:
        level, iv_a, iv_d, iv_s = exact[0]
    elif len(exact) > 1:
        raise read_profile.ReadError(
            f"{len(exact)} levels all reproduce CP {result['cp']} with IVs {bar_ivs} -- "
            "ambiguous, please retake the screenshot"
        )
    else:
        # The bar-measured IVs don't land on any level that reproduces this
        # CP (and HP, if OCR'd) exactly. CP/HP come from plain digit OCR
        # (reliable once it parses at all), while bar pixel-reading is the
        # noisier signal -- so fall back to the CP(+HP)-consistent combo
        # closest to what the bars measured, rather than hard-failing on
        # what's usually a 1-2-point misread of a single bar (e.g. a
        # background/lighting quirk making a partial fill look fuller than
        # it is).
        def distance(c):
            _, a, d, s = c
            return abs(a - bar_ivs[0]) + abs(d - bar_ivs[1]) + abs(s - bar_ivs[2])

        best = min(combos, key=distance)
        if distance(best) > BAR_MISMATCH_MAX_DISTANCE:
            raise read_profile.ReadError(
                f"bar-measured IVs {bar_ivs} don't match any level's CP/HP for "
                f"CP {result['cp']}, and the closest consistent combo "
                f"{best[1:]} is too far off to trust -- re-check the screenshot "
                "(species/form mismatch, or appraisal bars not fully loaded)"
            )
        level, iv_a, iv_d, iv_s = best
        note = (
            f"bar reading {bar_ivs} didn't match any CP{'/HP' if combos_hp else ''}"
            f"-consistent level; using the closest consistent combo "
            f"{(iv_a, iv_d, iv_s)} instead (one bar was likely misread, or "
            "this is a form the caption can't distinguish -- e.g. Origin/Altered Forme)"
        )

    iv_pct = S.iv_percent(iv_a, iv_d, iv_s)

    check_cp, check_hp = S.forward_solve(
        stats["atk"], stats["def"], stats["sta"], iv_a, iv_d, iv_s, level,
    )
    assert check_cp == result["cp"], (check_cp, result["cp"])

    stars = S.star_rating(iv_pct)
    summary = (
        f"{result['species']} · L{int(level) if level == int(level) else level} · "
        f"{iv_a}/{iv_d}/{iv_s} · {iv_pct}% "
        f"({stars}★) · CP {result['cp']}"
    )
    if note:
        summary += f"\nNote: {note}"
    return {
        "mode": "profile",
        "species": result["species"],
        "level": level,
        "iv_a": iv_a,
        "iv_d": iv_d,
        "iv_s": iv_s,
        "iv_pct": iv_pct,
        "cp": result["cp"],
        "note": note,
        "hp_ocr": result["hp"],
        "hp_check": check_hp,
        "summary": summary,
    }


def scan_encounter(image_path, source):
    import read_encounter
    import solver as S

    if source not in SOURCE_RULES:
        raise ValueError(f"unknown --source '{source}', expected one of {list(SOURCE_RULES)}")
    rule = SOURCE_RULES[source]

    result = read_encounter.read_encounter_screenshot(image_path)
    species_db = _load_species()
    stats = _species_stats(species_db, result["species"])

    lo, hi = rule["levels"]
    if result["weather_boost"] and source == "wild":
        lo, hi = 6, 35
        floor = (4, 4, 4)
    else:
        floor = rule["floor"]
    levels = _levels_in_range(lo, hi)

    combos = S.reverse_solve(stats["atk"], stats["def"], stats["sta"], result["cp"],
                              levels=levels, iv_floor=floor)

    if not rule["fixed_level"]:
        if not combos:
            raise read_encounter.ReadError("no (level, IV) combo reproduces this CP -- re-check the crop")
        pcts = sorted(S.iv_percent(a, d, s) for _, a, d, s in combos)
        summary = (
            f"{result['species']} · CP {result['cp']} · wild encounter -- "
            f"CP alone cannot determine IV. Candidate levels {min(c[0] for c in combos):.0f}"
            f"-{max(c[0] for c in combos):.0f}, IV% {pcts[0]}-{pcts[-1]}. "
            f"Catch it and re-scan the profile screen (with appraisal open) for the exact IVs."
        )
        return {
            "mode": "encounter",
            "species": result["species"],
            "cp": result["cp"],
            "source": source,
            "exact": False,
            "iv_pct_range": (pcts[0], pcts[-1]),
            "level_range": (min(c[0] for c in combos), max(c[0] for c in combos)),
            "weather_boost": result["weather_boost"],
            "summary": summary,
        }

    # Fixed level: check for the guaranteed-hundo case first.
    level = levels[0]
    if S.is_guaranteed_hundo(stats["atk"], stats["def"], stats["sta"], level, result["cp"]):
        summary = f"{result['species']} · CP {result['cp']} · L{int(level)} · 100% guaranteed (15/15/15)"
        return {
            "mode": "encounter",
            "species": result["species"],
            "cp": result["cp"],
            "source": source,
            "exact": True,
            "iv_pct": 100,
            "level": level,
            "summary": summary,
        }

    if not combos:
        raise read_encounter.ReadError("no IV combo reproduces this CP at the fixed level for this source")
    pcts = sorted(S.iv_percent(a, d, s) for _, a, d, s in combos)
    summary = (
        f"{result['species']} · CP {result['cp']} · L{int(level)} · "
        f"IV% {pcts[0]}-{pcts[-1]} ({len(combos)} candidate combo(s))"
    )
    return {
        "mode": "encounter",
        "species": result["species"],
        "cp": result["cp"],
        "source": source,
        "exact": False,
        "iv_pct_range": (pcts[0], pcts[-1]),
        "level": level,
        "combos": combos,
        "summary": summary,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Scan a Pokemon GO screenshot for IVs.")
    parser.add_argument("image")
    parser.add_argument("--source", choices=list(SOURCE_RULES), default="wild")
    parser.add_argument("--boosted", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    import classify

    screen_type = classify.classify_screen(args.image)
    if screen_type == classify.ENCOUNTER:
        result = scan_encounter(args.image, args.source)
    elif screen_type == classify.PROFILE_APPRAISAL:
        result = scan_profile(args.image)
    else:
        raise NotImplementedError(
            "profile screen without appraisal open -- CP+HP-only IV-set solve not yet wired into the CLI"
        )

    if args.json:
        print(json.dumps(result, default=str))
    else:
        print(result["summary"])


if __name__ == "__main__":
    main()
