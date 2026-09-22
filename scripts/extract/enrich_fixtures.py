"""Enrich the S&P fixtures ledger - set-based, in SQL.

The first attempt walked 549,434 rows in Python and issued one UPDATE per row,
which was still running after 5 minutes and would have taken far longer. DuckDB
does the whole job in one CREATE TABLE AS: split the comment on '|', then on '/',
and coalesce the pieces into fields that are currently empty.

Audit basis (scripts/extract/audit_deal_ledger.py): `route` is populated in 1 of
549,434 rows and load/discharge ports in ~9%, but the route is actually sitting in
`comment` as "<load> / <discharge> | Original Commodity: <cargo>". 142,544 rows
carry such text; 135,563 of them have load_port empty. Verified 8/8 on real rows:

    "Ruwais / Options East | Original Commodity: 12,000 MT PPL"
        -> load=Ruwais  discharge=Options East  commodity=12,000 MT PPL

States that are LEFT ALONE because they are legitimate, not defects:
    rate = "RNR"   - the source explicitly declines to report a rate
    rate = ''      - the broker published no rate (93.5% of rows)
Rewriting either would fabricate data.
"""
from __future__ import annotations

import argparse
import sys

SRC = "data/derived/fearnleys_fixtures_full.parquet"
OUT = "data/derived/fearnleys_fixtures_enriched.parquet"

SET_BASED = """
create or replace table legs as
select *,
       -- text before the first '|' is the routing leg
       trim(regexp_extract(comment, '^([^|]*)', 1))            as legs_raw,
       -- cargo description, when the source gives one in the structured tail
       nullif(trim(regexp_extract(comment, 'Original Commodity:\\s*(.*)$', 1)), '')
                                                                as com_raw
from '{src}'
"""

ENRICH = """
create or replace table enriched as
select
    id, date, charterer, owner, vessel, imo, rate, period, segment, department,
    laycan, comment,
    -- keep what we had; fill only where empty
    coalesce(nullif(trim(load_port), ''),
             nullif(trim(split_part(legs_raw, '/', 1)), ''))      as load_port,
    coalesce(nullif(trim(discharge_port), ''),
             nullif(trim(split_part(legs_raw, '/', 2)), ''))      as discharge_port,
    coalesce(nullif(trim(commodity), ''), com_raw)                as commodity,
    case
      when route is not null and trim(route) <> '' then route
      when legs_raw like '%/%'
        then trim(split_part(legs_raw, '/', 1)) || ' / '
             || trim(split_part(legs_raw, '/', 2))
      else null
    end                                                           as route
from legs
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    import duckdb
    con = duckdb.connect()
    n = con.execute(f"select count(*) from '{SRC}'").fetchone()[0]
    print(f"source rows: {n:,}")

    con.execute(SET_BASED.format(src=SRC))
    con.execute(ENRICH)

    q = con.execute("""
        select
          count(*)                                                          total,
          count(*) filter (where load_port is not null and trim(load_port) <> '')     lp,
          count(*) filter (where discharge_port is not null and trim(discharge_port) <> '') dp,
          count(*) filter (where route is not null and trim(route) <> '')             rt,
          count(*) filter (where commodity is not null and trim(commodity) <> '')     com
        from enriched""").fetchone()
    total, lp, dp, rt, com = q
    print(f"\nAFTER ENRICHMENT (was: load 9.1%, route 0.0%, commodity 46.8%)")
    print(f"  load_port      : {lp:,}  ({lp/total*100:5.1f}%)")
    print(f"  discharge_port : {dp:,}  ({dp/total*100:5.1f}%)")
    print(f"  route          : {rt:,}  ({rt/total*100:5.1f}%)")
    print(f"  commodity      : {com:,}  ({com/total*100:5.1f}%)")

    print("\n=== spot-check (enriched fields vs original comment):")
    for r in con.execute("""
        select comment, load_port, discharge_port, route, commodity
        from enriched
        where comment like '% | Original Commodity:%' limit 6""").fetchall():
        print(f"   {str(r[0])[:54]!r}")
        print(f"      load={r[1]!r} disch={r[2]!r} route={r[3]!r} com={str(r[4])[:26]!r}")

    if not a.apply:
        print("\n(report only; --apply writes the enriched parquet)")
        return 0

    con.execute(f"copy enriched to '{OUT}' (format parquet)")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
