"""Read a profile screenshot: species (caption), CP/HP (OCR), IVs (bar pixels)."""
import math
import re

REGIONS = {
    "cp": (0.055, 0.090, 0.20, 0.80),
    "nickname": (0.418, 0.448, 0.25, 0.75),
    # Widened from the nominal (0.470, 0.500) -- that band only caught the top
    # sliver of the "X / Y HP" text on every real fixture tested, which fed
    # OCR a half-cut glyph and produced consistently wrong digits.
    "hp": (0.44, 0.53, 0.25, 0.75),
    # y0 starts above the nominal 2-line caption band -- a long location name
    # (e.g. "Gillingham, England, United Kingdom") wraps the caption to 3
    # lines, which pushes the first line up past 0.905 and truncates "This
    # <species> was caught on..." if the crop starts there.
    "caption": (0.86, 0.985, 0.02, 0.98),
}

BAR_TRACK_X = (0.1163, 0.4690)
# Seed band only -- the bars box as a whole shifts vertically depending on
# whether a Dynamax-eligibility row is present above it, so these fractions
# are NOT used to sample a fixed row directly (see _locate_bar_rows).
BAR_ROWS = {
    "attack": (0.7676, 0.7761),
    "defense": (0.8115, 0.8208),
    "hp": (0.8559, 0.8645),
}
BAR_SEARCH_BAND = (0.60, 0.95)
BAR_ORDER = ("attack", "defense", "hp")

CAPTION_RE = re.compile(r"This\s+([A-Za-z:'\.\- ]+?)\s+was caught", re.IGNORECASE)
CP_RE = re.compile(r"cp\s*(\d{2,5})", re.IGNORECASE)

MAX_BAR_ERROR = 0.20


class ReadError(Exception):
    pass


def _crop(img, y0f, y1f, x0f, x1f):
    h, w = img.shape[:2]
    return img[int(h * y0f):int(h * y1f), int(w * x0f):int(w * x1f)]


def _is_filled(pixel):
    r, g, b = int(pixel[2]), int(pixel[1]), int(pixel[0])
    filled_orange = r > 225 and 140 < g < 205 and b < 130
    filled_red = r > 215 and 105 < g < 165 and 105 < b < 170
    return filled_orange or filled_red


def _is_unfilled_grey(pixel):
    r, g, b = int(pixel[2]), int(pixel[1]), int(pixel[0])
    return abs(r - g) < 8 and abs(g - b) < 8 and 200 < r < 240


def _row_recognised_fraction(img, y, x0, x1):
    row = img[y, x0:x1]
    filled = sum(1 for px in row if _is_filled(px))
    unfilled = sum(1 for px in row if _is_unfilled_grey(px))
    track_width = x1 - x0
    if track_width == 0:
        return 0.0, 0, 0
    return (filled + unfilled) / track_width, filled, unfilled


def locate_bar_rows(img):
    """Find the y-centre of the three appraisal bar rows by scanning a wide
    band for rows whose track is mostly filled/grey pixels, rather than
    trusting a fixed fraction -- the whole bars box shifts vertically by
    whether a Dynamax-eligibility row is present above it on the card."""
    h, w = img.shape[:2]
    x0, x1 = int(w * BAR_TRACK_X[0]), int(w * BAR_TRACK_X[1])
    y_start, y_end = int(h * BAR_SEARCH_BAND[0]), int(h * BAR_SEARCH_BAND[1])

    hits = []
    for y in range(y_start, y_end):
        frac, _, _ = _row_recognised_fraction(img, y, x0, x1)
        hits.append(frac >= 0.5)

    # Cluster consecutive (allowing tiny 2px antialiasing gaps) hit rows.
    clusters = []
    cur = []
    gap = 0
    for i, is_hit in enumerate(hits):
        y = y_start + i
        if is_hit:
            cur.append(y)
            gap = 0
        elif cur:
            gap += 1
            if gap > 2:
                clusters.append(cur)
                cur = []
                gap = 0
    if cur:
        clusters.append(cur)

    # Drop slivers (antialiasing noise) too short to be a real bar row.
    clusters = [c for c in clusters if len(c) >= 5]

    if len(clusters) != 3:
        raise ReadError(
            f"expected 3 appraisal bar rows in the search band, found {len(clusters)} "
            "-- either appraisal isn't open, or the screenshot was taken before the "
            "bars finished animating/rendering in (they fade/slide in on screen open). "
            "Wait a moment after opening the profile screen and retake the screenshot."
        )

    centres = [c[len(c) // 2] for c in clusters]
    return dict(zip(BAR_ORDER, centres))  # top-to-bottom == Attack, Defense, HP


def measure_bar_fraction(img, row_key, row_centres):
    x0f, x1f = BAR_TRACK_X
    h, w = img.shape[:2]
    x0, x1 = int(w * x0f), int(w * x1f)
    yc = row_centres[row_key]

    frac, filled, unfilled = _row_recognised_fraction(img, yc, x0, x1)
    total = filled + unfilled
    track_width = x1 - x0
    if track_width == 0 or frac < 0.5:
        raise ReadError(
            f"bar row '{row_key}' only recognised {total}/{track_width} track pixels "
            "-- crop is likely misaligned, or the bar hadn't finished rendering in "
            "yet when the screenshot was taken. Retake after the appraisal screen "
            "has fully settled."
        )
    return filled / total


def fraction_to_iv(fraction):
    exact = fraction * 15
    rounded = math.floor(exact + 0.5)
    rounded = max(0, min(15, rounded))
    nearest_fifteenth = rounded / 15
    if abs(fraction - nearest_fifteenth) > MAX_BAR_ERROR:
        raise ReadError(
            f"bar fraction {fraction:.4f} is more than {MAX_BAR_ERROR} from "
            f"the nearest fifteenth ({nearest_fifteenth:.4f}) -- crop likely misaligned"
        )
    return rounded


def read_ivs_from_bars(img):
    row_centres = locate_bar_rows(img)
    fractions = {k: measure_bar_fraction(img, k, row_centres) for k in BAR_ORDER}
    ivs = {k: fraction_to_iv(v) for k, v in fractions.items()}
    return ivs["attack"], ivs["defense"], ivs["hp"], fractions


def compute_iv_percent(iv_a, iv_d, iv_s):
    total = iv_a + iv_d + iv_s
    return int(math.floor(total / 45 * 100 + 0.5))


def _binarisations(gray):
    import cv2

    variants = []
    _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    variants.append(otsu)
    _, otsu_inv = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    variants.append(otsu_inv)
    for t in (150, 190, 215):
        _, th = cv2.threshold(gray, t, 255, cv2.THRESH_BINARY)
        variants.append(th)
        _, th_inv = cv2.threshold(gray, t, 255, cv2.THRESH_BINARY_INV)
        variants.append(th_inv)
    # White-on-near-white text (e.g. a pale habitat background) defeats every
    # fixed/Otsu threshold above -- adaptive thresholding picks up the local
    # stroke contrast instead of the (nearly identical) global brightness.
    adaptive = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 51, -5
    )
    variants.append(adaptive)
    adaptive_inv = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 51, -5
    )
    variants.append(adaptive_inv)
    return [_strip_edge_artifacts(v) for v in variants]


