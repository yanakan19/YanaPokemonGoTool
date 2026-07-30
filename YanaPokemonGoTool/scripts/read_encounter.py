"""Read an encounter (pre-catch) screenshot: locate the moving name+CP banner."""
import re

CP_RE = re.compile(r"cp\s*(\d{2,5})", re.IGNORECASE)
NAME_CP_RE = re.compile(r"([A-Za-z][A-Za-z:'\.\- ]*?)\s*cp\s*(\d{2,5})", re.IGNORECASE)

WEATHER_ICONS = (
    "clear", "rain", "partly_cloudy", "cloudy", "windy", "snow", "fog",
)


class ReadError(Exception):
    pass


def locate_banner(img):
    """Find the name+CP banner within the band it never leaves (§5.1). Returns
    (x, y, w, h) in full-image coordinates, or raises ReadError."""
    import cv2
    import numpy as np

    h, w = img.shape[:2]
    y0, y1 = int(h * 0.08), int(h * 0.60)
    roi = img[y0:y1, :]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, th = cv2.threshold(gray, 205, 255, cv2.THRESH_BINARY)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (160, 11))
    mask = cv2.morphologyEx(th, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates = []
    for c in contours:
        x, y, cw, ch = cv2.boundingRect(c)
        if cw > 380 and 35 < ch < 130 and cw / max(ch, 1) > 5:
            candidates.append((x, y, cw, ch))

    if not candidates:
        raise ReadError("could not locate the name/CP banner in the encounter band")

    candidates.sort(key=lambda b: b[2] * b[3], reverse=True)
    x, y, cw, ch = candidates[0]
    return (x, y + y0, cw, ch)


def ocr_banner(image_path):
    import cv2
    import pytesseract

    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"could not read image: {image_path}")

    x, y, w, h = locate_banner(img)
    pad = 16
    y0, y1 = max(0, y - pad), y + h + pad
    x0, x1 = max(0, x - pad), x + w + pad
    crop = img[y0:y1, x0:x1]

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=2.5, fy=2.5, interpolation=cv2.INTER_CUBIC)
    _, th = cv2.threshold(gray, 190, 255, cv2.THRESH_BINARY_INV)

    text = pytesseract.image_to_string(th, config="--psm 7")
    m = NAME_CP_RE.search(text)
    if not m:
        raise ReadError(f"could not parse name/CP from banner OCR text: {text!r}")
    name = m.group(1).strip()
    cp = int(m.group(2))
    return name, cp, (x, y, w, h)


def detect_weather_boost(image_path, banner_bbox, icon_templates=None):
    """Template-match a weather icon anchored to the banner's top-right corner.

    icon_templates: optional dict[name -> np.ndarray] of pre-loaded templates.
    Returns the matched weather name, or None if no template set is supplied
    or no match clears the confidence threshold.
    """
    if not icon_templates:
        return None

    import cv2

    img = cv2.imread(image_path)
    x, y, w, h = banner_bbox
    box_size = int(h * 1.2)
    icon_x0 = x + w
    icon_y0 = max(0, y - box_size // 2)
    icon = img[icon_y0:icon_y0 + box_size, icon_x0:icon_x0 + box_size]
    if icon.size == 0:
        return None

    gray_icon = cv2.cvtColor(icon, cv2.COLOR_BGR2GRAY)
    best_name, best_score = None, -1.0
    for name, template in icon_templates.items():
        t = cv2.resize(template, (gray_icon.shape[1], gray_icon.shape[0]))
        res = cv2.matchTemplate(gray_icon, t, cv2.TM_CCOEFF_NORMED)
        score = res.max()
        if score > best_score:
            best_name, best_score = name, score

    if best_score >= 0.55:
        return best_name
    return None


def read_encounter_screenshot(image_path, icon_templates=None):
    name, cp, bbox = ocr_banner(image_path)
    weather = detect_weather_boost(image_path, bbox, icon_templates=icon_templates)
    return {"species": name, "cp": cp, "weather_boost": weather, "banner_bbox": bbox}
