"""Build comparable time series from the corpus - from VERIFIED-CLEAN grids only.

Why this reads `cells` and not `label_series`
---------------------------------------------
`label_series` pivots (row label -> numeric value) but has no `engine` column,
and two engines write under the same (doc, table_idx). Measured on the real
corpus: 15,631 tables carry 2 engines, and 1,380,967 cells share a coordinate
with a DIFFERENT value. So (doc, table_idx, row_idx, col_idx) does not identify
a cell, and a pivot without `engine` silently mixes two different grids.

That is not theoretical: it made "PB Fines" - an iron ore price - come out with
median 3.87 and range -87..1,501, mixing prices, daily changes and differentials
from colliding sub-tables.

The gate
--------
A (doc, table_idx, engine) grid qualifies only if no (row, col) holds more than
one value. That excludes PDF two-up layouts whose side-by-side tables Camelot
merges into one grid, because there the row label pairs with values from a
neighbouring sub-table.

Measured qualification: html-table 100% clean, pdfplumber 44.9%, camelot-stream
32.1%. Excluded tables are counted and reported, never silently dropped.

usage:
    python scripts/extract/build_series.py --report
    python scripts/extract/build_series.py --write
    python scripts/extract/build_series.py --label "PB Fines" --show
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys

ISO_DATE = re.compile(r"(19|20)\d\d-[01]\d-[0-3]\d")
# NOTE: trailing \b does NOT work on these stems. Fields are joined with "_",
# which is a word character, so there is no boundary after "2026" in
# "10_09_2026_x" nor after "31" in "2021_W31_x". Measured: both patterns matched
# nothing until this became a digit lookahead.
DMY = re.compile(r"([0-3]\d)[_-]([01]\d)[_-]((?:19|20)\d\d)(?![0-9])")
BROKER_WEEK = re.compile(r"((?:19|20)\d\d)[_-]?[Ww](\d{1,2})(?![0-9])")
NAMED_WEEK = re.compile(r"[Ww]eek[_-]?(\d{1,2})[_-]?((?:19|20)\d\d)")

CLEAN_GRIDS = """
create or replace temp view clean_grids as
with per as (
    select source, doc, doc_stem, table_idx, engine,
           count(*) filter (where c > 1) as collided
    from (
        select source, doc, doc_stem, table_idx, engine, row_idx, col_idx,
               count(*) as c
        from cells group by 1,2,3,4,5,6,7
    ) group by 1,2,3,4,5
)
select source, doc, doc_stem, table_idx, engine from per where collided = 0
"""

# one engine per logical table, preferring the benched primary
ENGINE_RANK = ["camelot-stream", "pdfplumber", "tabula", "html-table"]


def resolve_date(stem: str) -> tuple[dt.date | None, str]:
    m = ISO_DATE.search(stem or "")
    if m:
        try:
            return dt.date.fromisoformat(m.group(0)), "iso"
        except ValueError:
            pass
    m = DMY.search(stem or "")
    if m:
        try:
            return dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1))), "dmy"
        except ValueError:
            pass
    m = NAMED_WEEK.search(stem or "")
    if m:
        wk, y = int(m.group(1)), int(m.group(2))
        if 1 <= wk <= 53:
            try:
                return dt.date.fromisocalendar(y, wk, 1), "named-week"
            except ValueError:
                pass
    m = BROKER_WEEK.search(stem or "")
    if m:
        y, wk = int(m.group(1)), int(m.group(2))
        if 1 <= wk <= 53:
            try:
                return dt.date.fromisocalendar(y, wk, 1), "broker-week"
            except ValueError:
                pass
    return None, "none"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/extracted/corpus/db/corpus.duckdb")
    ap.add_argument("--min-points", type=int, default=20)
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--label", default=None)
    ap.add_argument("--show", action="store_true")
    a = ap.parse_args()

    import duckdb
    con = duckdb.connect(a.db)
    con.execute(CLEAN_GRIDS)
    n_clean = con.execute("select count(*) from clean_grids").fetchone()[0]
    n_all = con.execute("select count(distinct (doc||'|'||table_idx||'|'||engine)) from cells").fetchone()[0]
    print(f"clean grids: {n_clean:,} of {n_all:,} engine-grids "
          f"({n_clean/max(n_all,1)*100:.1f}%) pass the collision gate")

    # label -> value pairs, reading ONLY clean grids
    con.execute("""
        create or replace temp view pairs as
        select c.source, c.doc, c.doc_stem, c.table_idx, c.engine,
               trim(c.value) as label, v.num_value
        from cells c
        join clean_grids g
          on g.doc=c.doc and g.table_idx=c.table_idx and g.engine=c.engine
        join cells v
          on v.doc=c.doc and v.table_idx=c.table_idx and v.engine=c.engine
         and v.row_idx=c.row_idx and v.col_idx > c.col_idx
         and v.is_numeric
        where c.col_idx = 0 and c.value is not null and not c.is_numeric
          and length(trim(c.value)) between 2 and 60
    """)
    rows = con.execute("select source, doc_stem, label, num_value from pairs").fetchall()
    print(f"label/value pairs from clean grids: {len(rows):,}")

    cache: dict[str, tuple] = {}
    kinds: dict[str, int] = {}
    series: dict[tuple, dict] = {}
    undated = 0
    for source, stem, label, value in rows:
        if stem not in cache:
            cache[stem] = resolve_date(stem)
        d, kind = cache[stem]
        kinds[kind] = kinds.get(kind, 0) + 1
        if d is None:
            undated += 1
            continue
        key = (source, label.casefold())
        s = series.setdefault(key, {"label": label, "source": source, "pts": {}})
        s["pts"][d] = float(value)

    keep = {k: v for k, v in series.items() if len(v["pts"]) >= a.min_points}
    print(f"undated pairs skipped: {undated:,}   date mix: {dict(sorted(kinds.items(), key=lambda kv:-kv[1]))}")
    print(f"series: {len(series):,} total, {len(keep):,} with >= {a.min_points} points")

    if a.report or not (a.show and a.label):
        top = sorted(keep.items(), key=lambda kv: -len(kv[1]["pts"]))[:22]
        print(f"\n{'source':<15}{'label':<34}{'pts':>7}  span")
        for (src, _), v in top:
            ds = sorted(v["pts"])
            print(f"{src[:13]:<15}{v['label'][:32]:<34}{len(ds):>7}  {ds[0]} .. {ds[-1]}")

    if a.label and a.show:
        want = a.label.casefold()
        for (src, lab), v in series.items():
            if want in lab:
                ds = sorted(v["pts"])
                vals = [v["pts"][d] for d in ds]
                print(f"\n{src} / {v['label']}: {len(ds)} points {ds[0]} .. {ds[-1]}")
                print(f"   min={min(vals):,.3f}  max={max(vals):,.3f}")
                for d in ds[:6]:
                    print(f"     {d}  {v['pts'][d]:>12,.4f}")
                print("     ...")
                for d in ds[-4:]:
                    print(f"     {d}  {v['pts'][d]:>12,.4f}")

    if not a.write:
        return 0

    con.execute("drop table if exists series_points")
    con.execute("drop table if exists series")
    con.execute("""create table series (series_id varchar, source varchar, label varchar,
                   label_key varchar, points integer, first_date date, last_date date)""")
    con.execute("create table series_points (series_id varchar, date date, value double)")
    s_rows, p_rows = [], []
    for (src, key), v in keep.items():
        ds = sorted(v["pts"])
        sid = f"{src}|{key}"
        s_rows.append((sid, src, v["label"], key, len(ds), ds[0], ds[-1]))
        p_rows.extend((sid, d, v["pts"][d]) for d in ds)
    con.executemany("insert into series values (?,?,?,?,?,?,?)", s_rows)
    con.executemany("insert into series_points values (?,?,?)", p_rows)
    print(f"\nwrote series {len(s_rows):,} rows / series_points {len(p_rows):,} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
