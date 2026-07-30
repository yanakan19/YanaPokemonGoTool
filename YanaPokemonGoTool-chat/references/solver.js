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
  return "solver.js self-test passed";
}

module.exports = {
  CPM, ALL_LEVELS, cpFormula, hpFormula, ivPercent, forwardSolve,
  reverseSolve, hundoCp, isGuaranteedHundo, starRating, selfTest,
};
