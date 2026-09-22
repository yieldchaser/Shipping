"""Dump one extracted table as a matrix, with its header rows, to see which
column actually holds the quantity of interest.

Motivation: a series for the row label "PB Fines" came out with median 3.87 and
range -87..1,501 - not an iron ore price. The label_series view is correct (it
joins on doc/page/engine/table_idx/row_idx), so the mixing happened because the
series key omitted col_idx: a row's price, daily change and %change columns were
fused into one series. This prints the grid so the column roles are visible.
"""
import sys
from collections import defaultdict

import duckdb

doc = sys.argv[1]
want = sys.argv[2] if len(sys.argv) > 2 else None
con = duckdb.connect("data/extracted/corpus/db/corpus.duckdb", read_only=True)

if want:
    rows = con.execute(
        # NOTE: label_series joins on engine but does not expose it, so which
        # engine a pair came from cannot be recovered from this view.
        """select page, table_idx, count(*) n from label_series
           where doc = ? and label = ? group by 1,2 order by 3 desc limit 3""",
        [doc, want],
    ).fetchall()
    print("row label lives in (page, table_idx):", rows)
    if not rows:
        sys.exit("label not found")
    pg, tb = rows[0][0], rows[0][1]
else:
    pg, tb = 0, 0
if "eng" not in dir():
    pass
# pick the engine holding the most cells for this page/table
_eng = con.execute(
    """select engine, count(*) n from cells
       where doc = ? and page = ? and table_idx = ?
       group by 1 order by 2 desc limit 1""",
    [doc, pg, tb],
).fetchone()
eng = _eng[0] if _eng else "camelot-stream"

print(f"\n=== FULL GRID  page={pg} table={tb} engine={eng}")
data = con.execute(
    """select row_idx, col_idx, value from cells
       where doc = ? and page = ? and table_idx = ? and engine = ?
       order by row_idx, col_idx""",
    [doc, pg, tb, eng],
).fetchall()

grid = defaultdict(dict)
for ri, ci, v in data:
    grid[ri][ci] = v
maxc = max((max(d) for d in grid.values() if d), default=0)

hdr = "      " + "".join(f"c{ci:<11}" for ci in range(maxc + 1))
print(hdr)
for ri in sorted(grid):
    cells = []
    for ci in range(maxc + 1):
        v = str(grid[ri].get(ci, "."))
        cells.append(f"{v[:11]:<12}")
    print(f"r{ri:<4} " + "".join(cells))

print("\n=== numeric value stats by column (this grid):")
for ci in range(1, maxc + 1):
    vals = con.execute(
        """select num_value from cells
           where doc = ? and page = ? and table_idx = ? and engine = ?
             and col_idx = ? and is_numeric and num_value is not null""",
        [doc, pg, tb, eng, ci],
    ).fetchall()
    v = [x[0] for x in vals]
    if v:
        print(f"   c{ci:<3} n={len(v):<4} min={min(v):>12,.2f} max={max(v):>14,.2f}")
