# Series-layer empty measurement_key: FIXED and SHIPPED (per-column header + date guard)

Run: 2026-10-04 ~16:4x-18:0x (source-by-source, 30m job). No extraction job was
running. All named sources are CLOSED. This run took the item the previous run
root-caused and left as "a design decision with numbers" (docs/series_key_phantom_verdict.md)
and turned it into a measured, ground-truthed fix that is now live.

## What was actually wrong (population stated)

Population = numeric cells that carry a col_idx=0 row label (i.e. cells that can
become a series point), using the SAME filter as `build_series_sql.py`'s BLOCKS
view: **1,635,971 cells**, of which **454,396 (27.8%)** resolve to NO column
header. (The earlier "1,000,707 / 2,493,286 = 40%" used a different denominator -
all numeric cells, label or not. 27.8% is the figure that matters, because only a
labelled-numeric cell becomes a series point.)

The previous run's single cause - "a chart's axis numbers drag the table's first
numeric row up and hide the header" - is real (proved again on Allied 03-10-2021
p9) but is only ONE of at least four mechanisms, and not the dominant one. The
dominant ones, all measured:

1. **Stacked / multi-row headers.** The old lookup took only non-numeric rows
   ABOVE the table's first numeric row. A nested header (BUNKER PRICES /
   ROTTERDAM SPORE / FUJAIRAH) puts its 2nd/3rd row BELOW the first numeric row,
   so those columns came back blank. Fixing this recovers the bulk of the text.
2. **Chart-tick drag** (the Allied case): a chart's tick numbers set the table's
   first numeric row too high up, hiding the real header row.
3. **Genuinely headerless columns** (a change/± column with no header text).
4. **Side-by-side table fusion**, where the header and the row label come from
   different sub-tables - a correctness issue, not just a missing label.

## Ground truth (from the page, not another extractor)

Positions read with `pymupdf` `page.get_text("words")` (this session has no image
tool; the skill's substitution - reconcile against the document's OWN text layer -
was used). Allied Weekly Market Report 03-10-2021, page 9, the market-stats table:

  y=377.8  01(x90.3) Oct(x101.6) | 27(x127.1) Aug(x138.4) | ±%(x170.0) | Min(x200.8) | Avg(x233.2) | Max(x264.7)
  y=389.7  Markets
  y=401.7  10year US Bond ...

So the real header row is `01 Oct | 27 Aug | ±% | Min | Avg | Max`. The old
lookup returned EMPTY for all six columns (first numeric row dragged into the
chart above). Correct model per the skill: the row label names the ENTITY, the
column names the MEASUREMENT - and `01 Oct`/`27 Aug` are PERIODS, not measurements.

## The fix (3 parts, shipped in scripts/extract/build_series_sql.py)

1. **Per-column header**: take the non-numeric rows above THIS column's own first
   numeric row (`min(row_idx) group by doc,page,table_idx,engine,col_idx`), so a
   chart or prose higher on the page no longer hides the table's header row.
2. **Table-wide fallback**: if a column has no numeric row of its own (so
   per-column finds nothing) fall back to the table-wide header. This preserves
   e.g. Clarkson Platou's `BUNKER PRICES` column that the pure per-column lookup
   dropped (verified: col5 had no numeric cell of its own).
3. **Date/period guard**: a header that is a BARE date or week
   (`01 Oct`, `Nov. 21`, `2021`, `21-Aug`, `Week 31`, `4-Feb`) is a PERIOD, not a
   measurement name - the observation date in series_points already carries it,
   and letting it into the series key fragments a weekly series into one series
   per issue. Blanked. **Month names only**, so `5 YEARS`, `10 YEARS`, `12 mos`
   and `IFO380` are NOT mistaken for dates (a first, looser rule wrongly blanked
   8,600+ of those - that is why the rule is month-scoped).

## Cell-level effect (measured on a scratch copy of the live cells)

| metric | old (table-wide) | new (hybrid + date guard) |
|---|---|---|
| headerless data cells | 454,396 (27.8%) | **335,546 (20.5%)** |
| recovered (was empty -> named) | - | **+168,381** |
| date-blanked (named period -> '') | - | 49,531 |
| lost non-date | - | **0** |
| renames (per-col joins a stacked header row) | - | 40,114 |

Net: **118,850 fewer headerless data cells**; 168,381 cells gain a real
measurement name; the only labels removed are bare periods (by design); and
**zero** non-date labels are lost.

## Series-layer ablation (all reproduced from scratch DB copies; integrity gate OK)

| variant | series | series_points | series_daily | empty measurement_key |
|---|---|---|---|---|
| live baseline (old script) | 5,241 | 1,167,616 | 942,263 | 2,247 (42.9%) |
| per-column only | 5,250 | 1,106,207 (-61,409) | 907,989 | 1,233 (23.5%) |
| per-column + LOOSE date rule (rejected) | 5,692 | 1,193,726 | 968,859 | 1,839 (32.3%) |
| **per-column + fallback + month-only date rule (SHIPPED)** | **5,743** | **1,193,579** | **970,291** | **1,796 (31.3%)** |

The "per-column only" row is why the previous run called the one-line fix worse:
by itself it fragments date-headed columns and drops 61,409 points. The date
guard is what makes per-column a net win. The loose-rule row is kept only to show
the over-blanking failure mode; it is superseded by the month-only rule.

## Verification (controls)

- **Control unit**: the OLD script on a scratch copy of the live cells reproduced
  the live layer EXACTLY - 5,241 / 1,167,616 / 942,263 - so the comparison is on
  the same input.
- **Ground truth**: both target pages checked against their own text layer -
  Allied p9 recovers `±% / Min / last 12 months Avg / Max` and blanks the two
  date columns; Clarkson Platou p2 keeps `BALTIC INDEX / EXCHANGE RATE /
  BUNKER PRICES` and recovers `FUJAIRAH`.
- **Live rebuild**: after patching the tracked script, the live DB rebuilt to
  5,743 / 1,193,579 / 970,291 with `integrity: orphans=0  mismatched=0` -
  identical to the scratch experiment, read back from the live DB.
- **Residual, stated**: the larger per-column band admits some prose as a header.
  Measured net-new prose-like headers = **838 cells (0.05%)** vs +168,381
  recovered (the old layer already carried 5,719 such). Accepted; noted, not hidden.

## Reproduce

  python3 - <<'PY'
  import duckdb; c=duckdb.connect('data/extracted/corpus/db/corpus.duckdb',read_only=True)
  print(c.execute("select count(*) from series").fetchone(),           # 5743
        c.execute("select count(*) from series_points").fetchone(),    # 1193579
        c.execute("select count(*) from series where measurement_key=''").fetchone())  # 1796
  PY

  # rebuild exactly:
  python3 scripts/extract/build_series_sql.py --write --min-points 20 \
      --db data/extracted/corpus/db/corpus.duckdb

Scratch (gitignored): scratch/meas_20261004/ (v0/v1/v2/v3 DB copies, the patched
variants, mkviews.py, page_cmp.py, v3check.py). Pre-change live DB backed up at
scratch/meas_20261004/corpus.pre_v3.duckdb.
