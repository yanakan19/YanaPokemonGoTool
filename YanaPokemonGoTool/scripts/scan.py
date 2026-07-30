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


def _candidate_forms(species_db, name):
    """Every stat-line this caption could refer to, default form first.

    The bottom caption says only "This Dialga was caught..." -- it cannot
    distinguish Origin Forme from Altered/normal, and the same is true of
    every other multi-form species (Giratina, Hisuian/Alolan regionals,
    Therian formes...). Base stats differ per form, so picking the default
    form and hoping is a coin flip. Instead, hand every form's stat line to
    the solver and let the CP/HP/bar reconciliation choose -- a wrong form
    almost never reproduces the exact bar reading, so the right one
    identifies itself.
    """
    base = name.lower().replace(" ", "_")
    keys = [base] if base in species_db else []
    keys += sorted(k for k in species_db if k.startswith(base + "_") and k != base)
    if not keys:
        raise KeyError(f"unknown species '{name}' -- not found in data/species.json")
    seen, forms = set(), []
    for key in keys:
        stats = species_db[key]
        fingerprint = (stats["atk"], stats["def"], stats["sta"])
        if fingerprint in seen:
            continue  # aliases of the same stat line (e.g. "dialga" == "dialga_dialga_normal")
        seen.add(fingerprint)
        forms.append((key, stats))
    return forms


BAR_MISMATCH_MAX_DISTANCE = 6  # sum of |delta| across the 3 stats we'll still trust


def scan_profile(image_path):
    import read_profile
    import solver as S

    result = read_profile.read_profile_screenshot(image_path)
    species_db = _load_species()
    forms = _candidate_forms(species_db, result["species"])
    bar_ivs = (result["iv_a"], result["iv_d"], result["iv_s"])

    # Try every form this caption could mean. A form whose base stats
    # reproduce the exact bar reading at some level (matching CP, and HP when
    # we read it) has effectively identified itself -- a wrong form's stat
    # line almost never lands on the same three integers by chance.
    form_key = None
    stats = None
    combos = combos_hp = None
    exact = []
    for candidate_key, candidate_stats in forms:
        cand_cp = S.reverse_solve(
            candidate_stats["atk"], candidate_stats["def"], candidate_stats["sta"],
            result["cp"], iv_floor=(0, 0, 0),
        )
        cand_hp = None
        if result["hp"] is not None:
            cand_hp = S.reverse_solve(
                candidate_stats["atk"], candidate_stats["def"], candidate_stats["sta"],
                result["cp"], iv_floor=(0, 0, 0), hp=result["hp"],
            )
        cand_combos = cand_hp if cand_hp else cand_cp
        cand_exact = [c for c in cand_combos if c[1:] == bar_ivs]
        # First form that reconciles exactly wins; otherwise keep the first
        # form that at least has candidate combos, for the fallback path.
        if cand_exact and not exact:
            form_key, stats, combos, combos_hp, exact = (
                candidate_key, candidate_stats, cand_combos, cand_hp, cand_exact,
            )
        elif stats is None and cand_combos:
            form_key, stats, combos, combos_hp = (
                candidate_key, candidate_stats, cand_combos, cand_hp,
            )

    if stats is None:
        raise read_profile.ReadError(
            f"no IV combo at any level reproduces CP {result['cp']} for "
            f"{result['species']} (tried {len(forms)} form(s): "
            f"{', '.join(k for k, _ in forms)}) -- re-check the CP digits"
        )

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
        # (reliable once it parsed at all -- and in the cases that motivated
        # this comment, independently confirmed correct by eye), while bar
        # pixel-reading is the noisier signal -- so fall back to the
        # CP(+HP)-consistent combo closest to what the bars measured, rather
        # than hard-failing on what's usually a small misread of a bar.
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
    # Only worth naming the form when the species actually has more than one
    # -- "Machamp (machamp)" is noise, "Dialga (dialga_dialga_origin)" isn't.
    form_label = f" [{form_key}]" if len(forms) > 1 else ""
    summary = (
        f"{result['species']}{form_label} · L{int(level) if level == int(level) else level} · "
        f"{iv_a}/{iv_d}/{iv_s} · {iv_pct}% "
        f"({stars}★) · CP {result['cp']}"
    )
    if note:
        summary += f"\nNote: {note}"
    return {
        "mode": "profile",
        "species": result["species"],
        "form": form_key,
        "forms_considered": [k for k, _ in forms],
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
