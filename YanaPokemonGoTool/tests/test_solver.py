import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import solver as S  # noqa: E402

METAGROSS = {"base_atk": 257, "base_def": 228, "base_sta": 190}
SLAKING = {"base_atk": 290, "base_def": 166, "base_sta": 284}
MUNNA = {"base_atk": 111, "base_def": 92, "base_sta": 183}


def test_cpm_endpoints():
    assert S.CPM[40.0] == pytest.approx(0.7903)
    assert S.CPM[50.0] == pytest.approx(0.8403, abs=1e-4)


def test_metagross_fixture_forward():
    cp, hp = S.forward_solve(**METAGROSS, iv_a=14, iv_d=15, iv_s=10, level=37.0)
    assert (cp, hp) == (3571, 154)


def test_slaking_fixture_forward():
    cp, hp = S.forward_solve(**SLAKING, iv_a=13, iv_d=14, iv_s=13, level=30.0)
    assert (cp, hp) == (3750, 217)


def test_metagross_fixture_reverse_unique_level():
    combos = S.reverse_solve(METAGROSS["base_atk"], METAGROSS["base_def"], METAGROSS["base_sta"], 3571)
    exact = [c for c in combos if c[1:] == (14, 15, 10)]
    assert exact == [(37.0, 14, 15, 10)]


def test_slaking_fixture_reverse_unique_level():
    combos = S.reverse_solve(SLAKING["base_atk"], SLAKING["base_def"], SLAKING["base_sta"], 3750)
    exact = [c for c in combos if c[1:] == (13, 14, 13)]
    assert exact == [(30.0, 13, 14, 13)]


def test_iv_percent():
    assert S.iv_percent(14, 15, 10) == 87
    assert S.iv_percent(13, 14, 13) == 89
    assert S.iv_percent(15, 15, 15) == 100
    assert S.iv_percent(0, 0, 0) == 0


def test_hundo_uniqueness_metagross_raid():
    assert S.max_cp_is_unique(**METAGROSS, level=20.0, iv_floor=(10, 10, 10))
    combos = S.reverse_solve(
        METAGROSS["base_atk"], METAGROSS["base_def"], METAGROSS["base_sta"],
        S.hundo_cp(**METAGROSS, level=20.0), levels=[20.0], iv_floor=(10, 10, 10),
    )
    assert len(combos) == 1
    assert combos[0][1:] == (15, 15, 15)


def test_hundo_uniqueness_slaking_raid():
    assert S.max_cp_is_unique(**SLAKING, level=20.0, iv_floor=(10, 10, 10))


def test_hundo_uniqueness_munna_raid():
    assert S.max_cp_is_unique(**MUNNA, level=20.0, iv_floor=(10, 10, 10))


def test_is_guaranteed_hundo_true_and_false():
    hundo = S.hundo_cp(**METAGROSS, level=20.0)
    assert S.is_guaranteed_hundo(**METAGROSS, level=20.0, observed_cp=hundo)
    assert not S.is_guaranteed_hundo(**METAGROSS, level=20.0, observed_cp=hundo - 5)


def test_munna_wild_encounter_candidate_spread():
    """CP 514, unknown level (1-30), 0/0/0 floor: candidates span a wide IV%."""
    combos = S.reverse_solve(**MUNNA, target_cp=514, levels=S.ALL_LEVELS, iv_floor=(0, 0, 0))
    pcts = [S.iv_percent(a, d, s) for _, a, d, s in combos]
    assert len(combos) > 20
    assert max(pcts) - min(pcts) > 30
