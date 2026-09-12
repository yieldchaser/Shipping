# Prompt 21 — next pass

Supersedes nothing: **`20-FIVE.md` F-1 to F-5 still stand and are part of this run.** Everything
below is additional, all confirmed by execution against the live build. The suite is **45 passed**
with every one of these present, so none is a test failure.

Definition of done is unchanged:

```bash
python -m pytest tests/test_ui_tabs.py tests/test_loader_contracts.py tests/test_freshness_and_wiring.py -q
```

**45 passed / 0 failed**, plus whatever assertions you add. Never invent a number, never weaken a
test, never `git add -A`, commit per item and push at the end of each section.

---

## G-1 · The Braemar strip is on all twelve Broker Desk sub-tabs

Clicking through every sub-tab and testing whether the strip is visible:

```
Overview SHOWN · TC Rates SHOWN · Tanker Routes SHOWN · Dry Routes SHOWN · S&P & Assets SHOWN
LNG Desk SHOWN · LPG Desk SHOWN · Fixtures Tape SHOWN · Series Museum SHOWN · Broker Voice SHOWN
Backtest Lab SHOWN · Newbuilding SHOWN
```

Twelve for twelve. This was raised at the start of this whole effort and never fixed. A forward FFA
strip belongs on **Overview only**; on the other eleven it pushes the actual content of the sub-tab
below the fold. Move it into the Overview panel rather than the desk shell.

## G-2 · Third-party broker branding — demote, do not delete

The owner does not want other brokers' names fronting our panels. Two things are being conflated
and they need different treatment:

- **Panel headings** like `BRAEMAR LIVE FORWARD FFA STRIP` — rename to a neutral, descriptive
  heading (`FORWARD FFA STRIP`). Same for any other panel whose title leads with a broker's brand.
- **Source attribution** — `Source: Braemar ACM Shipbroking`, the provenance-manifest entries, the
  Broker Voice records that are literally Fearnleys commentary. **Keep every one of these.** They
  are what makes the numbers checkable, and the entire anti-fabrication discipline of this project
  rests on being able to say where a figure came from. Attribution moves to the source line and the
  tooltip; it does not disappear.

If the owner wants attribution removed outright, that is his call to make explicitly — do not infer
it from this instruction, and do not silently strip provenance to satisfy it.

## G-3 · Data Catalogue & Provenance Museum — keep it, and fix the contradiction

What it is: an app-wide registry of every data series, with status (LIVE / ESTIMATED /
UNREGISTERED), row counts, date coverage, source, and two actions — "Audit Provenance" and "View in
App". **It is the single most valuable panel in the build for this project** and it stays: it is the
reader-facing version of the provenance discipline, and it is how anyone checks whether a number is
real. Do not remove it.

It does contradict itself. `index.html:13838` types the literal **"registry of all 86 data series"**
into markup, while the header at `index.html:50383` computes `seriesList.length` and renders
**"SHOWING 97 OF 102 REGISTERED SERIES (78 LIVE)"**. Same panel, 86 versus 102.

Delete the typed 86 and render that sentence from the same count the header uses. While you are
there, make the three numbers in the header self-consistent and defined: what "showing" counts
versus "registered" versus "LIVE" should be stated in the panel's tooltip.

## G-4 · Broker Voice shows 150 of 685 and hides the way to the rest

Measured: `Showing first 150 of 685 matches. Refine search query for specific topics.`

There *is* a `Load full archive` button and a `fearnVoiceType` selector, but the sentence does not
mention them, so the archive reads as truncated with no way forward. Two fixes:

1. Replace that dead-end sentence with real navigation — pagination, or "showing 150 of 685 ·
   **Load next 150** · **Load full archive**". The control that solves the problem must be in the
   sentence that states it.
2. Add the **month / year selector** the owner asked for. The archive is 11,717 rows of dated
   commentary; searching by keyword alone is the wrong primary axis. Desk + month + year, then
   keyword within that.

