---
name: YanaPokemonGoTool
description: Analyse Pokémon GO screenshots to get exact IVs, level and IV%. Use this whenever the user uploads or mentions a Pokémon GO screenshot, asks about IVs, appraisal, CP, "is this a hundo", whether a Pokémon is worth powering up, or wants a catch's stats -- even if they don't say "IV".
---

# YanaPokemonGoTool

Reads Pokémon GO screenshots (profile with appraisal, profile without, or a pre-catch
encounter) and reports species, level, IVs, and IV%, computed from the CP/HP formulas --
no ML, no sprite matching required for the common case.

## Capabilities menu (read this first)

  - **A) Scan a profile screenshot** (appraisal open) -> `scan.scan_profile(path)`. Exact
    species, level, IV A/D/S, IV%, CP, HP, star rating.
  - **B) Scan an encounter screenshot** (pre-catch) -> `read_encounter.py` +
    `solver.reverse_solve`. Honest IV% range, never a single number.
  - **C) Roster: view / sort / filter** scanned Pokemon -- maintained by the calling
    conversation, same sort/filter contract as the chat variant (CP or IV%, either
    direction, IV% threshold filter).
  - **D) Forward/reverse CP-HP solve** -> `solver.forward_solve` / `solver.reverse_solve`.
    Given known IVs+level -> CP/HP, or given CP(+HP) -> every matching (level, IVs) combo.
  - **E) Power-up cost calculator** -> `powerup_cost.powerup_cost(from_level, to_level,
    lucky=, shadow=, purified=)`. Stardust + candy required between two levels
    (1.0-40.5). Candy costs at/above level 39 come back with `approximate: True` --
    surface that if asked about that range.
  - **F) Max level under a CP cap, plus cost to get there** -> `solver.max_level_under_cp
    (base_atk, base_def, base_sta, iv_a, iv_d, iv_s, cp_cap)` then
    `powerup_cost.powerup_cost(current_level, that_level)`.
  - **G) Best moveset lookup** -> live web search/fetch (this is meta-dependent DPS/PvP
    ranking data from sites like PvPoke/GamePress/LeekDuck, not a formula -- look it up
    fresh each time and cite the source rather than hardcoding it).

Run `python3 scripts/menu.py` to print this list plus a self-test of the solver/cost-table
functions -- do this once per session before trusting any output.

## Capability matrix (be honest about what's achievable -- see references/limits.md)

| Input | Result |
|---|---|
| Profile + appraisal open | Exact IVs, exact level, exact IV% |
| Profile without appraisal | IV *set* (many combos) -- report as a range |
| Encounter, fixed-level source (raid/egg/research) | IV% to within a few points; 100% is provable if CP matches the hundo CP |
| Encounter, wild | Cannot give exact IV -- say so plainly |

## Usage

```
python3 scripts/scan.py <image> [--source wild|raid|research|egg|rocket] [--boosted] [--json]
```

The first run (or whenever `data/species.json` is missing/stale) needs base stats built
from the game master:

```
python3 scripts/build_data.py            # downloads the PokeMiners game master
python3 scripts/build_data.py latest.json # or build from an already-downloaded copy
```

## Pipeline

1. `scripts/classify.py` -- 3-way pixel classification of the screenshot type.
2. `scripts/read_profile.py` -- fractional-region OCR (CP, caption) + appraisal-bar
   pixel measurement (IVs). Species always comes from the bottom caption regex --
   never the nickname or the candy label (see references/calibration.md for why).
3. `scripts/read_encounter.py` -- locates the moving name+CP banner and reads it.
4. `scripts/solver.py` -- CP/HP formulas, CPM table, and a vectorised numpy
   brute-force solver (forward and reverse) over species/IV/level space.
5. `scripts/scan.py` -- ties it together into the CLI entry point.

## Output format

One compact line plus detail, e.g.:

```
Metagross · L37 · 14/15/10 · 87% (4★) · CP 3571
```

For encounter screenshots without appraisal, never present an estimate as exact --
report a candidate range and say why.

## Dependencies

`opencv-python-headless`, `numpy`, `pytesseract` (+ the `tesseract-ocr` binary), `Pillow`.
No ML/model-weight dependency of any kind.
