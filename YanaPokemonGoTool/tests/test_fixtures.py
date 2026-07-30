"""End-to-end tests against the real screenshots referenced in the build spec.

Drop the three fixture screenshots into tests/fixtures/ to enable these:
  - IMG_2416.PNG  (Metagross profile+appraisal)
  - IMG_2415.PNG  (Slaking profile+appraisal, nicknamed "LazyGuy")
  - IMG_2414.PNG  (Munna encounter, windy boost)

Without them present, these tests are skipped rather than faked -- this
environment does not have the original screenshots available.
"""
import sys
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent / "fixtures"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

pytestmark = pytest.mark.skipif(
    not (FIXTURES / "IMG_2416.PNG").exists(),
    reason="real fixture screenshots not present in tests/fixtures/",
)


def test_metagross_profile():
    import scan
    result = scan.scan_profile(str(FIXTURES / "IMG_2416.PNG"))
    assert result["species"] == "Metagross"
    assert result["level"] == 37.0
    assert (result["iv_a"], result["iv_d"], result["iv_s"]) == (14, 15, 10)
    assert result["iv_pct"] == 87
    assert result["cp"] == 3571
    assert result["hp_check"] == 154


def test_slaking_profile_not_nickname_or_candy():
    import scan
    result = scan.scan_profile(str(FIXTURES / "IMG_2415.PNG"))
    assert result["species"] == "Slaking"
    assert result["species"] not in ("LazyGuy", "Slakoth")
    assert result["level"] == 30.0
    assert (result["iv_a"], result["iv_d"], result["iv_s"]) == (13, 14, 13)
    assert result["iv_pct"] == 89
    assert result["cp"] == 3750
    assert result["hp_check"] == 217


def test_munna_encounter_refuses_exact_iv():
    import scan
    result = scan.scan_encounter(str(FIXTURES / "IMG_2414.PNG"), source="wild")
    assert result["species"] == "Munna"
    assert result["cp"] == 514
    assert result["exact"] is False
    lo, hi = result["iv_pct_range"]
    assert lo <= 25 and hi >= 70