## G-5 · DONE — floating quote ticker restored

Landed at `45be25529`; **do not revert or re-style it.** The track holds all 25 quotes twice and the
animation translates by exactly -50%, so the loop is seamless. Items are `flex: 0 0 auto` and never
truncated, which is what fixes the old mid-word clipping - the edge mask fades quotes in and out
instead of chopping them. Speed is computed from the measured width (55 px/sec) and recomputed on
resize and after webfonts load; hover pauses it; `prefers-reduced-motion` disables it. Verified at
55.7 px/sec, 0 px movement while hovered, 0 items truncated.

## G-6 · Give the tab bar more room

Measured at both 1366 and 1920: `scrollWidth == clientWidth`, overflow **0**. So nothing is hidden
any more — this is comfort, not a bug. The twelve labels are packed edge to edge. Increase the
horizontal padding between items and let the bar breathe; keep zero overflow at 1366.

## G-7 · Baltic route codes have no tooltips at all

Measured on the pages where they appear: `C3 → 0/2 tipped`, `C5 → 0/3 tipped`. Not one route code
carries a gloss.

Every Baltic code rendered anywhere — C3, C5, C7, P1A, P2A, P3A, S1B, S4A, S4B, S10, TD3C, TD20,
TC2, TC20, H7 — needs a plain-language route description, either in the tooltip or as small text
beside the code in the header. `data/reference/baltic_route_taxonomy.json` is the authority; read
the route from there rather than writing descriptions by hand, and **do not edit that file to make
a lookup succeed** — if a code is missing from it, say so.

Two mapping errors have already been made against this taxonomy in this project. Use the file.

## G-8 · Series Museum is working correctly — do not "fix" it

Recording this so it does not get changed by mistake. Stepping its range buttons on VLCC:

| Button | Points | Window |
|---|---|---|
| 2Y | 24 | 2024-10 → 2026-09 |
| 5Y | 60 | 2021-10 → 2026-09 |
| 10Y | 105 | 2017-07 → 2026-09 |
| Max | 105 | 2017-07 → 2026-09 |

`10Y` and `Max` agree because the Fearnleys monthly series genuinely starts 2017-07 — 105 months is
all there is. That is honest behaviour and the right answer.

**Contrast with `20-FIVE.md` F-2**, where the Dashboard's `10Y` and `All` return the *same six
years* as `5Y` while the BDI series runs back to 1985. That one is broken. This one is not. Fix F-2;
leave the Series Museum alone.

## G-9 · "Commercial Fleet Supply & Orderbook Profile" must stay current

The owner rates this panel highly. Confirm its underlying series has a scheduled writer and is
refreshed on a cadence that matches its source, the same way every other series now is. If it has
no writer, wire one; if its source only updates quarterly, label it with its real as-of date rather
than leaving the reader to assume it is live.

## G-10 · Port Detail works, but fails silently by design

`openBunkerPortDetail(portName)` resolves the port by **name** against `DATA.bunkerSummary` and does
`if (!p) return;`. All 213 ports resolve today — verified, with real history behind each (Port Louis
142 points, Singapore 148, Rotterdam 148, Abidjan 9). But any upstream rename turns the button dead
with no error and no message.

Match on a stable port code rather than display name, and when a lookup does fail, show the reader
something instead of nothing.

## G-11 · Tracking map filters are inert — same root as F-5

I swept every toggle group on all twelve tabs, then re-verified the hits on a chart+marker
signature (my first pass used a truncated page-text hash and produced mostly false positives —
five of six "inert" groups turned out to work fine). Exactly one survived:

```
tracking  ['All Status', 'Laden', 'Ballast']  -> INERT (chart + marker signature identical)
```

For contrast, these were flagged and are genuinely fine — do not touch them:

