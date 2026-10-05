# Banchero Costa series: W39 advance + the three frozen families root-caused (2026-10-05 18:4x)

## What was verified before writing (W39, freight/ffa/commodities)

The 15:5x run WITHHELD W39 because it measured `freight=108 / ffa=18-36` with
~18 FFA tenor rows (`Sep-26`, `Q4 26`) misrouting. That figure is **NOT
reproducible** on the current tree. Both W39 PDFs in the corpus
(`banchero_costa_2026_W39_...pdf` and `bancosta_30_09_2026_...week_39_2026.pdf`)
are **byte-identical** (md5 2914f821b746cf4360bf77b70c05c0b4), and the canonical
md extracts `freight=90 ffa=36 commod=36` — the same shape as W38 (90) and W37
(87/89). No misroute.

Verification performed (no vision tool exists in this cron session - substituted
the strongest available check, per the skill):

1. **Verbatim reconciliation.** All 162 W39 values (90 freight `rate_current`+
   `rate_previous`, 36 ffa, 36 commodity) are found **verbatim in the PDF's own
   text layer** — `reconcile_w39.py`, 0 misses.
2. **Continuity.** The W39 `rate_previous` column equals the W38 `rate_current`
   column exactly on every spot-checked route: BCI 182 TC Average 52,315;
   BPI 82 TC Average 20,262; BSI 63 TC Avg 22,332; TD3C AG-China 1165.0. The
   published W-o-W percentages reproduce from (cur, prev).
3. **The implausible-looking values are faithful.** `TD3C-TCE AG-China
   1,234,685 usd/day` is printed by the publisher: the same page's chart axis
   is `0, 200,000 … 1,400,000` under the title `TD3C VLCC MEG-FAR EAST
   (USD/DAY)`. The extraction is faithful to the page, not a scaling bug.

**Appended (union, prefix-asserted):** freight 20,497 -> **20,587** (+90),
ffa 7,690 -> **7,726** (+36), commodities 8,519 -> **8,555** (+36). 0 duplicate
keys; re-run adds 0 (idempotent).

## Root cause: why secondhand-matrix / VHSS / FX / container-fixtures froze

`scripts/extract/build_banchero_series.py` (the committed builder for these
families) parses **HTML `<table>` elements** via BeautifulSoup. The current md
tier emits **GFM markdown tables**, so on the newest md it finds **0 tables**; a
sandboxed re-run (`scratch/banchero_build_trial/series_out/`) reproduces the
shipped rows and stops at 2026-09-14 (W38). The modern md consumer
(`run_banchero_world_class_llama.extract_structured_tables_from_md`) *can* read
these tables but **drops the W-o-W / Y-o-Y columns**, so it cannot fill the
schema either. Container fixtures are a second format change: a REPORTED
FIXTURES table through W24, then a templated **prose** paragraph from W25 on.

Note: the earlier "the builder would DOWNGRADE sales" warning stands — the
builder writes all 7 series with a thinner sales schema. It was therefore NOT
run; a bespoke reader was used instead.

## Fix: scripts/extract/publishers/backfill_banchero_matrix_fx_vhss.py (new)

Bespoke GFM/prose reader for the four families, same row schema and same date
convention as the builder (report_week = filename week; issue_date = the ISO
Monday of that week). UNION-append, prefix equality asserted, idempotent.

Traps found and fixed during the trial (each would have published wrong rows):
- The older md renders the change-cell arrow glyph as a literal `+/-`, so W38
  pct cells read `+0.0+/-%`. Stripped -> `+0.0%` (matches the shipped rows).
  Without this fix, every existing week would have been re-added as a duplicate.
- The secondhand predicate `Category | Unit | … | W-o-W` also matches a
  **tanker-route** secondhand table (`TC8 MEG-UKC(65k)` etc.). Applied the
  builder's vessel-class whitelist -> those 4 contaminant rows excluded.
- Fixtures prose sometimes omits `@14`; `**bold**` markers leaked into FX pairs.

## Result (all values verbatim in the PDF text layer: 130/130 added rows)

| series | before | +W39/backfill | after | dupes |
|---|---|---|---|---|
| secondhand_matrix | 1,891 | +7 | **1,898** | 0 |
| vhss | 469 | +7 (W39) +77 (W24-W35) | **553** | 0 |
| fx | 244 | +4 (W39) +40 (W24-W35) | **288** | 0 |
| container_fixtures | 267 | +26 (W24,29,30,35,37,38,39) | **293** | 0 |

Re-running the script adds 0 for all four (idempotent).

## Still open / not done

- Container fixtures W25-W28, W31-W34, W36 have no published fixtures paragraph
  (only some weeks report fixtures); they are genuinely absent, not dropped.
- The whole banchero tier remains **not displayed** (0 `bancosta_*series` refs
  in `index.html`) — this is KB completeness only.
- Changes LEFT UNCOMMITTED on branch `main` (a parallel automation is active;
  "NEVER touch main").