def _strip_edge_artifacts(binary_img):
    """Zero out connected components that are thin diagonal streaks (e.g. the
    star-bubble's curved edge bleeding into a text crop) rather than compact
    glyph blobs. A diagonal line's bounding box can be almost as wide as it is
    tall, so width/height alone doesn't separate it from a glyph -- but its
    fill density (area / bbox area) is much lower than an actual character
    stroke, and it spans nearly the full crop height."""
    import cv2

    n, labels, stats, _ = cv2.connectedComponentsWithStats(binary_img, connectivity=8)
    cleaned = binary_img.copy()
    crop_h = binary_img.shape[0]
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if h == 0 or w == 0:
            continue
        density = area / (w * h)
        if h > crop_h * 0.85 and density < 0.2:
            cleaned[labels == i] = 0
    return cleaned


DIGIT_WHITELIST_CONFIG = "--psm 7 -c tessedit_char_whitelist=0123456789"


def ocr_cp(img):
    import cv2
    import pytesseract
    from collections import Counter

    crop = _crop(img, *REGIONS["cp"])
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=2.5, fy=2.5, interpolation=cv2.INTER_CUBIC)

    candidates = []
    for variant in _binarisations(gray):
        # The "CP" label is a fixed, known part of the UI -- restricting the
        # OCR pass to digits only removes the letter noise that otherwise
        # confuses individual digits (e.g. a "7" misread as "/" next to "CP").
        text = pytesseract.image_to_string(variant, config=DIGIT_WHITELIST_CONFIG)
        digits = re.sub(r"\D", "", text)
        if 2 <= len(digits) <= 5:
            candidates.append(digits)

    if not candidates:
        raise ReadError(
            "could not OCR CP after multi-binarisation -- if the screenshot was "
            "taken right as the profile screen opened, the CP number may still "
            "have been counting up/fading in. Retake once it's settled."
        )

    # A stray Pokemon-model edge (spikes, tails, sparkle effects) crossing the
    # digits can add a spurious extra digit in one or two binarisations, but
    # rarely in most of them -- take the value most binarisations agree on
    # rather than the first one found.
    winner, _ = Counter(candidates).most_common(1)[0]
    return int(winner)


def ocr_caption(img):
    import cv2
    import pytesseract

    crop = _crop(img, *REGIONS["caption"])
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    _, th = cv2.threshold(gray, 170, 255, cv2.THRESH_BINARY_INV)
    text = pytesseract.image_to_string(th, config="--psm 6")
    m = CAPTION_RE.search(text)
    if not m:
        raise ReadError(f"caption regex did not match OCR text: {text!r}")
    return m.group(1).strip()


HP_WHITELIST_CONFIG = "--psm 7 -c tessedit_char_whitelist=0123456789/"


def ocr_hp(img):
    """Cross-check only -- HP OCR is off the critical path (solver resolves level)."""
    import cv2
    import pytesseract
    from collections import Counter

    crop = _crop(img, *REGIONS["hp"])
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=2.5, fy=2.5, interpolation=cv2.INTER_CUBIC)

    candidates = []
    for variant in _binarisations(gray):
        # The field reads "current / max HP" -- keep the slash in the
        # whitelist so the two numbers don't fuse into one digit run.
        text = pytesseract.image_to_string(variant, config=HP_WHITELIST_CONFIG)
        numbers = re.findall(r"\d+", text)
        if numbers:
            candidates.append(numbers[0])

    if not candidates:
        return None
    winner, _ = Counter(candidates).most_common(1)[0]
    return int(winner)


def read_profile_screenshot(image_path):
    import cv2

    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"could not read image: {image_path}")

    species = ocr_caption(img)
    cp = ocr_cp(img)
    iv_a, iv_d, iv_s, fractions = read_ivs_from_bars(img)
    iv_pct = compute_iv_percent(iv_a, iv_d, iv_s)
    try:
        hp = ocr_hp(img)
    except Exception:
        hp = None

    return {
        "species": species,
        "cp": cp,
        "hp": hp,
        "iv_a": iv_a,
        "iv_d": iv_d,
        "iv_s": iv_s,
        "iv_pct": iv_pct,
        "bar_fractions": fractions,
    }
