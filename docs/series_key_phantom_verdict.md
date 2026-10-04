# Series-layer key model: phantoms closed + the empty measurement_key root-caused

Run: 2026-10-04 ~15:4x (source-by-source, 30m job). No extraction job was running
(the only python.exe processes are the Hermes gateway / litellm proxies). All
named sources are CLOSED, so this run worked the state file's recurring
"derived 764-key collisions / 43% empty measurement_key / DB label_series"
target, previously filed as "a recorded human decision" across several runs.
This run measured it: two of the three items are PHANTOMS, the third is
root-caused with numbers.

Everything here is read-only on the live DB. The one experiment that wrote files
used scratch COPIES (scratch/serieskey_20261004/); the live corpus.duckdb was
restored byte-for-byte from corpus.pre_headerfix.duckdb and verified (5,241
series / 1,167,616 points, identical value sum).

## 1. label_series is a VIEW - it can never go stale (PHANTOM CLOSED)

information_schema.tables reports label_series as a VIEW, and so are cells and
catalogue:

  cells        = CREATE VIEW cells AS SELECT * FROM read_parquet('.../tables.parquet')
  label_series = CREATE VIEW ... FROM cells c INNER JOIN cells l ON ... (row-label pivot)

label_series (1,619,891 rows) is derived live from cells, which is derived live
from tables.parquet; it is rebuilt on every query. The recurring
"DB label_series (older pipeline)" item is therefore a PHANTOM - nothing to
"refresh". CLOSED.

## 2. The 764-collision phantom (CLOSED as a non-defect)

Query: (source, entity_key, measurement_key) triples with >1 series_id = 764
(2,686 series). Every one is separable, because series_id is NOT that 3-tuple:

  series_id = source \x1f entity_key \x1f header_key \x1f 'b'||block_no [\x1f class_key]

- 760 of 764 triples differ by block_no (repeat column blocks inside one table);
- 4 differ by class_key (Drewry AIS: Crude_VLCC vs Crude_Aframax vs LPG_FR).

block_no and class_key are IN the primary key, so no two rows share a series_id
(it is the table PK). This is the documented design of build_series_sql.py
("each repeated (entity,measurement) block becomes its own series via a block
number, so the two are separable"). Sampled on the live DB:

  shipbrokers / 10year us bond / w-o-w change % / b1   (~98 pts)
  shipbrokers / 10year us bond / '' / b2..b6           (155 pts each) <- 01 Oct, 27 Aug, +-%, Min, Avg, Max
  drewry_ais_pdfs / mdwt / '' / b1 / Crude_Aframax vs LPG_FR vs ...

The "disjoint ranges" a prior run read as "not a series key" are the expected
signature of DISTINCT measurement blocks sharing a header name (or a headerless
block). Not a defect. Do not re-chase.

Noted (not proven): under the coarse source='shipbrokers' bucket, two publishers
whose market tables are both headerless can have their block-2, block-3 ...
columns fuse by ordinal. Not measured as wrong; flagged only.

## 3. Empty measurement_key - ROOT-CAUSED (was: "43% empty", unknown cause)

Measured today: 2,247 / 5,241 series (42.9%) carry an empty measurement_key, and
at cell level 1,000,707 / 2,493,286 numeric data cells (40%) resolve to no column
header.

Root cause (NEW): col_headers in build_series_sql.py takes the table's FIRST
numeric row at TABLE grain -
  min(row_idx) ... group by doc, page, table_idx, engine
- then keeps only non-numeric cells ABOVE it. On any page where a chart's axis
numbers sit above the real table, that first-numeric row is dragged up into the
chart, so the table's own header row is excluded and every column comes back
unlabelled.

Ground truth (rendered text layer, not another extractor), Allied Weekly Market
Report 03-10-2021, page 9:

  current logic  : col1..col6 headers = (none)    col7 'Yuan per US Dollar'
  per-column     : col1 '01 Oct' col2 '27 Aug' col3 '+-%' col4 'Min' col5 'Avg' col6 'Max'

The chart ticks (6.90, 95.00, ... rows 4-15 cols 7/8) set the table-wide
first_num=4, hiding the real header row at row 16.

## 4. The one-line "fix" makes it WORSE - so it is a real design call

Changing group by 1,2,3,4 -> group by 1,2,3,4,5 (+ and n.col_idx=c.col_idx) was
measured on scratch copies of the live DB, after reproducing the live layer
exactly first (--min-points 20 -> 5,241 / 1,167,616 / 942,263):

| run                              | series       | series_points     | series_daily |
|----------------------------------|--------------|-------------------|--------------|
| live baseline (--min-points 20)  | 5,241        | 1,167,616         | 942,263      |
| per-column, no threshold         | 143,945->177,998 | 1,400,193     | 1,140,599    |
| per-column, --min-points 20      | 5,250        | 1,106,207 (-61,409) | 907,989    |

Why it fails: the Allied market table's header row holds PERIOD-DATE labels
(01 Oct, 27 Aug) mixed with stats (+-%, Min, Avg, Max). Turning those into
measurement_key fragments the series - each week's date-headed column becomes its
own series (no-threshold case: +24% series) - and at the fixed threshold the extra
fragmentation pushes ~61k points below 20 and out.

So the blank header is NOT a one-line grain bug to flip. A correct fix must
separate a "date/period column" from a "true measurement column" before the header
enters the series key - exactly the (row label, column header) doctrine in the
skill, where the header may be a date and must be handled as an axis, not a name.
Left as a design decision with these numbers. The naive patch was reverted;
tracked code is unchanged.

## Disposition

- label_series stale item: CLOSED (it is a view).
- 764-collision item: CLOSED as a non-defect (design; separable by series_id).
- 43% empty measurement_key: ROOT-CAUSED and measured; the trivial fix is
  REJECTED (makes it worse). Correct fix = date-vs-measurement header classifier.
  Recorded with numbers so no future run re-derives it from scratch.

## Reproduce

  import duckdb; c=duckdb.connect('data/extracted/corpus/db/corpus.duckdb',read_only=True)
  print(c.execute("select count(*) from series where measurement_key=''").fetchone())  # 2247

  # baseline the live layer exactly:
  python3 scripts/extract/build_series_sql.py --write --min-points 20 --db <scratch-copy>
  # per-column experiment script:
  scratch/serieskey_20261004/build_series_sql_percol.py
