# Calibration constants (measured at 1290x2796, iPhone 15/16 Pro Max)

All regions are stored as fractions of image width/height so they're resolution-independent.
If a device's status bar height differs enough to shift these, detect the bars by colour
(see below) and use the fractions only to seed the search band.

## OCR regions (fractions of W x H)

| Field | y range | x range | psm | Notes |
|---|---|---|---|---|
| CP | 0.055 - 0.090 | 0.20 - 0.80 | 7 | white on arbitrary sky background -- needs multi-binarisation |
| Nickname | 0.418 - 0.448 | 0.25 - 0.75 | 7 | optional, not used for species |
| HP | 0.44 - 0.53 | 0.25 - 0.75 | 7 | cross-check only, but see below -- widened from the original 0.470-0.500 |
| Caption | 0.86 - 0.985 | 0.02 - 0.98 | 6 | species source -- the only trustworthy one; widened from 0.905 (see below) |

Multi-binarisation: try Otsu (both polarities) plus fixed thresholds 150/190/215 (both
polarities), upscale 2.5x cubic first, **plus adaptive thresholding** (Gaussian, block 51,
C=-5, both polarities) -- fixed/Otsu thresholds all fail when the CP text sits on a
near-white background (text and background both >200), which adaptive thresholding (local
contrast, not global brightness) handles. Real fixture example: `CP3750` on a pale beige
habitat background produced zero matches from fixed/Otsu thresholds; adaptive recovered it.

**Digit-only OCR whitelist.** Both CP and HP OCR should restrict Tesseract to
`0123456789` (`tessedit_char_whitelist`) rather than reading `"CP"`/`"HP"` text too --
letter noise next to a digit run causes misreads (a `7` next to `P` was read as `/`).
Since the label text is fixed UI chrome, there's nothing lost by not OCR'ing it.

**Majority vote across binarisations, not first-match.** A Pokemon model's spikes/tail/
sparkle effects crossing the CP digits can inject a spurious extra digit into one or two
of the ~10 binarisation variants (e.g. `2949` misread as `29490` in exactly the
binarisations where a crystal spike grazed the last digit). Collect a candidate from
every variant that plausibly parses (2-5 digits) and take the most common value, not the
first one that parses -- the first-match approach silently returned the wrong 5-digit
reading in this fixture.

**Edge-artifact stripping.** The circular star-bubble icon (top-right of the CP arc) can
bleed a curved edge into the CP crop when a wider crop is needed for longer CP numbers.
The edge's bounding box can be nearly as wide as it is tall (since it's diagonal), so
width/height ratio alone doesn't distinguish it from a glyph -- but its *fill density*
(foreground pixels / bounding-box area) is much lower than an actual character stroke.
Strip any connected component with `height > 0.85 * crop_height and density < 0.2` before
OCR (`_strip_edge_artifacts` in `read_profile.py`).

**Caption and HP crop regions were both too narrow in the original calibration.** The HP
region only ever captured the *top sliver* of "X / Y HP" on every real fixture tested,
silently feeding OCR a half-cut glyph -- widen to 0.44-0.53. The caption region missed the
first line ("This &lt;species&gt; was caught on...") whenever a long location name wraps
the caption to 3 lines instead of 2, since the extra line pushes the first line up past
0.905 -- widen the top of the band to 0.86.

## Appraisal bars -> exact IVs

```
bar track x: 0.1163 -> 0.4690
Attack  row y: 0.7676 - 0.7761  (centre 0.7719)   -- SEED BAND ONLY, see below
Defense row y: 0.8115 - 0.8208  (centre 0.8161)   -- SEED BAND ONLY, see below
HP      row y: 0.8559 - 0.8645  (centre 0.8602)   -- SEED BAND ONLY, see below
```

