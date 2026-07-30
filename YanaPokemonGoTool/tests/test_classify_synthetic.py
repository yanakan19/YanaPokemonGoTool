"""Synthetic classify.py tests -- real screenshots go in tests/fixtures/."""
import sys
from pathlib import Path

import pytest

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import classify as C  # noqa: E402


def _blank(width=1290, height=2796, value=30):
    return np.full((height, width, 3), value, dtype=np.uint8)


def test_encounter_when_no_caption_band(tmp_path):
    img = _blank()  # flat colour everywhere -> no caption text, no bars
    path = tmp_path / "encounter.png"
    cv2.imwrite(str(path), img)
    assert C.classify_screen(str(path)) == C.ENCOUNTER


def test_profile_only_when_caption_but_no_bars(tmp_path):
    img = _blank()
    y0, y1 = int(2796 * 0.905), int(2796 * 0.985)
    rng = np.random.default_rng(0)
    img[y0:y1, :] = rng.integers(0, 255, size=(y1 - y0, 1290, 3), dtype=np.uint8)
    path = tmp_path / "profile.png"
    cv2.imwrite(str(path), img)
    assert C.classify_screen(str(path)) == C.PROFILE_ONLY


def test_profile_appraisal_when_caption_and_bars(tmp_path):
    img = _blank()
    h, w = 2796, 1290
    y0, y1 = int(h * 0.905), int(h * 0.985)
    rng = np.random.default_rng(0)
    img[y0:y1, :] = rng.integers(0, 255, size=(y1 - y0, w, 3), dtype=np.uint8)

    x0, x1 = int(w * 0.1163), int(w * 0.4690)
    for y0f, y1f in [(0.7676, 0.7761), (0.8115, 0.8208), (0.8559, 0.8645)]:
        by0, by1 = int(h * y0f), int(h * y1f)
        half = (x0 + x1) // 2
        img[by0:by1, x0:half] = (230, 170, 100)
        img[by0:by1, half:x1] = (220, 220, 220)

    path = tmp_path / "profile_appraisal.png"
    cv2.imwrite(str(path), img)
    assert C.classify_screen(str(path)) == C.PROFILE_APPRAISAL
