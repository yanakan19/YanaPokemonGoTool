"""
YanaPokemonGoTool capabilities menu.

Run `python3 menu.py` with no arguments to print this list. This is the
"homepage" for the toolkit -- read it first to see what's available and
which script/function backs each capability, rather than guessing at
script names.
"""

MENU = """
YanaPokemonGoTool -- capabilities

  A) Scan a profile screenshot (appraisal open)  -> scan.scan_profile(path)
     Exact species, level, IV A/D/S, IV%, CP, HP, star rating.

  B) Scan an encounter screenshot (pre-catch)     -> read_encounter.py + solver.reverse_solve
     Honest IV% range (never a single number) for wild/raid/egg/research/Rocket.

  C) Roster: view / sort / filter scanned Pokemon -> maintained by the calling
     conversation (see references/roster equivalent), not a standalone script.
     Sort by CP or IV%, high-to-low or low-to-high; filter by IV% threshold.

  D) Forward/reverse CP-HP solve                  -> solver.forward_solve / solver.reverse_solve
     Given known IVs+level -> CP/HP, or given CP(+HP) -> all matching (level, IVs).

  E) Power-up cost calculator                     -> powerup_cost.powerup_cost(from_lvl, to_lvl)
     Stardust + candy required between two levels (1.0-40.5), with lucky/shadow/purified modifiers.

  F) Max level under a CP cap, plus cost to get there
     -> solver.max_level_under_cp(...) then powerup_cost.powerup_cost(current, that_level)
     e.g. "what's the highest level I can take this to and stay under 2500 CP,
     and what will that cost me from here?"

  G) Best moveset lookup                          -> live web search (WebSearch/WebFetch)
     Meta-dependent (PvP/PvE rankings shift), not a formula -- looked up fresh
     each time from PvPoke/GamePress/LeekDuck rather than hardcoded, so it stays
     current. Not backed by a local script.

Call self_test() below before trusting any solver output in a new session.
"""


def self_test():
    import solver as S
    import powerup_cost as P

    mg = S.forward_solve(257, 228, 190, 14, 15, 10, 37)
    assert mg == (3571, 154), mg
    assert S.iv_percent(14, 15, 10) == 87

    cost = P.powerup_cost(25.5, 40.0)
    assert cost["stardust"] == 190000, cost

    lvl = S.max_level_under_cp(275, 211, 205, 14, 11, 10, 2500)
    assert lvl is not None and S.cp_formula(275, 211, 205, 14, 11, 10, lvl) <= 2500

    return "menu.py self-test passed"


if __name__ == "__main__":
    print(MENU)
    print(self_test())
