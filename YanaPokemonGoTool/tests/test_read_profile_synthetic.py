"""Synthetic-image tests for bar measurement/rounding, since real fixture
screenshots (IMG_2414/2415/2416) are not available in this environment.
Real fixtures should be dropped into tests/fixtures/ to enable
test_fixtures.py's end-to-end assertions.
"""
import sys
from pathlib import Path

import pytest

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import read_profile as RP  # noqa: E402


def _make_bar_image(fraction, width=1290, height=2796):
    """Draw a synthetic image with an attack-row bar filled to `fraction`."""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[:, :] = (0, 0, 0)
    y0f, y1f = RP.BAR_ROWS["attack"]
    yc = int(height * (y0f + y1f) / 2)
    x0f, x1f = RP.BAR_TRACK_X
    x0, x1 = int(width * x0f), int(width * x1f)
    track_w = x1 - x0
    filled_w = int(track_w * fraction)
    # BGR: orange fill ~ (b<130, g~170, r~230); grey unfilled ~ (220,220,220)
    img[yc, x0:x0 + filled_w] = (100, 170, 230)
    img[yc, x0 + filled_w:x1] = (220, 220, 220)
    return img


def _attack_row_centre(height=2796):
    y0f, y1f = RP.BAR_ROWS["attack"]
    return int(height * (y0f + y1f) / 2)


@pytest.mark.parametrize("iv,fraction", [(0, 0.0), (7, 7 / 15), (14, 14 / 15), (15, 1.0)])
def test_measure_and_round_roundtrip(iv, fraction):
    img = _make_bar_image(fraction)
    row_centres = {"attack": _attack_row_centre()}
    measured = RP.measure_bar_fraction(img, "attack", row_centres)
    assert measured == pytest.approx(fraction, abs=0.02)
    assert RP.fraction_to_iv(measured) == iv


def test_measure_bar_fraction_rejects_misaligned_crop():
    # An all-black image has no recognisable filled/grey pixels at the attack row.
    img = np.zeros((2796, 1290, 3), dtype=np.uint8)
    row_centres = {"attack": _attack_row_centre()}
    with pytest.raises(RP.ReadError):
        RP.measure_bar_fraction(img, "attack", row_centres)


def test_compute_iv_percent_matches_spec_examples():
    assert RP.compute_iv_percent(14, 15, 10) == 87
    assert RP.compute_iv_percent(13, 14, 13) == 89


def test_fraction_to_iv_within_tolerance_accepted():
    # 0.06 off a fifteenth, per the spec's worst observed error -- must not raise.
    exact = 10 / 15
    RP.fraction_to_iv(exact + 0.05)
