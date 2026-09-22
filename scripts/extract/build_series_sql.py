"""Materialise series: (source, entity, measurement, block) - done in SQL.

Three defects this version fixes, all found by inspecting output rather than
trusting a "success":

1. Label join fan-out. `Change` and `CHANGE` share a header_key, so joining a
   label back per key produced one series row PER SPELLING: 5,221 rows for only
   3,448 distinct series_ids. Now one row per series_id, with a representative
   spelling chosen deterministically.

2. Orphan points. `series` was filtered to points >= threshold but
   `series_points` was not, so points existed for series that were never listed -
   and a duplicate-date count came back LARGER than the number of series, which
   is how the inconsistency was spotted. Both tables now cover the same set, and
   the point count is carried as a column so callers filter rather than lose data.

3. Block ambiguity. A measurement can appear in two column blocks of one table
   (e.g. a port-stock specification and a seaborne-brand specification both have
   "Silica"), giving two values for one date. Rather than silently averaging them
   - the exact failure mode that started this - each block becomes its own series
   via a block number, so the two are separable and labelled as such.

Integrity is asserted before reporting success: series count, orphan check, and
per-series declared-vs-actual point counts.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys

ISO_DATE = re.compile(r"(19|20)\d\d-[01]\d-[0-3]\d")
DMY = re.compile(r"([0-3]\d)[_-]([01]\d)[_-]((?:19|20)\d\d)(?![0-9])")
BROKER_WEEK = re.compile(r"((?:19|20)\d\d)[_-]?[Ww](\d{1,2})(?![0-9])")
NAMED_WEEK = re.compile(r"[Ww]eek[_-]?(\d{1,2})[_-]?((?:19|20)\d\d)")


def resolve_date(stem: str):
    stem = stem or ""
    m = ISO_DATE.search(stem)
    if m:
        try:
            return dt.date.fromisoformat(m.group(0))
        except ValueError:
            pass
    m = DMY.search(stem)
    if m:
        try:
            return dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass
    for rx, name_first in ((NAMED_WEEK, True), (BROKER_WEEK, False)):
        m = rx.search(stem)
        if m:
            wk, y = (int(m.group(1)), int(m.group(2))) if name_first else (int(m.group(2)), int(m.group(1)))
            if 1 <= wk <= 53:
                try:
                    return dt.date.fromisocalendar(y, wk, 1)
                except ValueError:
                    pass
    return None


SETUP = """
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
where not c.is_numeric and c.row_idx < n.first_num
  and c.value is not null and length(trim(c.value)) between 1 and 40
