"""3-way screen type classification: PROFILE+APPRAISAL / PROFILE / ENCOUNTER.

Pixel heuristics only, no ML. Lazy-imports cv2 so importing this module has
no cost when the skill isn't triggered.
"""

PROFILE_APPRAISAL = "profile_appraisal"
PROFILE_ONLY = "profile_only"
ENCOUNTER = "encounter"


def _appraisal_bars_present(gray, h, w):
    """Check the three bar-track rows (§4.2) for a mix of filled/grey pixels."""
    rows = [
        (0.7676, 0.7761),
        (0.8115, 0.8208),
        (0.8559, 0.8645),
    ]
    x0, x1 = int(w * 0.1163), int(w * 0.4690)
    hits = 0
    for y0f, y1f in rows:
        y0, y1 = int(h * y0f), int(h * y1f)
        band = gray[y0:y1, x0:x1]
        if band.size == 0:
            continue
        # A bar track has meaningful pixel variance (filled vs grey segments);
        # a blank area of background does not.
        if band.std() > 8:
            hits += 1
    return hits >= 2


def classify_screen(image_path):
    import cv2

    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"could not read image: {image_path}")
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Encounter screens have their name+CP banner somewhere in the upper-middle
    # band and no bottom caption text block; profile screens have a caption
    # band near the very bottom (y 0.905-0.985) that's mostly non-white.
    caption_y0, caption_y1 = int(h * 0.905), int(h * 0.985)
    caption_band = gray[caption_y0:caption_y1, int(w * 0.02):int(w * 0.98)]
    has_caption = caption_band.size > 0 and caption_band.std() > 10

    if not has_caption:
        return ENCOUNTER

    if _appraisal_bars_present(gray, h, w):
        return PROFILE_APPRAISAL
    return PROFILE_ONLY
