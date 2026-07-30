"""CP/HP formulas, CPM table, and forward/reverse IV solving for Pokemon GO.

No ML, no external calls at request time. All math is vectorised with numpy
over the 16x16x16 IV grid so a full brute-force search stays sub-millisecond.
"""
import json
import math
from functools import lru_cache
from pathlib import Path

import numpy as np

# Integer-level CPMs, loaded from data/species.json, which build_data.py
# extracts verbatim from the PokeMiners game master -- the authoritative
# source Niantic actually ships.
#
# DO NOT re-hardcode this table. A previously hardcoded copy silently carried
# wrong values across levels 16-29 and 31-41 (e.g. L20 0.5977679 instead of
# the real 0.5974, L28 0.7100906 instead of 0.7068842). The errors are tiny
# in absolute terms but shift computed CP by 10-25 points, which is enough to
# make a genuine 15/15/15 fail to reconcile and get mis-reported as ~93%.
# Every unreconcilable real-screenshot case turned out to sit in that
# corrupted band. Anchors at L1/10/15/30/35/40/45 happened to be correct,
# which is exactly why the bug survived earlier spot-checks -- verify the
# whole curve against the game master, never a handful of round levels.
MAX_LEVEL = 51  # highest level obtainable in game (Best Buddy boost from 50)

_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "species.json"


def _load_int_cpm():
    with open(_DATA_PATH) as f:
        raw = json.load(f)["cpm"]
    return {
        int(lvl): value
        for lvl, value in raw.items()
        if value is not None and int(lvl) <= MAX_LEVEL
    }


INT_CPM = _load_int_cpm()


def _build_full_cpm():
    """Integer levels plus half-levels (sqrt of the mean of the two adjacent squares).

    The half-level relation is verified against real screenshots: a 15/15/15
    Alakazam (271/167/146) at L28.5 reproduces its in-game CP 2490 / HP 114
    exactly under this formula with game-master integer CPMs.
    """
    full = {}
    levels = sorted(INT_CPM)
    for lvl in levels:
        full[float(lvl)] = INT_CPM[lvl]
    for a, b in zip(levels, levels[1:]):
        half = a + 0.5
        full[half] = math.sqrt((INT_CPM[a] ** 2 + INT_CPM[b] ** 2) / 2)
    return dict(sorted(full.items()))


CPM = _build_full_cpm()
ALL_LEVELS = sorted(CPM.keys())


def cp_formula(base_atk, base_def, base_sta, iv_a, iv_d, iv_s, level):
    cpm = CPM[level]
    val = (base_atk + iv_a) * math.sqrt(base_def + iv_d) * math.sqrt(base_sta + iv_s) * cpm ** 2 / 10
    return max(10, math.floor(val))


def hp_formula(base_sta, iv_s, level):
    cpm = CPM[level]
    return max(10, math.floor((base_sta + iv_s) * cpm))


def iv_percent(iv_a, iv_d, iv_s):
    total = iv_a + iv_d + iv_s
    return int(math.floor(total / 45 * 100 + 0.5))


# The in-game appraisal badge is a 3-star system (not 5), confirmed against
# 5 real screenshots spanning 78-93% IV -- all showed the same 3-filled-star
# badge. The upper two boundaries (66%, 49%) match widely-documented community
# values and are consistent with every fixture on hand, but no fixture below
# 66% was available to directly confirm the 1-star/2-star split -- flag this
# if a low-IV catch ever shows a badge that disagrees.
def star_rating(iv_pct):
    if iv_pct >= 66:
        return 3
    if iv_pct >= 49:
        return 2
    return 1


@lru_cache(maxsize=None)
def _species_grid(base_atk, base_def, base_sta):
    """(16,16,16) grid of (atk+a) * sqrt(def+d) * sqrt(sta+s), indexed [a, d, s]."""
    ivs = np.arange(16)
    a = base_atk + ivs
    d = np.sqrt(base_def + ivs)
    s = np.sqrt(base_sta + ivs)
    grid = a[:, None, None] * d[None, :, None] * s[None, None, :]
    return grid


def forward_solve(base_atk, base_def, base_sta, iv_a, iv_d, iv_s, level):
    cp = cp_formula(base_atk, base_def, base_sta, iv_a, iv_d, iv_s, level)
    hp = hp_formula(base_sta, iv_s, level)
    return cp, hp


def reverse_solve(base_atk, base_def, base_sta, target_cp, levels=None,
                   iv_floor=(0, 0, 0), hp=None):
    """Return all (level, iv_a, iv_d, iv_s) combos matching target_cp (and hp if given)."""
    if levels is None:
        levels = ALL_LEVELS
    grid = _species_grid(base_atk, base_def, base_sta)
    fa, fd, fs = iv_floor
    sub = grid[fa:16, fd:16, fs:16]

    matches = []
    for level in levels:
        cpm = CPM[level]
        cp_grid = np.floor(sub * cpm ** 2 / 10)
        cp_grid = np.maximum(cp_grid, 10)
        idx = np.argwhere(cp_grid == target_cp)
        for a, d, s in idx:
            iv_a, iv_d, iv_s = a + fa, d + fd, s + fs
            if hp is not None:
                computed_hp = hp_formula(base_sta, iv_s, level)
                if computed_hp != hp:
                    continue
            matches.append((level, int(iv_a), int(iv_d), int(iv_s)))
    return matches


def hundo_cp(base_atk, base_def, base_sta, level):
    """CP for 15/15/15 at a fixed level."""
    return cp_formula(base_atk, base_def, base_sta, 15, 15, 15, level)


def is_guaranteed_hundo(base_atk, base_def, base_sta, level, observed_cp):
    """True if observed_cp equals the unique 15/15/15 CP at this level."""
    return observed_cp == hundo_cp(base_atk, base_def, base_sta, level)


def max_cp_is_unique(base_atk, base_def, base_sta, level, iv_floor=(0, 0, 0)):
    """Verify the hundo CP has no other IV combo (within floor) producing the same CP."""
    top_cp = hundo_cp(base_atk, base_def, base_sta, level)
    combos = reverse_solve(base_atk, base_def, base_sta, top_cp, levels=[level], iv_floor=iv_floor)
    return len(combos) == 1 and combos[0][1:] == (15, 15, 15)


def max_level_under_cp(base_atk, base_def, base_sta, iv_a, iv_d, iv_s, cp_cap):
    """Highest level (from ALL_LEVELS) at which this exact IV combo's CP stays <= cp_cap.

    Returns None if even level 1 exceeds cp_cap (undersized cap for this species).
    """
    best = None
    for level in ALL_LEVELS:
        cp = cp_formula(base_atk, base_def, base_sta, iv_a, iv_d, iv_s, level)
        if cp <= cp_cap:
            best = level
        else:
            break  # CP is monotonic in level for fixed IVs
    return best