```
signals  Daily Attribution / 30D Cumulative / 90D Cumulative  -> 3 distinct states
signals  BDRY vs BCI / BWET vs BDTI / BWET vs BCTI            -> 3 distinct states
bunkers  Spot Prices / 12M Forward Curves / Physical Volumes  -> 3 distinct states
etfs     1M / 3M / 6M / 1Y / 3Y / All                         -> 6 distinct states
```

`All Status / Laden / Ballast` joins the sector buttons from `20-FIVE.md` F-5: the tracking map
has a row of filters and **none of them repaint it**. Fix them together — they are one defect with
two faces, not two defects.

One milder thing found in the same pass: on Signals, a range group renders `3Y` distinctly but
`5Y` and `All` identically. Same family as F-2; worth checking while you are in there.


## G-12 · Shorten the signal banner and retire the trade-instruction words

The banner currently reads, on one line:

```
BEARISH SIGNAL: SELL (Overheated) : the index sits at 96.8% of its 5-year range. Historically since
1989, the BDI's next 3 months from this zone averaged -1.1% (median -2.3%, higher 47% of the time,
n = 2,632) against +7.3% for any random day. Base rate, not a forecast.
```

Too long for a banner. The evidence is right and should stay reachable, but it belongs in the
tooltip, not shouted across the page.

**Target:**

```
RICH  ·  the index sits at 96.8% of its 5-year range.
```

with the full base-rate sentence moved to that element's `data-tooltip`, unchanged and still
derived from `data/views/signal_base_rates.json`. Do not re-type the statistics into the tooltip
string - pass the same computed text through.

**Rename the ladder.** Two problems with the current labels: `SELL` and `ACCUMULATE` are trade
instructions, which is exactly what was removed from the banner body last round; and `GOLDEN DIP`,
`CATCHING KNIFE`, `VALUE TRAP` are retail-trader slang rather than broker language. Replace with
valuation words that describe where the index sits:

| Current label | New label |
|---|---|
| `SELL (Overheated)` | `Rich` |
| `ACCUMULATE` | `Cheap` |
| `GOLDEN DIP` | `Deep value` |
| `CATCHING KNIFE` | `Distressed` |
| `VALUE TRAP` | `Distressed - structurally weak` |
| `WAIT` | `Mid-range` |

Drop the `BEARISH SIGNAL:` / `BULLISH SIGNAL:` prefixes entirely - they are typed into the markup
around `#alertBearishText` / `#alertBullishText`, so remove them there rather than blanking them in
JS. Keep the existing red/green colour coding; the colour carries the direction without the page
having to shout it.

**Do not change the thresholds or the buckets** - only the words. The ladder still fires on the
same percentile and z-score boundaries, and `signal_base_rates.json` still keys on
`overheated` / `accumulate` / `deep_distress` / `unconditional`. This is a labelling change, not a
model change, and the tooltip must still say the numbers are a base rate and not a forecast.


---

## Assertions to add

`20-FIVE.md` already lists four. Add these:

5. **A panel that belongs to one sub-view must not render on the others.** Assert the forward FFA
   strip is visible on Broker Desk Overview and on no other Broker Desk sub-tab. Catches G-1 and
   the whole class of shell-versus-panel mistakes.
6. **Counts rendered in prose must equal the counts they describe.** Assert no typed integer in
   markup contradicts a computed one in the same panel. Catches G-3.
7. **Every Baltic route code rendered must resolve in `baltic_route_taxonomy.json` and carry a
   tooltip.** Catches G-7, and guards the taxonomy against a third mapping error.
8. **A truncation message must be accompanied by a working control that continues.** If the UI says
   "showing first N of M", assert a visible paginate/load control exists in the same container.
   Catches G-4.

## Order

G-1, G-3, G-7 first — each is small and immediately visible. Then `20-FIVE.md` F-1 to F-5. Then
G-4, G-6, G-9, G-10, G-11, G-12. G-5 is already done - see below. G-2 needs the owner's confirmation on scope before you touch attribution;
do the panel-heading half, leave the source lines alone.
