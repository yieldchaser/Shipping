"""Deal-ledger audit: separate "absent from the source" from "we failed to capture".

The distinction matters because the remedy is opposite in each case:
  absent from source  -> cross-reference from another dataset, or accept
  failed to capture    -> parse/re-extract what we already hold

Measured on the 549,434-row S&P fixtures ledger, the earlier read of "route is
0.0% populated, so it is missing" was WRONG in a useful way. Real rows look like:

    rate = "RNR"                                      <- Rate Not Reported: a
                                                         legitimate state, not a
                                                         gap
    rate = "USD 67 per ton basis Houston/Chiba via Panama"   <- rate AND route
                                                         as prose
    comment = "Ruwais / Options East | Original Commodity: 12,000 MT PPL"
                                                      <- the actual route, as
                                                         "<load> / <discharge>"

So the route/port data is present but unparsed. This script quantifies how much
is recoverable by parsing, versus genuinely not published by the source.
"""
from __future__ import annotations

import re
import sys

LEDGER = "data/derived/fearnleys_fixtures_full.parquet"
NOT_REPORTED = {"RNR", "N/A", "NA", "TBN", "-", "NOT DISCLOSED", "UNDISCLOSED"}


def main() -> int:
    import duckdb
    con = duckdb.connect()
    src = f"'{LEDGER}'"
    total = con.execute(f"select count(*) from {src}").fetchone()[0]
    print(f"deal ledger: {total:,} rows\n")

    # ---- rate field: how much is a real number vs an explicit non-disclosure?
    print("=== rate field states")
    rows = con.execute(f"""
        select case
          when rate is null or trim(rate) = '' then 'empty'
          when upper(trim(rate)) in ('RNR','N/A','NA','TBN','-') then 'explicitly not reported'
          when regexp_matches(rate, '[0-9]') then 'contains a number'
          else 'other text'
        end as kind, count(*) n
        from {src} group by 1 order by 2 desc""").fetchall()
    for k, n in rows:
        print(f"   {k:<28}{n:>9,}  {n / total * 100:5.1f}%")

    # ---- of the ones containing a number, how many also embed a route?
    n_route_in_rate = con.execute(f"""
        select count(*) from {src}
        where regexp_matches(rate, '[0-9]') and rate like '%/%'""").fetchone()[0]
    print(f"      of those, also naming a route ('.../...'): {n_route_in_rate:,}")

    # ---- comment: route recoverable as "<load> / <discharge> | ..."
    print("\n=== comment field states")
    rows = con.execute(f"""
        select case
          when comment like '% | Original Commodity:%' then 'route + commodity (structured)'
          when comment like '%/%' then 'slash present'
          when comment is null or trim(comment) = '' then 'empty'
          else 'other'
        end as kind, count(*) n
        from {src} group by 1 order by 2 desc""").fetchall()
    for k, n in rows:
        print(f"   {k:<32}{n:>9,}  {n / total * 100:5.1f}%")

    # ---- concrete recovery estimate
    rec = con.execute(f"""
        select count(*) from {src}
        where comment is not null and comment like '%/%'""").fetchone()[0]
    print(f"\nRECOVERABLE: route text present in comment for {rec:,} rows "
          f"({rec / total * 100:.1f}%)")
    n_port_only = con.execute(f"""
        select count(*) from {src}
        where (load_port is null or trim(load_port)='')
          and comment is not null and comment like '%/%'""").fetchone()[0]
    print(f"  ...of which load_port is currently EMPTY: {n_port_only:,} "
          f"-> direct gain if parsed")

    # ---- demonstrate the parse on a sample, so the claim is checkable
    print("\n=== parse demonstration (first 8 recoverable rows)")
    pat = re.compile(r"^(?P<legs>[^|]+?)\s*\|\s*Original Commodity:\s*(?P<com>.*)$")
    sample = con.execute(f"""
        select comment, rate, load_port, discharge_port from {src}
        where comment like '% | Original Commodity:%' limit 8""").fetchall()
    ok = 0
    for comment, rate, lp, dp in sample:
        m = pat.match(comment or "")
        if not m:
            continue
        legs = [x.strip() for x in m.group("legs").split("/") if x.strip()]
        load = legs[0] if legs else None
        disch = legs[1] if len(legs) > 1 else None
        ok += 1
        print(f"   comment={comment[:52]!r}")
        print(f"      -> load={load!r} disch={disch!r} commodity={m.group('com')[:28]!r}")
    print(f"\n   parsed cleanly: {ok}/{len(sample)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
