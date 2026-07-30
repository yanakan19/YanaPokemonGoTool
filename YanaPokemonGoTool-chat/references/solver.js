/*
 * CP/HP solver for Pokemon GO, ported from the Claude Code skill's solver.py.
 * Run this in the analysis/code-execution tool -- do NOT do this arithmetic
 * mentally, the CP formula's floor() and sqrt() make hand-calculation
 * unreliable across 4096 IV combos x 101 levels.
 *
 * Usage inside the sandbox:
 *   1. Paste this whole file (or fetch it if the tool allows file reads).
 *   2. Call forwardSolve(...) / reverseSolve(...) / hundoCp(...) as needed.
 */

// Integer-level CPMs from the game master (validated ground truth -- do not
// substitute a value from a blog/SEO calculator).
const INT_CPM = {
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
};

function buildFullCpm() {
  const levels = Object.keys(INT_CPM).map(Number).sort((a, b) => a - b);
  const full = {};
  for (const lvl of levels) full[lvl] = INT_CPM[lvl];
  for (let i = 0; i < levels.length - 1; i++) {
    const a = levels[i], b = levels[i + 1];
    full[a + 0.5] = Math.sqrt((INT_CPM[a] ** 2 + INT_CPM[b] ** 2) / 2);
  }
  return full;
}

const CPM = buildFullCpm();
const ALL_LEVELS = Object.keys(CPM).map(Number).sort((a, b) => a - b);

function cpFormula(baseAtk, baseDef, baseSta, ivA, ivD, ivS, level) {
  const cpm = CPM[level];
  const val = (baseAtk + ivA) * Math.sqrt(baseDef + ivD) * Math.sqrt(baseSta + ivS) * cpm ** 2 / 10;
  return Math.max(10, Math.floor(val));
}

function hpFormula(baseSta, ivS, level) {
  const cpm = CPM[level];
  return Math.max(10, Math.floor((baseSta + ivS) * cpm));
}

function ivPercent(ivA, ivD, ivS) {
  const total = ivA + ivD + ivS;
  return Math.floor((total / 45) * 100 + 0.5);
}

function forwardSolve(baseAtk, baseDef, baseSta, ivA, ivD, ivS, level) {
  return {
    cp: cpFormula(baseAtk, baseDef, baseSta, ivA, ivD, ivS, level),
    hp: hpFormula(baseSta, ivS, level),
  };
}

// Brute-force reverse solve: all (level, ivA, ivD, ivS) combos matching
// targetCp (and hp, if given), restricted to `levels` and `ivFloor`.
function reverseSolve(baseAtk, baseDef, baseSta, targetCp, {
  levels = ALL_LEVELS, ivFloor = [0, 0, 0], hp = null,
} = {}) {
  const [fa, fd, fs] = ivFloor;
  const matches = [];
  for (const level of levels) {
    const cpm = CPM[level];
    for (let a = fa; a <= 15; a++) {
      for (let d = fd; d <= 15; d++) {
        for (let s = fs; s <= 15; s++) {
          const cp = cpFormula(baseAtk, baseDef, baseSta, a, d, s, level);
          if (cp !== targetCp) continue;
          if (hp !== null && hpFormula(baseSta, s, level) !== hp) continue;
          matches.push({ level, ivA: a, ivD: d, ivS: s });
        }
      }
    }
  }
  return matches;
}

function hundoCp(baseAtk, baseDef, baseSta, level) {
  return cpFormula(baseAtk, baseDef, baseSta, 15, 15, 15, level);
}

function isGuaranteedHundo(baseAtk, baseDef, baseSta, level, observedCp) {
  return observedCp === hundoCp(baseAtk, baseDef, baseSta, level);
}

// 3-star system (not 5), confirmed against 5 real screenshots spanning
// 78-93% IV -- all showed the same 3-filled-star badge. The 66%/49%
// boundaries match widely-documented community values and are consistent
// with every fixture checked, but no fixture below 66% was available to
// directly confirm the 1-star/2-star split.
function starRating(ivPct) {
  if (ivPct >= 66) return 3;
  if (ivPct >= 49) return 2;
  return 1;
}

// Highest level (from ALL_LEVELS) at which this exact IV combo's CP stays
// <= cpCap. CP is monotonic in level for fixed IVs, so this can stop at the
// first level that exceeds the cap. Returns null if even level 1 exceeds it.
function maxLevelUnderCp(baseAtk, baseDef, baseSta, ivA, ivD, ivS, cpCap) {
  let best = null;
  for (const level of ALL_LEVELS) {
    const cp = cpFormula(baseAtk, baseDef, baseSta, ivA, ivD, ivS, level);
    if (cp <= cpCap) best = level;
    else break;
  }
  return best;
}

