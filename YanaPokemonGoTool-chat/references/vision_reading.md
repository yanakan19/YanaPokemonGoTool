# Reading a screenshot with vision only (no pixel math)

There's no OpenCV/Tesseract available in this mode -- everything below is done by
looking at the image directly, the same way a person would.

## Species (mandatory source: the caption)

Near the very bottom of a profile screen there's a small line of grey text: "This
___ was caught on [date] around [location]." That blank is the true species. Use it
every time, even when:

- The large text next to the pencil icon is a nickname (arbitrary, user-set).
- The candy counter is labelled after the *base* species of the evolution line (e.g. a
  fully-evolved Slaking's candy still says "Slakoth Candy", Metagross's says "Beldum
  Candy"). Never read the species off the candy label.

If the caption is scrolled off-screen or in a non-English locale, say so rather than
guessing from the sprite or nickname.

## CP and HP

Read the numbers directly -- they're large, high-contrast, purpose-built UI text. No
special handling needed beyond normal careful reading (double-check digit-by-digit on
a 4-5 digit CP; these numbers matter for the exact-match check against the solver).

## Appraisal bars -> IVs

Each of the three bars (Attack, Defense, HP, in that order) is a track that reads as 3
visible clusters, each cluster representing 5 of the bar's 15 total units. Count how
many of the 15 units are filled (coloured -- orange normally, red for whichever stat the
team leader calls out as best) versus grey/unfilled. This is a **discrete pip count**,
not a percentage estimate -- report a whole number 0-15 per bar, and say so if the image
is too small/blurry to count confidently rather than guessing.

Do not use the star badge under CP as a stand-in for measuring the bars -- it only
narrows IV% to a wide band and the appraisal bars give the exact number directly.

The bars box's vertical position on the card **is not fixed** -- it sits noticeably
higher when the Pokemon has no second type-icon row (single-type species) or no
Dynamax-eligibility row above it, and lower otherwise. Don't assume a fixed position on
the screen; locate the "Attack"/"Defense"/"HP" labels visually each time and read the
bars directly below whichever label you find, rather than a remembered pixel position
from an earlier scan in this conversation.

## When the screenshot was taken too early (mid-load)

The appraisal bars animate in (fade/slide) when the profile screen opens, and the CP
number can still be counting up for a moment too. If a bar looks like it's mid-animation
(faded, partially rendered, or one bar missing/blank while the other two look normal),
or the CP number looks like it's still transitioning, say so explicitly and ask for a
screenshot taken a beat later rather than counting pips on an unsettled UI -- a
mid-animation read is exactly the kind of confident-but-wrong result this skill exists
to avoid.

## When the bar count doesn't reconcile with CP/HP

Once you've counted the three bars and solved for a level, always forward-check: does
`forwardSolve` with that level and your three counted IVs reproduce the OCR'd CP and HP
exactly? If not, don't force it -- CP and HP are plain numbers (much easier to read
correctly than three separate pip counts), so when they disagree with the bars, trust
CP/HP and re-run `reverseSolve` (unconstrained by your pip counts) filtered by CP and HP
together to find the consistent IV combo closest to what you counted. Tell the user
which stat you had to override and why (e.g. "Defense bar looked fully filled, but only
12/15 defense reproduces this CP+HP -- one of the three segments may have been hard to
tell apart from a full bar at this image's resolution").

## Level

Never estimate level from the arc/dial angle by eye -- it's imprecise. Always solve for
it: once you have the three IVs from the bars, use `references/solver.js`'s
`reverseSolve` (filtered down to your counted IVs) to find the one level whose CP
matches. This is exact, not an estimate, as long as your IV counts and CP reading were
both correct -- which the CP/HP round-trip check in SKILL.md verifies.

## Encounter banner

On a pre-catch encounter screen, the name+CP banner floats and can be positioned
anywhere in the upper-middle part of the screen (it's not fixed like the profile
screen's regions). Locate it first, then read the species name and CP off it. A small
weather icon may sit near the banner -- note it if a boost-relevant weather (e.g. Windy
for Psychic-boosted, Sunny/Clear for Fire, etc.) is shown, since it changes the
level/IV-floor range per `references/limits.md`.
