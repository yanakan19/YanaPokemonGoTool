"""CP/HP formulas, CPM table, and forward/reverse IV solving for Pokemon GO.

No ML, no external calls at request time. All math is vectorised with numpy
over the 16x16x16 IV grid so a full brute-force search stays sub-millisecond.
"""
import math
from functools import lru_cache

import numpy as np

# Integer-level CPMs from the game master (see references/calibration.md).
INT_CPM = {
    1: 0.094, 2: 0.16639787, 3: 0.21573247, 4: 0.25572005, 5: 0.29024988,
    6: 0.3210876, 7: 0.34921268, 8: 0.3752356, 9: 0.39956728, 10: 0.4225,
    11: 0.44310755, 12: 0.46279839, 13: 0.48168495, 14: 0.49985844, 15: 0.51739395,
    16: 0.5343277, 17: 0.5507927, 18: 0.5668094, 19: 0.5824596, 20: 0.5977679,
    21: 0.6127566, 22: 0.6274445, 23: 0.6418475, 24: 0.6559804, 25: 0.6698589,
    26: 0.6834955, 27: 0.6969034, 28: 0.7100906, 29: 0.7230753, 30: 0.7317,
    31: 0.73776948, 32: 0.74378943, 33: 0.74976104, 34: 0.75568551, 35: 0.76156384,
    36: 0.76739717, 37: 0.7731865, 38: 0.77893275, 39: 0.78463697, 40: 0.7903,
    41: 0.79530001, 42: 0.8003, 43: 0.8053, 44: 0.8103, 45: 0.8153,
    46: 0.8203, 47: 0.8253, 48: 0.8303, 49: 0.8353, 50: 0.84029999,
    51: 0.84529999,
}


def _build_full_cpm():
    """Integer levels plus half-levels (sqrt of the mean of the two adjacent squares)."""
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