// Stardust/candy power-up cost table. Source: reverse-engineered by the
// community, published at https://github.com/mathiasbynens/pogopowerupcost
// -- verified against a real gameinfo.io screenshot showing 190,000 stardust
// for a 25.5->40 power-up path (this table reproduces that exactly). Candy
// costs at/above level 39 are flagged approximate (the source repo itself
// marks that tier unconfirmed). Levels above 40.5 (Best Buddy/XL Candy) are
// not included -- never published by Niantic, no reliable source found.
const COST_PER_POWERUP = {
  1.0: [200, 1], 1.5: [200, 1], 2.0: [200, 1], 2.5: [200, 1],
  3.0: [400, 1], 3.5: [400, 1], 4.0: [400, 1], 4.5: [400, 1],
  5.0: [600, 1], 5.5: [600, 1], 6.0: [600, 1], 6.5: [600, 1],
  7.0: [800, 1], 7.5: [800, 1], 8.0: [800, 1], 8.5: [800, 1],
  9.0: [1000, 1], 9.5: [1000, 1], 10.0: [1000, 1], 10.5: [1000, 1],
  11.0: [1300, 2], 11.5: [1300, 2], 12.0: [1300, 2], 12.5: [1300, 2],
  13.0: [1600, 2], 13.5: [1600, 2], 14.0: [1600, 2], 14.5: [1600, 2],
  15.0: [1900, 2], 15.5: [1900, 2], 16.0: [1900, 2], 16.5: [1900, 2],
  17.0: [2200, 2], 17.5: [2200, 2], 18.0: [2200, 2], 18.5: [2200, 2],
  19.0: [2500, 2], 19.5: [2500, 2], 20.0: [2500, 2], 20.5: [2500, 2],
  21.0: [3000, 3], 21.5: [3000, 3], 22.0: [3000, 3], 22.5: [3000, 3],
  23.0: [3500, 3], 23.5: [3500, 3], 24.0: [3500, 3], 24.5: [3500, 3],
  25.0: [4000, 3], 25.5: [4000, 3], 26.0: [4000, 3], 26.5: [4000, 3],
  27.0: [4500, 3], 27.5: [4500, 3], 28.0: [4500, 3], 28.5: [4500, 3],
  29.0: [5000, 4], 29.5: [5000, 4], 30.0: [5000, 4], 30.5: [5000, 4],
  31.0: [6000, 6], 31.5: [6000, 6], 32.0: [6000, 6], 32.5: [6000, 6],
  33.0: [7000, 8], 33.5: [7000, 8], 34.0: [7000, 8], 34.5: [7000, 8],
  35.0: [8000, 10], 35.5: [8000, 10], 36.0: [8000, 10], 36.5: [8000, 10],
  37.0: [9000, 12], 37.5: [9000, 12], 38.0: [9000, 12], 38.5: [9000, 12],
  39.0: [10000, 15], 39.5: [10000, 15], 40.0: [10000, 15], 40.5: [10000, 15],
};
const MAX_KNOWN_LEVEL = 40.5;
const UNCONFIRMED_FROM = 39.0;

function powerupCost(fromLevel, toLevel, { lucky = false, shadow = false, purified = false } = {}) {
  if (toLevel <= fromLevel) throw new Error("toLevel must be greater than fromLevel");
  if (toLevel > MAX_KNOWN_LEVEL) throw new Error(`no verified cost data above level ${MAX_KNOWN_LEVEL}`);
  let dust = 0, candy = 0, approximate = false;
  for (let lvl = fromLevel; lvl < toLevel; lvl = Math.round((lvl + 0.5) * 10) / 10) {
    if (!(lvl in COST_PER_POWERUP)) throw new Error(`level ${lvl} not in cost table`);
    const [d, c] = COST_PER_POWERUP[lvl];
    if (lvl >= UNCONFIRMED_FROM) approximate = true;
    dust += d;
    candy += c;
  }
  if (shadow) { dust = Math.round(dust * 1.2); candy = Math.round(candy * 1.2); }
  else if (purified) { dust = Math.ceil(dust * 0.9); candy = Math.ceil(candy * 0.9); }
  if (lucky) dust = Math.round(dust * 0.5);
  return { stardust: dust, candy, approximate };
}

// --- Self-check against the two validated fixtures. Run this first; if it
// throws, do not trust any other output from this file in this session. ---
function selfTest() {
  const mg = forwardSolve(257, 228, 190, 14, 15, 10, 37);
  if (mg.cp !== 3571 || mg.hp !== 154) {
    throw new Error(`Metagross fixture failed: got CP ${mg.cp}, HP ${mg.hp}, expected CP 3571, HP 154`);
  }
  const sl = forwardSolve(290, 166, 284, 13, 14, 13, 30);
  if (sl.cp !== 3750 || sl.hp !== 217) {
    throw new Error(`Slaking fixture failed: got CP ${sl.cp}, HP ${sl.hp}, expected CP 3750, HP 217`);
  }
  if (ivPercent(14, 15, 10) !== 87) throw new Error("IV% formula failed on 14/15/10");
  if (ivPercent(13, 14, 13) !== 89) throw new Error("IV% formula failed on 13/14/13");
  const cost = powerupCost(25.5, 40.0);
  if (cost.stardust !== 190000) throw new Error(`powerupCost fixture failed: got ${cost.stardust}, expected 190000`);
  return "solver.js self-test passed";
}

module.exports = {
  CPM, ALL_LEVELS, cpFormula, hpFormula, ivPercent, forwardSolve,
  reverseSolve, hundoCp, isGuaranteedHundo, starRating, maxLevelUnderCp,
  COST_PER_POWERUP, powerupCost, selfTest,
};
