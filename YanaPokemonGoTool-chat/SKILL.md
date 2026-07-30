---
name: YanaPokemonGoChat
description: Analyse Pokemon GO screenshots to get exact IVs, level, and IV%, using vision only (no code execution besides the built-in analysis tool for arithmetic). Also maintains a running roster of every Pokemon scanned in this conversation, sortable/filterable by CP and IV. Use whenever the user uploads or mentions a Pokemon GO screenshot, asks about IVs, appraisal, CP, "is this a hundo", whether a Pokemon is worth powering up, wants to see their scanned Pokemon list, or asks to sort/filter their Pokemon by CP or IV -- even if they don't say "IV".
---

# YanaPokemonGoChat

Chat-only counterpart to the Claude Code `YanaPokemonGoTool` skill. No OpenCV, no Tesseract,
no Python execution -- everything that skill did with pixel math and OCR, this one does
with your own vision on the uploaded image, plus the built-in analysis/code-execution
tool for the arithmetic that must not be done by hand.

**Read `references/limits.md` first.** The honesty rules from the Code version apply
identically here: never present an estimate as an exact IV, and a wild encounter never
gets a single IV% number.

## Capabilities menu (read this first)

  - **A) Scan a profile screenshot** (appraisal open) -> Mode A below. Exact species,
    level, IV A/D/S, IV%, CP, HP, star rating.
  - **B) Scan an encounter screenshot** (pre-catch) -> Mode B below. Honest IV% range,
    never a single number.
  - **C) Roster: view / sort / filter** scanned Pokemon -> see "The running roster" and
    `references/roster.md`. Sort by CP or IV%, either direction; filter by IV% threshold.
  - **D) Forward/reverse CP-HP solve** -> `forwardSolve` / `reverseSolve` in
    `references/solver.js`. Given known IVs+level -> CP/HP, or given CP(+HP) -> every
    matching (level, IVs) combo.
  - **E) Power-up cost calculator** -> `powerupCost(fromLevel, toLevel, {lucky, shadow,
    purified})` in `references/solver.js`. Stardust + candy required between two levels
    (1.0-40.5). Candy costs at/above level 39 are flagged `approximate: true` in the
    result -- say so if asked about that range.
  - **F) Max level under a CP cap, plus cost to get there** -> `maxLevelUnderCp(baseAtk,
    baseDef, baseSta, ivA, ivD, ivS, cpCap)` then `powerupCost(currentLevel, thatLevel)`.
    e.g. "what's the highest level I can take this to and stay under 2500 CP, and what
    will that cost from here?"
  - **G) Best moveset lookup** -> live web search (this is meta-dependent DPS/PvP ranking
    data from sites like PvPoke/GamePress/LeekDuck, not a formula -- look it up fresh each
    time rather than guessing or relying on stale training knowledge, and say which source
    you used).

## Division of labour: vision vs. code execution

- **Vision does**: reading the CP number, the HP number, the bottom caption text, the
  species name, counting filled pips on the three appraisal bars, locating and reading
  the moving name+CP banner on an encounter screen, and reading the weather icon.
- **The analysis tool does**: every CP/HP formula evaluation and the brute-force level
  solve. Load `references/solver.js` into the tool and call its functions -- do not
  compute CP or HP by hand, and do not eyeball which level a CP corresponds to. The
  floor()/sqrt() interactions make this unreliable to do mentally even for a single
  data point, let alone a brute-force search over 101 levels.

Before trusting any solver output in a session, run `solver.selfTest()` once. If it
doesn't return "solver.js self-test passed" exactly, stop and report the mismatch
instead of proceeding with unverified arithmetic.

See `references/vision_reading.md` for the detailed how-to on reading each field with
vision alone (species caption, CP/HP, pip-counting the bars, locating the encounter
banner) -- read it before your first scan in a session.

## Mode A: profile screenshot (with appraisal open)

