# Honest capability matrix

| Input | What's on screen | Achievable result |
|---|---|---|
| Profile screen with appraisal open | CP, HP, 3 stat bars, species caption | Exact IVs, exact level, exact IV% |
| Profile screen without appraisal | CP, HP only | IV *set* (dozens of combos) |
| Encounter screen (pre-catch), fixed-level source | species + CP only, no HP | IV% to ~+-2%; 100% is provable |
| Encounter screen (pre-catch), wild | species + CP only, no HP | Cannot give exact IV |

The encounter-screen ask is mathematically limited, not a coding problem: CP is one scalar
produced from four hidden values (level, IV_a, IV_d, IV_s). One equation, four unknowns.

- Unknown level (wild): candidates can span 20%-76% IV. Not useful as a single number.
- Known level, raid catch (L20, 10/10/10 floor): ~2.8 candidates per CP, spread ~1 IV point
  -> IV% pinned to about +-2%.
- Known level, research encounter (L15, 0 floor): ~22 candidates per CP, spread ~5 points
  -> +-11%. Weak.

So Mode B (encounter) must classify the encounter type, then either return a tight range
(raid/egg/research) or say plainly "wild encounter, CP alone cannot determine IV" and offer
the post-catch scan instead. Never present an estimate as exact.

## The one guaranteed case: max CP is always unique to 15/15/15

Verified across multiple species/level combinations: the CP for a 15/15/15 (hundo) at a
fixed level has no other IV combination producing the same CP, with a gap of several CP
points to the next-highest combo. If a fixed-level encounter's CP equals the hundo CP for
that species/level, report **100% guaranteed**. `solver.is_guaranteed_hundo` implements this.

## Encounter level rules

| Source | Level | IV floor |
|---|---|---|
| Wild | 1-30 (uniform, capped by trainer level) | 0/0/0 |
| Wild, weather boosted | 6-35 | 4/4/4 |
| Raid boss catch | 20 (25 if boosted) | 10/10/10 |
| Egg hatch | 20 | 10/10/10 |
| Field research | 15 | 10/10/10 |
| Team GO Rocket shadow | 8 (13 if boosted) | 0/0/0 (6/6/6 in raids) |
| Lucky (traded) | unchanged | 12/12/12 |

## Species ID trap: the candy label and the nickname are not the species

A Pokémon's candy is always named after the *base form* of its evolution line, and its
nickname is arbitrary user text. Both will silently give you the wrong species (and
therefore the wrong base stats, level, and IVs) if used as the source of truth.

Regression case: IMG_2415 shows a Slaking nicknamed "LazyGuy" with candy labelled
"Slakoth Candy". The only field that says "Slaking" is the bottom caption
("This Slaking was caught on..."). A naive scraper keying off the candy label would
compute IVs against Slakoth's base stats (60/60/100) instead of Slaking's (290/166/284),
producing a wildly wrong level and IV. `scripts/read_profile.py` only ever reads species
from the caption regex.
