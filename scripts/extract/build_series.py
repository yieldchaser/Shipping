"""Build time series the RIGHT way: a series is (row label, column header).

What went wrong before
----------------------
Two successive bugs in my own code produced two wrong conclusions:

1. Keying a table on (doc, table_idx, engine, row, col) without `page`. Table
   indices restart on every page, so six pages' worth of the same coordinate got
   fused, and I reported a 40% "collision" rate that did not exist. Including
   `page` gives exactly zero collisions across 6.8M cells.

2. Keying a series on (source, row_label) without `col_idx`. A row holds several
   different measurements - for "PB Fines" the columns are Fe, Alumina, Silica,
   Phos, Moisture - so five specification values were fused into one "series",
   and its median (3.87) was really the Silica % cell. The extraction was correct
   the whole time.

The correct model
-----------------
A row label names an ENTITY ("PB Fines"); a column names a MEASUREMENT ("Silica"
or a date). A series is the pair. So the column header must be resolved from the
header rows above each column, and carried into the series key.

Header rows are whatever sits above the first numeric row in that column; text
from several stacked header rows is joined (nested headers are common).

usage:
    python scripts/extract/build_series.py --report
    python scripts/extract/build_series.py --write
    python scripts/extract/build_series.py --entity "PB Fines" --show
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys

ISO_DATE = re.compile(r"(19|20)\d\d-[01]\d-[0-3]\d")
# Trailing \b does NOT work on these stems: fields are joined with "_", a word
# character, so there is no boundary after 2026 in "10_09_2026_x".
DMY = re.compile(r"([0-3]\d)[_-]([01]\d)[_-]((?:19|20)\d\d)(?![0-9])")
BROKER_WEEK = re.compile(r"((?:19|20)\d\d)[_-]?[Ww](\d{1,2})(?![0-9])")
NAMED_WEEK = re.compile(r"[Ww]eek[_-]?(\d{1,2})[_-]?((?:19|20)\d\d)")


def resolve_date(stem: str):
    stem = stem or ""
    m = ISO_DATE.search(stem)
    if m:
        try:
            return dt.date.fromisoformat(m.group(0)), "iso"
        except ValueError:
            pass
    m = DMY.search(stem)
    if m:
        try:
            return dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1))), "dmy"
        except ValueError:
            pass
    m = NAMED_WEEK.search(stem)
    if m and 1 <= int(m.group(1)) <= 53:
        try:
            return dt.date.fromisocalendar(int(m.group(2)), int(m.group(1)), 1), "named-week"
        except ValueError:
            pass
    m = BROKER_WEEK.search(stem)
    if m and 1 <= int(m.group(2)) <= 53:
        try:
            return dt.date.fromisocalendar(int(m.group(1)), int(m.group(2)), 1), "broker-week"
        except ValueError:
            pass
    return None, "none"


HEADERS_SQL = """
create or replace temp view col_headers as
with numeric_rows as (
    select doc, page, table_idx, engine, min(row_idx) as first_num
    from cells where is_numeric group by 1,2,3,4
)
select c.doc, c.page, c.table_idx, c.engine, c.col_idx,
       string_agg(trim(c.value), ' ') as header
from cells c
join numeric_rows n
  on n.doc=c.doc and n.page=c.page and n.table_idx=c.table_idx and n.engine=c.engine
where not c.is_numeric
  and c.row_idx < n.first_num
  and c.value is not null
  and length(trim(c.value)) between 1 and 40
group by 1,2,3,4,5
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/extracted/corpus/db/corpus.duckdb")
    ap.add_argument("--min-points", type=int, default=20)
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--entity", default=None)
    ap.add_argument("--show", action="store_true")
    a = ap.parse_args()

    import duckdb
    con = duckdb.connect(a.db)
    con.execute(HEADERS_SQL)

    rows = con.execute("""
        select c.source, c.doc_stem, trim(l.value) as entity,
               coalesce(h.header, '') as header, c.num_value
        from cells c
        join cells l
          on l.doc=c.doc and l.page=c.page and l.engine=c.engine
         and l.table_idx=c.table_idx and l.row_idx=c.row_idx and l.col_idx=0
         and not l.is_numeric
        left join col_headers h
          on h.doc=c.doc and h.page=c.page and h.table_idx=c.table_idx
         and h.engine=c.engine and h.col_idx=c.col_idx
        where c.is_numeric and c.col_idx > 0 and c.num_value is not null
          and length(trim(l.value)) between 2 and 60
    """).fetchall()
    print(f"entity/header/value triples: {len(rows):,}")

    cache, kinds, undated = {}, {}, 0
    series: dict[tuple, dict] = {}
    for source, stem, entity, header, value in rows:
        if stem not in cache:
            cache[stem] = resolve_date(stem)
        d, kind = cache[stem]
        kinds[kind] = kinds.get(kind, 0) + 1
        if d is None:
            undated += 1
            continue
        key = (source, entity.casefold(), header.casefold())
        s = series.setdefault(key, {"entity": entity, "header": header,
                                    "source": source, "pts": {}})
        s["pts"][d] = float(value)

    keep = {k: v for k, v in series.items() if len(v["pts"]) >= a.min_points}
    print(f"undated skipped: {undated:,}   date mix: {dict(sorted(kinds.items(), key=lambda kv: -kv[1]))}")
    print(f"series: {len(series):,} total, {len(keep):,} with >= {a.min_points} points")

    if a.entity and a.show:
        want = a.entity.casefold()
        hits = [(k, v) for k, v in series.items() if want in k[1]]
        print(f"\n=== entity matches: {len(hits)}")
        for (src, ek, hk), v in sorted(hits, key=lambda kv: -len(kv[1]["pts"]))[:10]:
            ds = sorted(v["pts"])
            vals = [v["pts"][d] for d in ds]
            print(f"  {src:<12} {v['entity'][:22]:<24} [{v['header'][:26]:<28}] "
                  f"n={len(ds):<5} {ds[0]}..{ds[-1]}  min={min(vals):,.2f} max={max(vals):,.2f}")

    if a.report or not (a.show and a.entity):
        top = sorted(keep.items(), key=lambda kv: -len(kv[1]["pts"]))[:22]
        print(f"\n{'source':<13}{'entity':<24}{'header':<26}{'pts':>6}  span")
        for (src, _, _), v in top:
            ds = sorted(v["pts"])
            print(f"{src[:11]:<13}{v['entity'][:22]:<24}{v['header'][:24]:<26}"
                  f"{len(ds):>6}  {ds[0]} .. {ds[-1]}")

    if not a.write:
        return 0

    con.execute("drop table if exists series_points")
    con.execute("drop table if exists series")
    con.execute("""create table series (series_id varchar, source varchar,
        entity varchar, header varchar, entity_key varchar, header_key varchar,
        points integer, first_date date, last_date date)""")
    con.execute("create table series_points (series_id varchar, date date, value double)")
    s_rows, p_rows = [], []
    for (src, ek, hk), v in keep.items():
        ds = sorted(v["pts"])
        sid = f"{src}|{ek}|{hk}"
        s_rows.append((sid, src, v["entity"], v["header"], ek, hk, len(ds), ds[0], ds[-1]))
        p_rows.extend((sid, d, v["pts"][d]) for d in ds)
    con.executemany("insert into series values (?,?,?,?,?,?,?,?,?)", s_rows)
    con.executemany("insert into series_points values (?,?,?)", p_rows)
    print(f"\nwrote series {len(s_rows):,} / series_points {len(p_rows):,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