group by 1,2,3,4,5
"""

# block_no separates repeated (entity, measurement) column pairs inside one table
BLOCKS = """
create or replace temp view blocks as
select c.source, c.doc, c.doc_stem, c.page, c.table_idx, c.engine, c.row_idx, c.col_idx,
       lower(trim(l.value))  as entity_key,
       trim(l.value)         as entity,
       lower(coalesce(h.header,'')) as header_key,
       coalesce(h.header,'')  as header,
       c.num_value,
       -- Some publications encode the instrument in the FILENAME, not the table:
       -- Drewry AIS issues are "Drewry_AIS[_PDF]_{Product}_{Class}_Week{NN}_{YYYY}",
       -- and its six sections are identical across classes, so without this the
       -- same measurement from Crude/Aframax, Crude/VLCC and Drybulk/Handysize
       -- collapses into one series with several values per date. Measured: 30
       -- such series were class-blended and unusable, only 7 were identifiable.
       -- Non-matching stems yield '' and leave the series_id byte-identical.
       regexp_extract(c.doc_stem, '^Drewry_AIS(?:_PDF)?_(.*?)_Week', 1) as class_key,
       dense_rank() over (
           partition by c.doc, c.page, c.table_idx, c.engine, c.row_idx,
                        lower(coalesce(h.header,''))
           order by c.col_idx
       ) as block_no
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
  and l.value not like '%\n%'
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/extracted/corpus/db/corpus.duckdb")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--min-points", type=int, default=1)
    a = ap.parse_args()

    import duckdb
    con = duckdb.connect(a.db)
    con.execute(SETUP)
    con.execute(BLOCKS)

    stems = [r[0] for r in con.execute("select distinct doc_stem from blocks").fetchall()]
    dated = [(s, resolve_date(s)) for s in stems]
    print(f"doc stems: {len(stems):,}   undated: {sum(1 for _, d in dated if d is None):,}")
    con.execute("drop table if exists doc_dates")
    con.execute("create table doc_dates (doc_stem varchar, d date)")
    con.executemany("insert into doc_dates values (?,?)", [(s, d) for s, d in dated if d])

    if not a.write:
        for r in con.execute("""
            select source, entity, header, block_no, count(distinct doc_stem) n
            from blocks group by 1,2,3,4 order by n desc limit 15""").fetchall():
            print(f"   {r[0][:11]:<12}{r[1][:20]:<22}{r[2][:24]:<26}b{r[3]} n={r[4]}")
        return 0

    con.execute("drop table if exists series_points")
    con.execute("drop table if exists series")
    con.execute("""
        create table series_points as
        select b.source || '|' || b.entity_key || '|' || b.header_key
                 || '|b' || b.block_no
                 || case when b.class_key <> '' then '|' || b.class_key else '' end
                                                      as series_id,
               dd.d                                   as date,
               b.num_value                            as value
        from blocks b
        join doc_dates dd on dd.doc_stem = b.doc_stem
    """)
    con.execute("""
        create table series as
        select series_id,
               split_part(series_id,'|',1) as source,
               split_part(series_id,'|',2) as entity_key,
               split_part(series_id,'|',3) as measurement_key,
               try_cast(replace(split_part(series_id,'|',4),'b','') as integer) as block_no,
               split_part(series_id,'|',5)          as instrument_class,
               count(*)            as points,
               count(distinct date) as distinct_dates,
               min(date)           as first_date,
               max(date)           as last_date
        from series_points group by series_id
    """)
    # representative spellings, one row per series (was fanning out per variant)
    con.execute("""
        create or replace table series as
        select s.*, e.entity, h.measurement
        from series s
        join (select entity_key, min(entity) as entity
              from (select distinct entity_key, entity from blocks) group by 1) e
          on e.entity_key = s.entity_key
        join (select header_key, min(header) as measurement
              from (select distinct header_key, header from blocks) group by 1) h
          on h.header_key = s.measurement_key
    """)
    if a.min_points > 1:
        con.execute("delete from series_points where series_id not in "
                    "(select series_id from series where points >= ?)", [a.min_points])
        con.execute("delete from series where points < ?", [a.min_points])

    # A measurement+block can still be stated in more than one table of the same
    # document (e.g. a port-stock specification and a seaborne-brand one whose
    # headers both reduce to "Silica"). 166,293 (series, date) pairs hold more
    # than one value. Averaging them silently is the exact failure this work
    # started from, so instead: keep every raw observation in series_points, and
    # expose ONE row per (series, date) here with the spread and the count, so
    # the ambiguity is visible to any consumer rather than hidden by me.
    con.execute("drop table if exists series_daily")
    con.execute("""
        create table series_daily as
        select series_id, date,
               min(value) as value,
               max(value) as value_max,
               max(value) - min(value) as spread,
               count(*) as n_observations,
               count(distinct value) as n_distinct_values
        from series_points group by series_id, date
    """)

    n_s, n_p = (con.execute("select count(*) from series").fetchone()[0],
                con.execute("select count(*) from series_points").fetchone()[0])
    orphans = con.execute("""
        select count(*) from series_points p
        where not exists (select 1 from series s where s.series_id=p.series_id)""").fetchone()[0]
    mism = con.execute("""
        select count(*) from series s
        where s.points <> (select count(*) from series_points p where p.series_id=s.series_id)""").fetchone()[0]
    dup_dates = con.execute("""
        select count(*) from (select series_id, date from series_points
                              group by 1,2 having count(*)>1)""").fetchone()[0]
    n_d, n_amb = (con.execute("select count(*) from series_daily").fetchone()[0],
                  con.execute("select count(*) from series_daily where n_distinct_values>1").fetchone()[0])
    print(f"series={n_s:,}  series_points={n_p:,}  series_daily={n_d:,}")
    print(f"  daily rows with >1 distinct value (ambiguity disclosed, not averaged): {n_amb:,}")
    print(f"integrity: orphans={orphans}  mismatched={mism}  duplicate(series,date)={dup_dates}")
    if orphans or mism:
        print("INTEGRITY FAIL")
        return 2
    print("integrity OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