**These fixed y-fractions do not hold universally -- the whole bars box shifts
vertically** depending on whether a Dynamax-eligibility row is present above it on the
card (confirmed on a real fixture: a single-type Pokemon with no such row had its bars
box sitting ~85px/~0.03 of image height higher than the calibration source). Don't
sample these fixed rows directly. Instead (`locate_bar_rows` in `read_profile.py`): scan
a wide band (0.60-0.95 of height) for rows whose track is >=50% recognised filled/grey
pixels, cluster consecutive hit-rows (bridging gaps up to 2px for antialiasing), drop
slivers under 5px tall, and require exactly 3 clusters -- their top-to-bottom order is
always Attack/Defense/HP. Raise (don't guess) if the count isn't exactly 3; this also
catches the "screenshot taken before the bars finished animating in" case, which
otherwise produces a partially-rendered bar row.

Colour masks (classify by "filled vs grey", never by hue -- the leader highlights the best
stat in red, the rest in orange):

```python
filled_orange = (r>225) & (140<g<205) & (b<130)
filled_red    = (r>215) & (105<g<165) & (105<b<170)
unfilled_grey = (abs(r-g)<8) & (abs(g-b)<8) & (200<r<240)
```

Rounding rule (mandatory, two separate roundings in this order):

1. Each stat IV = `floor(fraction * 15 + 0.5)`, clamped to 0-15. Never report a fractional IV.
2. IV% = `floor((iv_a + iv_d + iv_s) / 45 * 100 + 0.5)`, computed from the already-rounded
   integers -- never from the raw pixel fractions directly.

Reject and re-measure (raise, don't guess) if any measured fraction is more than 0.20 away
from the nearest fifteenth -- that means the bar crop is misaligned.

## Species: caption only, never the candy label or nickname

Regex: `r'This\s+([A-Za-z:\'\.\- ]+?)\s+was caught'` on the caption band, `--psm 6`,
inverted threshold ~170.

The candy counter is always named after the base form of an evolution line (a Slaking's
candy is labelled "Slakoth Candy"), and the nickname is arbitrary user text. Both are traps.
The bottom caption is generated by the game from the true species ID and is the only field
safe to key off. See `references/limits.md` for the regression case (IMG_2415: Slaking,
nicknamed "LazyGuy", candy labelled "Slakoth Candy").

## Level: solve it, don't read the arc

Once IVs are known from the bars, brute-force all half-levels 1-51 for the one whose
computed CP matches the OCR'd CP. This has been collision-audited: 0 ambiguous CPs found
across the validated fixtures. Use HP only as a tie-break if the solver ever returns more
than one candidate level.

## Encounter banner detection

The name+CP banner moves, so never crop a fixed box for it:

```python
roi = im[int(H*0.08):int(H*0.60), :]
_, th = threshold(gray, 205, 255, THRESH_BINARY)
mask = morphologyEx(th, MORPH_CLOSE, rect_kernel(160, 11))  # width 160 matters
# keep contours with w > 380, 35 < h < 130, aspect > 5; take the largest
```

A kernel narrower than ~160px splits the name and CP into separate contours. Don't OCR the
full frame -- it's an order of magnitude slower and can fail to find the CP at all.

## When the bar-measured IVs don't reconcile with CP/HP

CP and HP are both plain digit OCR (reliable once the digit-whitelist + majority-vote
approach above parses at all); bar pixel-reading is the noisier signal of the two. On a
real fixture (a shiny Dialga), the Defense bar read as uniformly, unambiguously 100%
filled by every pixel sampled across its full width -- yet **no IV combination with
defense=15 reproduces that Pokemon's CP and HP at any level**, for either of Dialga's two
known forms. The reconciled answer (defense=11, matching CP+HP exactly, with attack and
HP-IV both matching the bar read) was only reachable by treating CP+HP as authoritative
and the bars as a tiebreak among CP(+HP)-consistent candidates, not the other way round.

`scan_profile` in `scan.py` implements this: solve for all (level, IVs) combos matching
CP (and HP, if OCR'd) exactly; if the bar-read IVs land on exactly one of them, use it
directly; if not, fall back to the CP(+HP)-consistent combo closest to the bar reading
(by summed absolute difference) and surface a `note` explaining which stat was
overridden, rather than crashing. Only refuse outright if even the closest consistent
combo is implausibly far off (see `BAR_MISMATCH_MAX_DISTANCE`) -- that's more likely a
wrong species/form (forms share the caption text but not base stats) than a bar misread.

## Star rating is a 3-star system, not 5

Confirmed against 5 real screenshots spanning 78-93% IV -- all showed the same 3-filled
gold star badge. `solver.star_rating` uses 66-100%=3, 49-65%=2, 0-48%=1. The 66%/49%
boundaries match widely-documented community values and are consistent with every
fixture on hand, but no fixture below 66% was available to directly confirm the
1-star/2-star split.
