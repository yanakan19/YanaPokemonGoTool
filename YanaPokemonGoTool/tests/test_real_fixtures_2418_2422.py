"""Regression tests against 5 real screenshots (IMG_2418-2422) supplied
during development. These caught real bugs that the synthetic tests missed:

- CP OCR failing outright on a pale/low-contrast habitat background, and on
  a star-bubble icon's curved edge bleeding into the crop (IMG_2418, 2420).
- The caption crop truncating "This <species> was caught..." when a long
  location name wraps the caption to 3 lines instead of 2 (IMG_2421).
- The appraisal bars box shifting vertically depending on whether a
  Dynamax-eligibility row is present above it on the card (IMG_2421).
- The HP region only ever capturing the top sliver of "X / Y HP" text,
  silently producing a wrong cross-check value on every fixture (all 5).
- A Pokemon-model spike/edge crossing the CP digits and adding a spurious
  digit in a minority of binarisations (IMG_2422).
- A bar (Dialga's Defense) reading as fully filled with no way to reconcile
  that against the CP+HP-consistent IV space for either known form --
  exercises the closest-consistent-combo fallback in scan.scan_profile
  rather than a hard crash.
"""
import sys
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent / "fixtures"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

pytestmark = pytest.mark.skipif(
    not (FIXTURES / "IMG_2418.PNG").exists(),
    reason="real fixture screenshots not present in tests/fixtures/",
)


def test_slaking_2418():
    import scan
    result = scan.scan_profile(str(FIXTURES / "IMG_2418.PNG"))
    assert result["species"] == "Slaking"
    assert result["level"] == 30.0
    assert (result["iv_a"], result["iv_d"], result["iv_s"]) == (13, 14, 13)
    assert result["iv_pct"] == 89
    assert result["cp"] == 3750
    assert result["hp_ocr"] == 217
    assert result["hp_check"] == 217
    assert result["note"] is None


def test_metagross_2419():
    import scan
    result = scan.scan_profile(str(FIXTURES / "IMG_2419.PNG"))
    assert result["species"] == "Metagross"
    assert result["level"] == 37.0
    assert (result["iv_a"], result["iv_d"], result["iv_s"]) == (14, 15, 10)
    assert result["iv_pct"] == 87
    assert result["cp"] == 3571
    assert result["hp_ocr"] == 154
    assert result["hp_check"] == 154
    assert result["note"] is None


def test_gyarados_2420():
    import scan
    result = scan.scan_profile(str(FIXTURES / "IMG_2420.PNG"))
    assert result["species"] == "Gyarados"
    assert result["level"] == 36.0
    assert (result["iv_a"], result["iv_d"], result["iv_s"]) == (11, 11, 15)
    assert result["iv_pct"] == 82
    assert result["cp"] == 3115
    assert result["hp_ocr"] == 177
    assert result["hp_check"] == 177


def test_machamp_2421_shifted_bars_box():
    """Single-type Fighting Pokemon with no second type-icon row -- the whole
    bars box sits ~85px higher on the card than the dual-type fixtures."""
    import scan
    result = scan.scan_profile(str(FIXTURES / "IMG_2421.PNG"))
    assert result["species"] == "Machamp"
    assert result["level"] == 42.0
    assert (result["iv_a"], result["iv_d"], result["iv_s"]) == (15, 12, 15)
    assert result["iv_pct"] == 93
    assert result["cp"] == 3107
    assert result["hp_ocr"] == 177
    assert result["hp_check"] == 177


def test_dialga_2422_falls_back_to_cp_hp_consistent_combo():
    """The Defense bar reads as fully filled but no combo with defense=15
    reproduces this CP+HP for either known Dialga form -- scan_profile must
    fall back to the closest CP+HP-consistent combo and flag it via `note`,
    not crash and not silently report the unverifiable bar-read IVs."""
    import scan
    result = scan.scan_profile(str(FIXTURES / "IMG_2422.PNG"))
    assert result["species"] == "Dialga"
    assert result["cp"] == 2949
    assert result["hp_ocr"] == 146
    assert result["hp_check"] == 146
    assert result["note"] is not None
    assert "15" in result["note"]  # names the bar-measured defense of 15
