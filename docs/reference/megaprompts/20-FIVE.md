# Prompt 20 — five defects found by hand

All five confirmed by execution against the live build. None is a test failure; the suite is
**45 passed** with every one of these present. Each ends with what the test should have caught.

---

## F-1 · "Realized Pctl" on the SGX FFA forward curve does nothing

`index.html:12746` — `onclick="setFFAComp('dist')"`. Measured on `#ffaForwardChart`:

```
before            : 1 dataset  — Capesize (current), 76 pts
after Realized Pctl: 4 datasets — Capesize (current) 76 pts
                                  Realized Spot Median (P50)   0 pts
                                  Realized Spot P10-P90 Band   0 pts
                                  Realized Spot P10 Lower      0 pts
after "1M ago"     : 2 datasets — Capesize (current) 76, 1M ago 76   <- control, works
```

So `setFFAComp('dist')` builds the three percentile datasets and never fills them. No console
error, no visible change — the button looks inert. Its sibling `1m` populates correctly, so the
plumbing is fine and only the distribution computation is missing or returning empty.

Fix the computation. If the realized-spot history genuinely cannot support a P10/P50/P90 across
tenors, **disable the button and say why in its tooltip** — do not leave three empty datasets
attached to the chart.

## F-2 · Dashboard year overlay is capped at 6 years; 10Y and All do nothing

`#overlayChart`, stepping each range control:

| Button | Series drawn |
|---|---|
| Clear | 2026 |
| 3Y | 2026, 2025, 2024, 2023 |
| 5Y | 2026, 2025, 2024, 2023, 2022, 2021 |
| **10Y** | **same 6 — 2026…2021** |
| **All** | **same 6 — 2026…2021** |

`bdiy_historical.csv` holds **10,515 rows from 1985-01-04**, so 10Y should reach 2016 and All
should reach 1985. The year list the overlay can choose from is being built with a 6-year horizon,
so the wider buttons have nothing further to select.

Build the selectable year set from the series' own span, then have each range pick from it. The
check-boxes above the chart must grow to match.

## F-3 · The Capesize spot line implies continuity it does not have

"LEADING RESTOCKING PRESSURES", blue `Capesize Spot ($/day)` series. The underlying data:

```
getRows('cape')  -> 618 points, first 2022-01-19, last 2026-09-10
largest gap      -> 282 days, 2023-09-04 -> 2024-06-12
points in 2022-01..2023-11 -> 59   (a ~23 month window)
```

Two consequences, both visible on screen. The 282-day hole is bridged by a **single straight
line**, which is the diagonal ramp from roughly $10k to $30k that looks synthetic — it is not data,
it is Chart.js joining two points nine months apart. And the sparse 2022–2023 stretch (one point
per ~12 days) is drawn as long flat segments, so it reads as "Capesize was flat near $10k for
eighteen months", which is false.

`lookupSpot` (`index.html:16574`) also snaps to the nearest value within a 4-day window, which
repeats a value across neighbouring rows and flattens the line further.

Fix: set `spanGaps: false` on that dataset so holes break the line instead of being bridged, and
stop nearest-snapping across gaps — a row with no spot within the window should be `null`, not the
nearest neighbour. A broken line that shows where data is missing is the honest rendering.
**Do not backfill or interpolate the missing nine months.**

## F-4 · BIX "obs 2026-09-04" is our bug, not a stale source

The Bunkers regional-movers table is stamped `obs 2026-09-04`. The data is newer than that:

```
data/bunkers/bix_history.csv -> 3,870 rows, observation_date 2025-09-09 .. 2026-09-09
rows per date: 2026-09-04 (15), 09-07 (15), 09-08 (15), 09-09 (15)   <- complete sets
```

And the harvest log from the 2026-09-10 `Data Expansion Collectors` run confirms it fetched them:

```
BIX history harvest: {"date_max": "2026-09-09", "distinct_obs_dates": 258, "new_keys_added": 15, ...}
```

So three complete trading days (09-07, 09-08, 09-09) sit in the file and are not displayed. The
"latest observation" selection in the front end is picking 09-04 instead of the true max. Find why
— most likely it reads a different, staler artefact (`bunker_bix_macro_benchmarks.json` stops at
09-04) rather than `bix_history.csv`, or it filters to dates present in every index_code.

The displayed `obs` date must be the newest observation actually rendered in that table.

## F-5 · Fleet AIS sector buttons do not filter the map at all

Clicking the sector controls over the tracking map and counting rendered map objects:

```
baseline              : 160 markers
after "Dry Bulk 1,453" : 160 markers
after "Tankers 1,746"  : 160 markers
after "Container 1,238": 160 markers
```

Identical every time. They change the surrounding counts and headline text but repaint nothing on
the map, so today they highlight neither vessels nor ports.

**The intended behaviour is the owner's stated preference and is the better design:** selecting a
sector should narrow the map to that trade — the vessels of that class *and* the ports that serve
it, so the map answers "where does dry bulk actually move" rather than just recolouring a number.
Implement that: filter vessel markers by class, and filter/emphasise port markers by the same
sector using the class mix already present in the port universe rows. Leave unrelated ports drawn
but de-emphasised rather than removing them, so the geography stays legible.

---

## What the tests should have caught, and did not

All five survived a green suite. Add these, and expect them to fail until the fixes land:

1. **Controls must change something.** For each toggle in a control group, snapshot the relevant
   chart's dataset point-counts (or the map's marker count) before and after clicking, and assert
   the state actually changed. That catches F-1 and F-5 directly.
2. **A range control must widen the range.** Assert 10Y yields strictly more series than 5Y, and
   All at least as many as 10Y. Catches F-2.
3. **No chart may bridge a gap larger than its own sampling interval.** For time series, assert
   `spanGaps` is false wherever the source has holes beyond a threshold. Catches F-3.
4. **A displayed as-of date must equal the max date in the data behind it.** Catches F-4, and it is
   the same class of bug as the frozen view layer from Prompt 17.

Rules unchanged: never invent a number, never interpolate across a gap to make a line look
continuous, never weaken a test, stage explicit paths. The suite must still read **45 passed**
plus whatever you add.