1. Look at the bottom caption band (near the very bottom of the screenshot, small grey
   text starting "This ___ was caught on..."). **This caption is the only trustworthy
   species source.** Never use the nickname (large text near the pencil icon) or the
   candy counter label -- see `references/limits.md` for why the candy label is a trap
   (a Slaking's candy is labelled "Slakoth Candy").
2. Read the CP number at the top and the HP number below the sprite directly with vision.
3. Look at the three appraisal bars (Attack, Defense, HP order, each a track of 15 pips
   drawn as 3 visible groups of 5). Count how many pips are filled (coloured) vs
   unfilled (grey) in each bar. This is a discrete count, not a continuous measurement --
   report the pip count as your confidence in the number, not a percentage estimate.
   The bar highlighted in red (rather than orange) is the Pokemon's best stat -- this is
   just a colour choice by the game and doesn't change how you count pips.
4. Look up the species' base stats in `references/species.json` (key = lowercase species
   name, e.g. `"metagross"`). If the species isn't found, say so rather than guessing
   base stats.
5. In the analysis tool: call `reverseSolve(baseAtk, baseDef, baseSta, cp, {hp})` (pass
   the HP you read too, if you're confident in it -- it's a second independent digit
   read, same reliability class as CP) and filter the results down to the combo matching
   your counted attack/defense/hp pip IVs exactly. If exactly one combo matches, that's
   your answer -- run `forwardSolve` to confirm it reproduces CP and HP exactly as a
   sanity check.
   If **none** match: don't hard-fail. CP and HP are plain digit reads (more reliable
   than three separate pip counts), so fall back to the CP(+HP)-consistent combo closest
   to your pip counts (smallest total difference across the three stats), and tell the
   user which bar you had to override, per `references/vision_reading.md`'s "when the bar
   count doesn't reconcile" section. Only refuse outright if even the closest consistent
   combo is wildly far from what you counted (more than ~2 stats off by several points
   each) -- that suggests a wrong species/form rather than a simple misread.
6. Compute IV% as `ivPercent(ivA, ivD, ivS)` -- never estimate this by eye.

## Mode B: encounter screenshot (pre-catch)

1. Locate the moving name+CP banner (it can be anywhere in the upper-middle band of the
   screen) and read the species name and CP from it directly.
2. Ask the user (or use what they told you) which encounter source this is: wild, raid,
   egg, research, or Rocket. Look for a weather icon near the banner if relevant.
3. Apply the level/floor rules from `references/limits.md`'s encounter table.
4. For **wild**: use `reverseSolve` over all levels 1-30 (or 6-35 if weather-boosted) with
   the appropriate IV floor, then report the candidate IV% range and level range plainly --
   **never a single IV%**. Explicitly say CP alone can't determine IV for a wild catch and
   suggest scanning the profile screen with appraisal open after catching it.
5. For **raid/egg/research** (fixed level): first check `isGuaranteedHundo` -- if true,
   report "100% guaranteed IV". Otherwise run `reverseSolve` at that fixed level and floor
   and report the resulting IV% range (usually a handful of points wide).

## The running roster (this conversation only)

Maintain a single roster of every Pokemon scanned so far **in this conversation**, since
there is no cross-conversation storage available in plain chat. After every successful
scan (Mode A only -- encounter-mode results are estimates and should not silently join
the exact-IV roster unless the user explicitly asks you to log them as a range entry):

1. Re-print the **entire updated roster** as a markdown table so it stays visible in the
   conversation history for you to re-read on the next turn. Do not just print the new
   entry -- earlier entries must not be lost.
2. Table columns, in this exact order: `Species | CP | IV% | IV (A/D/S) | HP | Level`.
3. If the same species+CP+IV combination the user scans again is already in the roster,
   don't duplicate it -- ask if it's the same Pokemon or a new catch with identical rolls.

See `references/roster.md` for the exact sort/filter contract (defaults, command phrasing
to recognise, and output format) -- follow it precisely, this is a specific UX the user
asked for.

## Output format for a single scan

One compact line plus the roster update, e.g.:

```
Metagross - L37 - 14/15/10 - 87% (3-star) - CP 3571 - HP 154
Added to your roster (now 12 Pokemon tracked).
```
