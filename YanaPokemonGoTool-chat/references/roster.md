# Roster sort/filter contract

The roster is the running markdown table of every Pokemon scanned in this conversation
(see SKILL.md). This file defines exactly how to sort, filter, and respond when the user
asks to see it -- follow it precisely, these are specific defaults the user requested.

## Default view

When the user asks to see their Pokemon with no further qualifier ("show my pokemon",
"what have I scanned", "list them"):

- Sort by **CP, high to low**.
- Show the full roster, unfiltered.

## Sorting

Recognise requests for either sort key, in either direction:

| User says (examples) | Sort key | Direction |
|---|---|---|
| "sort by CP" / "highest CP" / no qualifier | CP | high to low (default) |
| "sort by CP low to high" / "lowest CP first" / "worst CP" | CP | low to high |
| "sort by IV" / "best IV" / "highest IV%" | IV% | high to low (default) |
| "sort by IV low to high" / "worst IV first" | IV% | low to high |

Default direction for **both** keys is high to low unless the user says otherwise
("low to high", "worst first", "lowest first", "ascending" all mean low to high).

Ties: when sorting by CP, break ties by IV% (high to low). When sorting by IV%, break
ties by CP (high to low).

## Filtering

Recognise an IV% threshold in phrasing like "90+ IV", "IV over 90", "at least 90%",
"90% or better", "hundos" (== exactly 100%).

The in-game appraisal badge is a **3-star** system (not 5). Confirmed against 5 real
screenshots spanning 78-93% IV, all of which showed the same 3-filled-star badge:

| Stars | IV% |
|---|---|
| 3 (best) | 66-100% |
| 2 | 49-65% |
| 1 | 0-48% |

The 66% and 49% boundaries are the widely-documented community values and are consistent
with every screenshot checked, but no screenshot below 66% was available to directly
confirm the 1-star/2-star split -- if a filter by "1 star" or "2 star" ever looks wrong
against what the user's app actually shows, say so and ask them to confirm the boundary
rather than silently trusting it. "3 star" and "3-star or better" filtering can be
applied with full confidence (>=66%).

When a filter is applied:
- Default sort **within the filtered set is IV%, high to low**, unless the user also
  specified a CP sort or a direction, in which case honour that instead.
- State the filter and the count in the reply, e.g. "3 Pokemon at 90%+ IV:".
- If nothing matches, say so plainly rather than showing an empty table silently.

## Combining sort + filter

A request can specify both, e.g. "show my 90+ IV pokemon by CP low to high" -- filter
first, then apply the requested sort/direction to the filtered set.

## Output format

Always a markdown table, columns in this order:

```
| Species | CP | IV% | IV (A/D/S) | HP | Level |
```

Do not add extra columns (star rating, date scanned, etc.) unless the user asks -- keep
it to what was specified.
