# Prompt 19 — Polish

Everything in Prompt 18 is done and green: **45 passed / 0 failed** at `1075b241a`, Pages deploy
succeeded, live at https://yieldchaser.github.io/Shipping/.

I then browsed the live site — all 12 tabs, sub-tabs, scrolled each one. Programmatically it is
clean: **0 console errors, 0 failed requests, 0 dead charts, 0 empty states, 0 clipped text nodes,
no horizontal scroll on any tab.** Offshore is fully visible in the nav again.

What follows is what a *person* sees that no test asserts. None of it is a test failure. Do not
change any test to cover these unless the fix genuinely needs it.

---

## P-1 · DONE — header ships no longer cover the wordmark

**The ships are a deliberate design choice and they stay.** Only the collision was a bug: they
sailed across the "SHIPPING INTELLIGENCE" text and made it unreadable. Fixed by pinning the ship
lane to `z-index: 0` and giving the wordmark an opaque `var(--card)` chip at `z-index: 3`, so the
ships pass behind it. Do not remove the ships, and do not reintroduce the overlap.

## P-2 · The quote ticker — keep or cut is the owner's call

`index.html:11029` — a 25-entry `var quotes` ticker under the nav. It includes **four Captain Jack
Sparrow quotes**, "Why is the rum always gone?", and pirate-raid trivia ("The Ganj-i-Sawai, 1695 —
£600,000 in gold & silver seized on the Indian Ocean. The richest pirate raid in history").

The ticker is part of the same deliberate aesthetic as the ships, so **do not delete it without
being asked.** One thing is a real defect regardless of taste: it scrolls text off both edges
mid-word, so quotes are frequently unreadable at the viewport margins. Fix the marquee so each
quote enters and leaves whole.

## P-3 · Tracking: Port Universe shows zero rows out of 2,065

Tracking tab, left panel, "Port Universe (2,065)" sub-tab. Default state on load:

```
Port | Class Mix | Calls (YTD)
      No ports match the current search.
      0 of 0 universe ports
```

Filters are at their defaults — "All Universe Ports" and "Any calls" — and the tab's own label says
2,065. So the default filter state matches nothing. Find why the default query returns empty and
make the unfiltered view list all 2,065.

This passed every test because the string "No ports match the current search" is a legitimate empty
state; nothing checks that it is *wrong* to be empty here.

## P-4 · Tracking: map overlays stack on top of each other

The map's "SECTOR HIGHLIGHT (PORTWATCH CALLS)" heading is covered by the "1977 ports" pill sitting
over it. The class chips (Tankers 372,235 · Dry Bulk 182,007 · Container 313,272 · Gen Cargo
250,665 · RoRo 69,023) sit on top of the map's own numeric labels, and a "Display Fleet Live"
checkbox is half hidden behind them. The legend box at bottom-left also overlaps the map.

Give the overlay a single panel with its own background and a defined stacking order, or move the
chips out of the map into the strip above it.

## P-5 · Offshore: year-on-year figures look wrong

All four segment tiles read implausibly:

| Segment | Rate | YoY |
|---|---|---|
| Large AHTS (>22,000 BHP) | £96,015/d | **+499.2%** |
| Medium AHTS (<22,000 BHP) | £62,332/d | **+292.1%** |
| Large PSV (>900 m²) | £21,445/d | **+261.9%** |
| Medium PSV (<900 m²) | £18,000/d | **+280.0%** |

Four segments up three-to-five-fold in a year is not a market, it is a calculation. Check the base
period: most likely it compares against a month with near-zero or missing data, or against a
different unit. The chart underneath shows 2025 rates in the £20k–£60k band, which is nothing like
a 5x rise. **Verify against the Seabrokers archive before changing any number**, and if the
YoY base is genuinely absent, show an em-dash rather than a computed figure.

## P-6 · Offshore: broken glyph on the PDF links

The "Seabreeze Intelligence Publications" cards render a mojibake character where a download icon
should be, next to each report's size. Encoding or a missing glyph — replace with a plain text
link ("Download PDF") rather than an icon font.

## P-7 · Broker Desk: the Braemar strip is honest now but still stale

It correctly says **"As of 10 Sep 2026"** instead of the old "Live GraphQL Feed" — that is the
right fix and it should stay. But the header says "Data as of 2026-09-11" and the strip is two days
behind, because that source still has no scheduled writer. Section A1 asked for it either to
refresh on a schedule or stop claiming to be live; it did the second half only. Wire the fetcher
into one of the new sync workflows.

## P-8 · Broker Desk: twenty-odd identical green ACTIVE pills

The overview grid badges every tile `ACTIVE` in green. When everything carries the same badge the
badge carries no information, and it is the same visual noise as the old "LIVE …" pills that were
removed. Show the badge only when a series is *not* active, or replace it with the as-of date,
which is the thing a reader actually wants.

## P-9 · Dashboard: the history chart draws past its card

On "CURRENT YEAR VS HISTORICAL YEARS", the 2023 and 2024 series appear to continue past the card's
right border toward the viewport edge. Confirm at 1920 px and clip the plot area to the card.

## P-10 · DONE — signal banner now derives its own base rates

The banner asserted "Since 1991: −1.1% avg fwd 3M BDI vs +7.5% unconditional. Profit taking &
hedging recommended." Recomputed from `bdiy_historical.csv`: −1.14% vs +7.26%, so the numbers were
right — but typed into a template string where nothing would recompute them, and invisible to
`test_no_typed_numbers` because they live inside `<script>`.

`build_views.py` now emits `data/views/signal_base_rates.json` on every build, and the banner reads
it. It also shows median, win rate and sample size, and no longer recommends a trade. Leave it
deriving; do not reintroduce typed statistics into the banner strings.


## P-11 · Broker Desk → S&P & Assets: the parity chart is empty for 29 of 33 vessel classes

"5Y-OLD SECONDHAND VALUE AS % OF NEWBUILD PRICE" (`#fearnAcParity`) renders a 300 px chart with a
legend, a 0%–1% axis and **no line at all** for 29 of the 33 classes in the selector. Measured on
the live site by stepping through every option: only **Kamsarmax, Suezmax, Ultramax and VLCC** draw
anything. VLCC is the default, which is exactly why every test passes — the suite only ever sees
the default value of a `<select>`.

Root cause is in the data, and it is unambiguous. `data/derived/fearnleys_asset_curves.json` keys
each class to a set of tenor series. The ratio needs **both** a `PRICES` (newbuild) leg and a 5-year
leg (`DRY-5`, `WET-5`, `DRY-5-JP`, `DRY-5-CN`) under the *same* class key. Availability:

| Class group | Has `PRICES` | Has a 5y leg | Parity possible |
|---|---|---|---|
| Kamsarmax · Suezmax · Ultramax · VLCC | yes | yes | **yes — these 4 work** |
| 1,900–21,000 TEU · Aframax · LNGC · MGC · Newcastlemax · Product · VLGC | yes | no | no |
| Capesize · Handysize · MR · Aframax / LR2 | no | yes | no |
| every `(Japanese)` / `(Chinese)` variant | no | yes | no |
| Panamax (Japanese) · Panamax (Chinese) | no | no | no |

Two things to do, in this order:

1. **Stop drawing an empty chart.** When a class has no overlap, hide the canvas and show only the
   message that is already there (`no NB+5y overlap for <class>`). A 300 px axis labelled 0%–1%
   with no data looks like a broken chart, which is worse than an honest sentence.
2. **Then go get the missing leg.** Fearnleys publishes newbuild prices for Capesize, Handysize and
   the Panamax family; they are simply not in this file. Extend the fetcher so the classes that
   have a 5y leg also get their own `PRICES`.

**Do not join across bases to manufacture coverage.** Dividing a `DRY-5-JP` (Japanese-built 5-year)
by a generic `PRICES` newbuild is a different-basis ratio and would be a fabricated number wearing a
real one's clothes. Same-class only, or no chart.

## P-12 · Internal series codes are printed in the UI

The S&P & Assets header line reads, verbatim:

```
VLCC · Newbuilding price [PRICES] · 10yr old [WET-10] · 5yr old [WET-5] · Resale [WET-RESALE] · scrap: Tanker scrap (India, $/ldt) [tanker_india]
```

and on the dry side `[DRY-10]`, `[DRY-5]`, `[DRY-10-JP]`, `[DRY-15-JP]`, `[dry_india]`. These are
internal lookup keys from `fearnleys_asset_curves.json`. `test_ui_copy_lint` misses them because
they are not in its banned-term list and they are generated at runtime rather than sitting in
markup.

Drop the bracketed codes from the visible label. If the provenance is worth showing, put the key in
the tooltip, where it answers "where did this come from" without cluttering the header.

## P-13 · Test gap: the suite only ever sees default dropdown values

P-11 sat on the live site through four rounds of green tests because `#fearnAcParity` is only empty
for non-default selections. The UI sweep clicks buttons and sub-tabs; it never changes a `<select>`.

Extend `test_charts_have_data` (or add a sibling) to walk each visible `<select>` through its
options on the panels that have them, and assert no visible canvas ends up with a Chart instance
carrying zero points. This is a strengthening, so it is allowed — but land it **after** P-11, or it
will fail on 29 classes immediately.

## Not a bug — for the record

The "Excel" box that appears over the DEMOLITION SCRAP FLOOR tile in the screenshot is a Windows
taskbar hover tooltip, not part of the page. I searched the DOM for it on the live site and there is
no such element. Nothing to fix.

---

## Rules still in force

Never invent a number. No synthetic series, no placeholder values, no zero-filling — when there is
no data the UI says so. Never weaken a test to make something pass; every change under `tests/`
must be justified in your report. Never `git add -A`. Re-run the suite before and after, and report
before/after for every metric including ones you did not touch:

```bash
python -m pytest tests/test_ui_tabs.py tests/test_loader_contracts.py tests/test_freshness_and_wiring.py -q
```

It must still read **45 passed** when you are done.
